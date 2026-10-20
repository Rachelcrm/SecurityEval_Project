import json

import pytest

from security_eval.contracts import load_samples
from security_eval.generation import generate, prepare
from security_eval.pipeline import evaluate
from test_generation import fixture_client
from test_contracts import SAMPLES


def test_pipeline_runs_static_analyzers_and_detects_tampering(tmp_path):
    sample = load_samples(SAMPLES)[0]
    run = tmp_path / "run"
    generate(sample, run, "fixture-only", client=fixture_client("def remove_user(conn, username): return 0"))
    results = evaluate(run, tmp_path / "analysis")
    assert len(results) == 3
    assert {r["tool"]: r["status"] for r in results} == {
        "bandit": "completed", "ast": "completed", "pytest-docker": "not_run"}
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
