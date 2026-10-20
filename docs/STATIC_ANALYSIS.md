# Static analysis (Member 2)

Bandit is the baseline scanner; two custom AST rules add input-to-sink checks for the
selected samples. Both produce the shared `analysis.json` contract, plus a combined
`static_summary.json`. **Every finding is an unverified potential issue**, not a confirmed
vulnerability; "no findings" does not mean the code is secure.

## Usage

Set up the environment as described in the README Quick Start (`requirements.txt` pins
`bandit==1.9.4`), then run:

```bash
security-eval static artifacts/sql-live-001 --out artifacts/sql-static-001   # one generation run
security-eval static artifacts/ --out artifacts/static-all-001               # every run dir in artifacts/
security-eval static path/to/code.py --sample-id sql_delete_user --out artifacts/static-file-001
python -m pytest -q tests/unit/test_static.py                                # rule validation
```

Inputs may be `.py` files, generation run directories (with `generation.json`; status and
code hash are verified as in `evaluate`), or a folder with such files and directories (not
recursive). Exit code: 0 if every scan completed, 1 if any scan or input failed, 2 for
usage errors (e.g. the output directory already exists; results are never overwritten).
`security-eval evaluate` runs the same two analyzers with Member 3's adapter.

## Output

```
<out>/static_summary.json          per-target status + flat list of all static findings
<out>/<target>/bandit.json         analysis contract (tool=bandit)
<out>/<target>/ast.json            analysis contract (tool=ast)
<out>/<target>/bandit.raw.json     unmodified Bandit JSON output (evidence)
<out>/<target>/bandit.stderr.txt   Bandit stderr (evidence)
<out>/<target>/ast_rules.json      rule set, descriptions, limitations and findings (evidence)
```

Each `static_summary.json` finding has `target, sample_id, source_file, tool, rule_id, cwe,
severity, confidence, line, message, evidence, validation_status`. `validation_status` is
always `unverified` here; set it later from review or dynamic tests. Per-target results
report `outcome` as `findings`, `no_findings` or `error`; bad inputs appear as `input_error`.
Bandit rule IDs (e.g. `B608`) keep their original severity, confidence and CWE; the
`tool` field separates them from `AST-*` findings.

## Bandit integration

Runs `python -m bandit -f json -q --ignore-nosec <file>` with a 120 s timeout and default
plugins. `--ignore-nosec` stops generated code from suppressing the baseline with
`# nosec`. Bandit exits 0 even when it cannot parse a file and only lists it under
`errors`, so a non-empty `errors` list is reported as `status: error`. Exit 1 must match
non-empty results; anything else is a tool failure.

## Custom AST rules (`analyzers/ast_rules.py`, rule set 0.1.0)

A value is *input-derived* if it is a parameter of the enclosing function, a call to
`input()`, or a local variable assigned (transitively) from one. Code is parsed with
`ast.parse` and never imported or executed.

| Rule | Sample | Reports | Cannot determine |
|---|---|---|---|
| `AST-SQL-001` (CWE-089, high) | `sql_delete_user` | `.execute/.executemany/.executescript` whose SQL text (first argument) is input-derived | Sanitization or trusted input; flows through other functions, attributes, containers, globals; any method named `execute` counts as SQL |
| `AST-CMD-001` (CWE-078) | `command_allowlist` | `subprocess.*`/`os.system`/`os.popen` with an input-derived command, either through a shell (high) or selecting the program to run (medium) | Allowlist checks before the call (validated code is still reported); argument injection when the program name is constant; `os.exec*`/`spawn*`; `shell=<variable>` is treated as `shell=True` |

Both rules are intraprocedural and flow-insensitive: they ignore statement order and
branches, and any expression that mentions an input-derived name counts as input-derived
(e.g. `len(username)`), which can produce false positives. Imports and aliases such as
`import subprocess as sp` and `from subprocess import run` are resolved; `getattr` and
dynamic imports are not. No rule for `path_read_file` yet: the relevant mistakes (missing
`resolve()`/containment checks) are hard to judge syntactically and are better left to
dynamic tests.

To add a rule, write `check(tree, ctx) -> list[finding]` and append a `Rule` to `RULES`.

## Validation

`tests/fixtures/static/` holds **hand-written rule-test fixtures**, not SecurityEval
samples or LLM output. Lines marked `# expect: <RULE>` must be reported, and nothing else
may be. `tests/unit/test_static.py` checks:

- the exact (rule, line) pairs for the unsafe and safe fixtures of each rule;
- the command rule's severity split (shell: high; program choice: medium);
- contract validity and evidence files;
- syntax errors in both tools, Bandit's no-findings case and batch input errors;
- that results are never overwritten.

As a sanity check, the suite was run against deliberately broken copies of the rules (input
source, propagation, `shell=` handling, list-head check, alias resolution); each one made
at least one test fail. Passing fixtures show the rules behave as designed on these
patterns; they do not measure false-positive or false-negative rates on real code.

## Assumptions to confirm

- Member 1: candidates live in `artifacts/<run>/` with `generation.json`, `sample.json` and
  `code.py`, as the scaffold writes them.
- Member 3: `static_summary.json` findings can be joined with dynamic results by
  `sample_id` + `code_sha256`; `validation_status` is the field to update after testing.
- Shared harness: `BanditAnalyzer(out_dir)` / `ASTAnalyzer(out_dir)` now take the output
  directory for evidence files; `pipeline.evaluate` passes it.
