from pathlib import Path
from typing import Protocol

from ..contracts import utc_now, validate
from ..generation import digest


class Analyzer(Protocol):
    def analyze(self, code_path: Path, sample: dict, run_id: str) -> dict:
        """Return an analysis contract for this exact code hash; never rewrite code."""
        ...


def pending(code_path: Path, sample: dict, run_id: str, tool: str) -> dict:
    record = {
        "schema_version": "1.0", "run_id": run_id, "sample_id": sample["sample_id"],
        "tool": tool, "tool_version": None, "code_sha256": digest(code_path.read_bytes()),
        "status": "not_run", "started_at": None, "completed_at": utc_now(),
        "findings": [], "tests": [], "evidence_files": [],
        "error": None, "notes": "Integration pending; no security conclusion can be drawn.",
    }
    validate("analysis", record)
    return record
