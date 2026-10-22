import json
from pathlib import Path
import sys

import pytest

from security_eval.analyzers import dynamic
from security_eval.contracts import validate


def report(outcome="passed", exit_code=0):
    return {"sample_id": "sql_delete_user", "exit_code": exit_code, "pytest_version": "fixture",
            "collection_errors": [], "tests": [{"test_id": "test", "category": "security",
            "outcome": outcome, "message": ""}]}


def test_report_rejects_empty_duplicate_collection_and_mismatch():
    good = report()
    encode = lambda r: dynamic.PREFIX + json.dumps(r)
    assert dynamic.parse_report(encode(good), 0, "sql_delete_user") == good
    for text in ["", encode(good) + "\n" + encode(good),
                 encode({**good, "tests": []}), encode({**good, "collection_errors": ["oops"]}),
                 encode(report("error", 1))]:
        with pytest.raises(dynamic.RunnerError):
            dynamic.parse_report(text, 0, "sql_delete_user")
    assert dynamic.parse_report(encode(report("failed", 1)), 1, "sql_delete_user")["tests"][0]["outcome"] == "failed"


def test_command_timeout_and_output_limit():
    with pytest.raises(dynamic.RunnerError, match="Timeout"):
        dynamic.command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1)
    with pytest.raises(dynamic.RunnerError, match="OutputLimit"):
        dynamic.command([sys.executable, "-c", "print('x' * 3000000)"], timeout=5)


@pytest.mark.parametrize("mode", ["passed", "failed", "timeout", "missing_report", "cleanup_failure"])
def test_runner_lifecycle(tmp_path, monkeypatch, mode):
    calls = []
    def fake(args, timeout=15):
        calls.append(args)
        if args[1:3] == ["image", "inspect"]:
            return 0, json.dumps([{"Id": "sha256:fixture"}]), ""
        if args[1] == "start":
            if mode == "timeout":
                raise dynamic.RunnerError("Timeout: fixture")
            if mode == "missing_report":
                return 0, "no report", ""
            payload = report("failed" if mode == "failed" else "passed", int(mode == "failed"))
            return payload["exit_code"], dynamic.PREFIX + json.dumps(payload), ""
        if args[1] == "rm" and mode == "cleanup_failure":
            return 1, "", "daemon unavailable"
        return 0, "", ""
    monkeypatch.setattr(dynamic, "command", fake)
    code = tmp_path / "candidate.py"
    code.write_text("raise RuntimeError('never execute on host')")
    directory = tmp_path / "evidence"
    result = dynamic.DockerPytestAnalyzer(directory).analyze(code, {"sample_id": "sql_delete_user"}, "unit")
    validate("analysis", result)
    assert result["status"] == ("completed" if mode in ("passed", "failed") else "error")
    assert any(c[1:3] == ["rm", "-f"] for c in calls)
    create = next(c for c in calls if c[1] == "create")
    for flag in ("--read-only", "--network", "--memory", "--pids-limit", "--user"):
        assert flag in create
    assert "sha256:fixture" in create
    assert all((directory.parent / p).is_file() for p in result["evidence_files"])


def test_missing_docker_returns_error(tmp_path, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("docker unavailable")
    monkeypatch.setattr(dynamic, "command", missing)
    code = tmp_path / "code.py"
    code.write_text("pass")
    result = dynamic.DockerPytestAnalyzer(tmp_path / "evidence").analyze(code, {"sample_id": "sql_delete_user"}, "unit")
    assert result["status"] == "error"
    assert result["tests"] == []
