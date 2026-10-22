import json

import pytest

from security_eval.contracts import load_samples
from security_eval.generation import generate, prepare
from security_eval.pipeline import evaluate
from test_generation import fixture_client
from test_contracts import SAMPLES


def test_pipeline_records_dynamic_error_and_detects_tampering(tmp_path, monkeypatch):
    from security_eval.analyzers import dynamic
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("Docker mocked unavailable")
    monkeypatch.setattr(dynamic, "command", unavailable)
    sample = load_samples(SAMPLES)[0]
    run = tmp_path / "run"
    generate(sample, run, "fixture-only", client=fixture_client("def remove_user(conn, username): return 0"))
    results = evaluate(run, tmp_path / "analysis")
    assert len(results) == 3
    assert [r["status"] for r in results] == ["completed", "completed", "error"]
    assert json.loads((tmp_path / "analysis/bandit.json").read_text())["findings"] == []
    assert (tmp_path / "analysis/bandit.raw.json").exists() and (tmp_path / "analysis/ast_rules.json").exists()
    (run / "code.py").write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        evaluate(run, tmp_path / "tampered")


def test_prepared_request_cannot_be_evaluated(tmp_path):
    run = tmp_path / "run"
    prepare(load_samples(SAMPLES)[0], run, "fixture-only")
    with pytest.raises(ValueError, match="successfully generated"):
        evaluate(run, tmp_path / "analysis")


def test_pipeline_combines_static_and_dynamic_results(tmp_path, monkeypatch):
    """Real static analyzers plus a synthetic Docker report; no host candidate import."""
    from security_eval.analyzers import dynamic

    def docker_fixture(args, timeout=15):
        if args[1:3] == ["image", "inspect"]:
            return 0, json.dumps([{"Id": "sha256:fixture"}]), ""
        if args[1] == "start":
            report = {
                "sample_id": "sql_delete_user", "exit_code": 1,
                "pytest_version": "synthetic-fixture", "collection_errors": [],
                "tests": [{"test_id": "synthetic-test", "category": "functional",
                           "outcome": "failed", "message": "synthetic failure"}],
            }
            return 1, dynamic.PREFIX + json.dumps(report), ""
        return 0, "", ""

    monkeypatch.setattr(dynamic, "command", docker_fixture)
    run = tmp_path / "run"
    generate(load_samples(SAMPLES)[0], run, "fixture-only",
             client=fixture_client("def remove_user(conn, username): return 0"))
    out = tmp_path / "analysis"
    results = evaluate(run, out)
    assert all(r["status"] == "completed" for r in results)
    assert len({r["code_sha256"] for r in results}) == 1
    assert len({r["run_id"] for r in results}) == 1
    assert results[2]["tests"][0]["outcome"] == "failed"
    for result in results:
        for evidence in result["evidence_files"]:
            assert (out / evidence).is_file()
