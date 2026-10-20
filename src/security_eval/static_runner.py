"""Member 2: run Bandit and AST rules over files or generation run directories.

Writes, under a new output directory:
  <target>/bandit.json, <target>/ast.json   analysis contracts (shared schema)
  <target>/bandit.raw.json, bandit.stderr.txt, ast_rules.json   raw evidence
  static_summary.json   flat list of all static findings plus per-target scan status
"""
import re
from pathlib import Path

from jsonschema.exceptions import ValidationError

from .analyzers.static import ASTAnalyzer, BanditAnalyzer
from .contracts import utc_now, validate, write_json
from .generation import digest
from .pipeline import load_candidate

SUMMARY_VERSION = "static-summary-0.1"


def _sample_id(name: str) -> str:
    sample_id = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    return sample_id if re.match(r"^[a-z]", sample_id) else "file_" + sample_id


def collect_targets(paths: list[Path], sample_id: str | None = None) -> list[dict]:
    """Resolve inputs into targets: {name, path, sample, run_id} or {name, path, input_error}."""
    targets = []

    def add_file(path: Path):
        sid = sample_id or _sample_id(path.stem)
        targets.append({"name": path.stem, "path": path, "sample": {"sample_id": sid},
                        "run_id": "static:" + digest(path.read_bytes())})

    def add_run(run_dir: Path):
        try:
            code, sample, run_id = load_candidate(run_dir)
            targets.append({"name": run_dir.name, "path": code, "sample": sample, "run_id": run_id})
        except (ValueError, OSError, ValidationError, TypeError) as exc:
            targets.append({"name": run_dir.name, "path": run_dir, "input_error": str(exc)})

    for path in paths:
        if path.is_file() and path.suffix == ".py":
            add_file(path)
        elif path.is_dir() and (path / "generation.json").exists():
            add_run(path)
        elif path.is_dir():
            runs = sorted(p for p in path.iterdir() if p.is_dir() and (p / "generation.json").exists())
            files = sorted(p for p in path.glob("*.py") if p.is_file())
            for run in runs:
                add_run(run)
            for file in files:
                add_file(file)
            if not runs and not files:
                targets.append({"name": path.name, "path": path,
                                "input_error": "No .py files or generation run directories found"})
        else:
            targets.append({"name": path.stem or "input", "path": path,
                            "input_error": "Not an existing .py file or directory"})
    if sample_id and len(targets) > 1:
        raise ValueError("--sample-id can only be used with a single Python file")
    seen = {}
    for target in targets:  # unique output subdirectory per target
        base = _sample_id(target["name"])
        seen[base] = seen.get(base, 0) + 1
        target["out_name"] = base if seen[base] == 1 else f"{base}_{seen[base]}"
    return targets


def _outcome(result: dict) -> str:
    if result["status"] != "completed":
        return result["status"]
    return "findings" if result["findings"] else "no_findings"


def run_static(paths: list[Path], out: Path, sample_id: str | None = None) -> dict:
    targets = collect_targets(paths, sample_id)
    out.mkdir(parents=True, exist_ok=False)
    summary = {"summary_version": SUMMARY_VERSION, "generated_at": utc_now(),
               "note": "Findings are scanner reports of potential issues (validation_status "
                       "'unverified'); they are not confirmed vulnerabilities. 'no_findings' "
                       "does not establish that the code is secure.",
               "targets": [], "findings": []}
    for target in targets:
        entry = {"target": target["out_name"], "source_file": str(target["path"])}
        if "input_error" in target:
            entry.update(sample_id=None, code_sha256=None, results={},
                         input_error=target["input_error"])
            summary["targets"].append(entry)
            continue
        target_out = out / target["out_name"]
        entry.update(sample_id=target["sample"]["sample_id"],
                     code_sha256=digest(target["path"].read_bytes()), results={})
        for analyzer in (BanditAnalyzer(target_out), ASTAnalyzer(target_out)):
            result = analyzer.analyze(target["path"], target["sample"], target["run_id"])
            validate("analysis", result)
            write_json(target_out / f'{result["tool"]}.json', result)
            entry["results"][result["tool"]] = {
                "status": result["status"], "outcome": _outcome(result),
                "finding_count": len(result["findings"]), "tool_version": result["tool_version"],
                "record": f'{target["out_name"]}/{result["tool"]}.json', "error": result["error"]}
            for f in result["findings"]:
                summary["findings"].append({
                    "target": target["out_name"], "sample_id": result["sample_id"], "source_file": str(target["path"]),
                    "tool": result["tool"], "rule_id": f["rule_id"], "cwe": f["cwe"],
                    "severity": f["severity"], "confidence": f["confidence"], "line": f["line"],
                    "message": f["message"], "evidence": f["evidence"],
                    "validation_status": "unverified"})
        summary["targets"].append(entry)
    write_json(out / "static_summary.json", summary)
    return summary


def format_summary(summary: dict) -> str:
    lines = []
    for t in summary["targets"]:
        if "input_error" in t:
            lines.append(f'{t["target"]}: INPUT ERROR - {t["input_error"]}')
            continue
        parts = [f'{tool}={r["outcome"]}' + (f'({r["finding_count"]})' if r["finding_count"] else "")
                 for tool, r in t["results"].items()]
        lines.append(f'{t["target"]} [{t["sample_id"]}]: ' + ", ".join(parts))
        for tool, r in t["results"].items():
            if r["error"]:
                lines.append(f'    {tool} error: {r["error"]["type"]}: {r["error"]["message"]}')
        for f in summary["findings"]:
            if f["target"] == t["target"]:
                lines.append(f'    L{f["line"]} {f["tool"]}:{f["rule_id"]} {f["cwe"] or "-"} '
                             f'sev={f["severity"]} conf={f["confidence"]} - {f["message"][:90]}')
    lines.append(f'Total findings: {len(summary["findings"])} (all unverified scanner reports)')
    return "\n".join(lines)


def all_completed(summary: dict) -> bool:
    return all("input_error" not in t and all(r["status"] == "completed" for r in t["results"].values())
               for t in summary["targets"])
