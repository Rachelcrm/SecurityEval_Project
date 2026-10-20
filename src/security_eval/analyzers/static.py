"""Member 2: Bandit baseline and custom AST rules, both returning the analysis contract.

Candidate code is only read (Bandit and ``ast.parse``); it is never imported or executed.
"""
import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from ..contracts import utc_now, validate, write_json
from ..generation import digest
from . import ast_rules

BANDIT_TIMEOUT_SECONDS = 120
LEVELS = {"low", "medium", "high"}


def _record(code_bytes: bytes, sample: dict, run_id: str, tool: str, started_at: str) -> dict:
    return {
        "schema_version": "1.0", "run_id": run_id, "sample_id": sample["sample_id"],
        "tool": tool, "tool_version": None, "code_sha256": digest(code_bytes),
        "status": "error", "started_at": started_at, "completed_at": None,
        "findings": [], "tests": [], "evidence_files": [], "error": None, "notes": "",
    }


def _fail(record: dict, kind: str, message: str) -> dict:
    record.update(status="error", completed_at=utc_now(), findings=[],
                  error={"type": kind, "message": message[:2000] or kind})
    validate("analysis", record)
    return record


def _level(value) -> str:
    value = str(value or "").lower()
    return value if value in LEVELS else "unknown"


def _cwe(issue_cwe) -> str | None:
    cwe_id = (issue_cwe or {}).get("id") if isinstance(issue_cwe, dict) else None
    return f"CWE-{int(cwe_id):03d}" if cwe_id else None


class BanditAnalyzer:
    """Runs Bandit with default plugins on one file and maps its JSON to our contract.

    ``out_dir`` receives the raw evidence (``bandit.raw.json``, ``bandit.stderr.txt``).
    """

    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)

    def analyze(self, code_path: Path, sample: dict, run_id: str) -> dict:
        record = _record(code_path.read_bytes(), sample, run_id, "bandit", utc_now())
        try:
            record["tool_version"] = "bandit " + version("bandit")
        except PackageNotFoundError:
            return _fail(record, "ToolMissing", "Bandit is not installed; run pip install '.[static]'")
        # --ignore-nosec: generated code must not be able to suppress the baseline scanner.
        command = [sys.executable, "-m", "bandit", "-f", "json", "-q", "--ignore-nosec",
                   str(code_path.resolve())]
        self.out_dir.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(command, capture_output=True, text=True,
                                  timeout=BANDIT_TIMEOUT_SECONDS, cwd=self.out_dir)
        except subprocess.TimeoutExpired:
            return _fail(record, "Timeout", f"Bandit exceeded {BANDIT_TIMEOUT_SECONDS}s")
        except OSError as exc:
            return _fail(record, type(exc).__name__, str(exc))
        (self.out_dir / "bandit.raw.json").write_text(proc.stdout, encoding="utf-8")
        (self.out_dir / "bandit.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        record["evidence_files"] = ["bandit.raw.json", "bandit.stderr.txt"]
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return _fail(record, "ToolFailure", f"Bandit exit {proc.returncode}, no JSON output: "
                         + proc.stderr.strip()[-500:])
        # Bandit exits 0 on unparsable files and lists them only under "errors".
        if report.get("errors"):
            return _fail(record, "ScanError", "; ".join(e.get("reason", "unknown") for e in report["errors"]))
        results = report.get("results", [])
        if proc.returncode not in (0, 1) or (proc.returncode == 1) != bool(results):
            return _fail(record, "ToolFailure", f"Unexpected Bandit exit {proc.returncode} "
                         f"with {len(results)} results")
        record["findings"] = [{
            "rule_id": r.get("test_id") or "unknown",
            "cwe": _cwe(r.get("issue_cwe")),
            "severity": _level(r.get("issue_severity")),
            "confidence": _level(r.get("issue_confidence")),
            "message": r.get("issue_text") or "(no description)",
            "line": r.get("line_number") or None,
            "evidence": f'{r.get("test_name", "")}: {(r.get("code") or "").strip()}'[:1000] or "n/a",
        } for r in results]
        record.update(status="completed", completed_at=utc_now(),
                      notes="Bandit findings are potential issues requiring validation, not confirmed "
                            "vulnerabilities. No findings does not establish that the code is secure.")
        validate("analysis", record)
        return record


class ASTAnalyzer:
    """Applies the rules in ``ast_rules.RULES``; writes ``ast_rules.json`` as evidence."""

    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)

    def analyze(self, code_path: Path, sample: dict, run_id: str) -> dict:
        code_bytes = code_path.read_bytes()
        record = _record(code_bytes, sample, run_id, "ast", utc_now())
        record["tool_version"] = (f"ast-rules {ast_rules.RULESET_VERSION} "
                                  f"(python {sys.version.split()[0]})")
        try:
            findings = ast_rules.scan(code_bytes)
        except SyntaxError as exc:
            return _fail(record, "SyntaxError", f"line {exc.lineno}: {exc.msg}")
        except (ValueError, UnicodeDecodeError) as exc:
            return _fail(record, type(exc).__name__, str(exc))
        write_json(self.out_dir / "ast_rules.json", {
            "ruleset_version": ast_rules.RULESET_VERSION,
            "rules": [{"rule_id": r.rule_id, "cwe": r.cwe, "description": r.description,
                       "limitations": r.limitations} for r in ast_rules.RULES],
            "findings": findings,
        })
        record.update(status="completed", completed_at=utc_now(), findings=findings,
                      evidence_files=["ast_rules.json"],
                      notes="AST findings flag potentially unsafe patterns within one function; they "
                            "are not confirmed vulnerabilities. See ast_rules.json for rule limitations.")
        validate("analysis", record)
        return record
