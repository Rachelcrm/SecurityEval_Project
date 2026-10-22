"""Container-only pytest entry point. Reports are observations, not tamper-proof attestations."""
import hashlib
import json
from pathlib import Path
import platform
import sys

import pytest

FILES = {
    "sql_delete_user": "test_sql_delete_user.py",
    "command_allowlist": "test_command_allowlist.py",
    "path_read_file": "test_path_read_file.py",
}
PREFIX = "SECURITY_EVAL_REPORT="


class Recorder:
    def __init__(self):
        self.categories = {}
        self.results = {}
        self.collection_errors = []

    def pytest_collection_modifyitems(self, items):
        for item in items:
            categories = [m for m in ("functional", "security") if item.get_closest_marker(m)]
            if len(categories) != 1:
                raise pytest.UsageError("Each candidate test needs exactly one category")
            self.categories[item.nodeid] = categories[0]

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(str(report.longrepr)[:12000])

    def pytest_runtest_logreport(self, report):
        if report.when != "call" and report.passed:
            return
        outcome = report.outcome
        if report.failed and report.when != "call":
            outcome = "error"
        old = self.results.get(report.nodeid)
        if old and old["outcome"] == "error":
            return
        self.results[report.nodeid] = {
            "test_id": report.nodeid,
            "category": self.categories[report.nodeid],
            "outcome": outcome,
            "message": str(report.longrepr)[:12000] if report.longrepr else "",
        }


def main():
    sample = sys.argv[1]
    test_file = FILES[sample]
    # Hash before candidate import; persist the exact test environment identity.
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path("/tests").glob("*.py")
    }
    recorder = Recorder()
    exit_code = int(pytest.main([
        f"/tests/{test_file}", "-v", "--strict-markers", "-p", "no:cacheprovider",
        "--basetemp=/tmp/pytest", "--capture=fd",
    ], plugins=[recorder]))
    payload = {
        "sample_id": sample, "exit_code": exit_code,
        "python_version": platform.python_version(), "pytest_version": pytest.__version__,
        "test_sha256": hashes, "tests": list(recorder.results.values()),
        "collection_errors": recorder.collection_errors,
    }
    print("\n" + PREFIX + json.dumps(payload), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
