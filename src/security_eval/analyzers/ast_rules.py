"""Custom AST rules (Member 2). Source is parsed as data; it is never imported or executed.

Both rules use the same intraprocedural approximation of "untrusted input": a value is
*input-derived* if it is a parameter of the enclosing function, a call to ``input()``, or a
local variable assigned (directly or transitively) from an expression that contains one.
To add a rule, write ``check(tree, ctx) -> list[finding]`` and append a ``Rule`` to RULES.
"""
import ast
from dataclasses import dataclass
from typing import Callable

RULESET_VERSION = "0.1.0"
SQL_METHODS = {"execute", "executemany", "executescript"}
SHELL_SINKS = {"os.system", "os.popen", "subprocess.getoutput", "subprocess.getstatusoutput"}
PROCESS_SINKS = {"subprocess.run", "subprocess.call", "subprocess.check_call",
                 "subprocess.check_output", "subprocess.Popen"}
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


class Context:
    """Per-file helpers: source text, parent links, import aliases and per-scope taint."""

    def __init__(self, tree: ast.Module, source: str):
        self.source = source
        self.parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        self.aliases = {}  # local name -> qualified name, e.g. "sp" -> "subprocess"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
        self._taint = {}

    def qualified_name(self, func: ast.expr) -> str | None:
        if isinstance(func, ast.Name):
            return self.aliases.get(func.id, func.id)
        if isinstance(func, ast.Attribute):
            base = self.qualified_name(func.value)
            return f"{base}.{func.attr}" if base else None
        return None

    def scope(self, node: ast.AST) -> ast.AST:
        while node in self.parent and not isinstance(node, FUNCTIONS):
            node = self.parent[node]
        return node

    def tainted(self, scope: ast.AST) -> set[str]:
        if scope not in self._taint:
            names = set()
            if isinstance(scope, FUNCTIONS):
                args = scope.args
                names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
                names |= {a.arg for a in (args.vararg, args.kwarg) if a}
            self._taint[scope] = names
            assignments = [n for n in ast.walk(scope)
                           if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign,
                                             ast.NamedExpr, ast.For, ast.comprehension))]
            changed = True
            while changed:  # flow-insensitive fixpoint: loops and reassignments are approximated
                changed = False
                for node in assignments:
                    value = getattr(node, "value", None) or getattr(node, "iter", None)
                    if value is None or not self.derived(value, scope):
                        continue
                    targets = getattr(node, "targets", None) or [node.target]
                    for target in targets:
                        for name in ast.walk(target):
                            if isinstance(name, ast.Name) and name.id not in names:
                                names.add(name.id)
                                changed = True
        return self._taint[scope]

    def derived(self, expr: ast.AST, scope: ast.AST) -> bool:
        names = self._taint.get(scope) if scope in self._taint else self.tainted(scope)
        for node in ast.walk(expr):
            if isinstance(node, ast.Name) and node.id in names:
                return True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "input":
                return True
        return False

    def finding(self, rule: "Rule", node: ast.AST, severity: str, message: str) -> dict:
        segment = ast.get_source_segment(self.source, node) or ast.unparse(node)
        return {"rule_id": rule.rule_id, "cwe": rule.cwe, "severity": severity,
                "confidence": "medium", "message": message, "line": node.lineno,
                "evidence": " ".join(segment.split())[:300]}


def _first_arg(call: ast.Call, keyword: str) -> ast.expr | None:
    if call.args:
        return call.args[0]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def check_sql(tree: ast.Module, ctx: Context) -> list[dict]:
    findings = []
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr in SQL_METHODS):
            continue
        query = _first_arg(call, "sql")
        if query is None or isinstance(query, ast.Constant):
            continue
        if ctx.derived(query, ctx.scope(call)):
            findings.append(ctx.finding(SQL_RULE, call, "high",
                f"SQL text passed to .{call.func.attr}() is built from input-derived data; "
                "use a constant query with bound parameters (e.g. '?' placeholders)."))
    return findings


def check_command(tree: ast.Module, ctx: Context) -> list[dict]:
    findings = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        name = ctx.qualified_name(call.func)
        if name not in SHELL_SINKS and name not in PROCESS_SINKS:
            continue
        command = _first_arg(call, "args" if name in PROCESS_SINKS else "cmd")
        if command is None or not ctx.derived(command, ctx.scope(call)):
            continue
        shell = name in SHELL_SINKS or any(
            k.arg == "shell" and not (isinstance(k.value, ast.Constant) and not k.value.value)
            for k in call.keywords)
        if shell:
            findings.append(ctx.finding(COMMAND_RULE, call, "high",
                f"{name}() passes an input-derived command to a shell; shell metacharacters "
                "in the input may run additional commands."))
        elif not (isinstance(command, (ast.List, ast.Tuple)) and command.elts
                  and isinstance(command.elts[0], ast.Constant)):
            findings.append(ctx.finding(COMMAND_RULE, call, "medium",
                f"{name}() executes a program whose name is input-derived; verify that an "
                "allowlist check restricts which program can run."))
    return findings


@dataclass(frozen=True)
class Rule:
    rule_id: str
    cwe: str
    description: str
    limitations: str
    check: Callable[[ast.Module, Context], list[dict]]


SQL_RULE = Rule(
    "AST-SQL-001", "CWE-089",
    "A DB-API .execute/.executemany/.executescript call whose SQL text (first argument) is "
    "derived from a function parameter or input() instead of being a constant.",
    "Intraprocedural and flow-insensitive: misses taint passed through other functions, "
    "attributes, containers or globals; cannot tell whether the input was sanitized or is "
    "trusted; any method named execute is treated as a SQL sink.", check_sql)
COMMAND_RULE = Rule(
    "AST-CMD-001", "CWE-078",
    "A subprocess/os command call whose command is input-derived and either runs through a "
    "shell (shell=True, os.system, os.popen, getoutput) or selects the program to run.",
    "Cannot see allowlist or validation checks before the call, so validated commands are "
    "still reported; lists with a constant program name are not reported (argument "
    "injection is out of scope); shell=<variable> is treated as shell=True; os.exec*/spawn* "
    "and dynamic imports are not covered.", check_command)
RULES = (SQL_RULE, COMMAND_RULE)


def scan(code: bytes | str) -> list[dict]:
    """Return contract-shaped findings sorted by line. Raises SyntaxError for invalid code."""
    tree = ast.parse(code)
    source = code.decode("utf-8", errors="replace") if isinstance(code, bytes) else code
    ctx = Context(tree, source)
    findings = [f for rule in RULES for f in rule.check(tree, ctx)]
    return sorted(findings, key=lambda f: (f["line"], f["rule_id"]))
