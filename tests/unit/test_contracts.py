import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from security_eval.contracts import load_samples, validate
from security_eval.analyzers.dynamic import DockerPytestAnalyzer

SAMPLES = Path(__file__).resolve().parents[2] / "data/samples.jsonl"


def test_selected_samples_have_stable_original_prompt_hashes():
    samples = load_samples(SAMPLES)
    assert len(samples) == 3
    assert {s["cwe"] for s in samples} == {"CWE-022", "CWE-078", "CWE-089"}
    for sample in samples:
        assert hashlib.sha256(sample["original_prompt"].encode()).hexdigest() == sample["source"]["prompt_sha256"]
        assert sample["original_prompt"] != sample["adapted_prompt"]


@pytest.mark.parametrize("mutation", ["missing", "unknown", "invalid_id"])
def test_invalid_sample_contracts_are_rejected(mutation):
    sample = copy.deepcopy(load_samples(SAMPLES)[0])
    if mutation == "missing":
        del sample["original_prompt"]
    elif mutation == "unknown":
        sample["made_up_result"] = "passed"
    else:
        sample["sample_id"] = "../../escape"
    with pytest.raises(ValidationError):
        validate("sample", sample)


def test_duplicate_samples_are_rejected(tmp_path):
    sample = load_samples(SAMPLES)[0]
    path = tmp_path / "duplicate.jsonl"
    path.write_text((json.dumps(sample) + "\n") * 2)
    with pytest.raises(ValueError, match="Duplicate"):
        load_samples(path)


@pytest.mark.parametrize("analyzer", [DockerPytestAnalyzer()])
def test_unimplemented_analyzers_cannot_claim_success(analyzer, tmp_path):
    code = tmp_path / "fixture.py"
    code.write_text("raise RuntimeError('must never execute')\n")
    record = analyzer.analyze(code, load_samples(SAMPLES)[0], "unit-test-only")
    assert record["status"] == "not_run"
    assert record["findings"] == record["tests"] == []
    assert record["code_sha256"] == hashlib.sha256(code.read_bytes()).hexdigest()
    record["status"] = "completed"
    with pytest.raises(ValidationError):
        validate("analysis", record)


def test_not_run_cannot_contain_test_results(tmp_path):
    code = tmp_path / "fixture.py"
    code.write_text("pass\n")
    record = DockerPytestAnalyzer().analyze(code, load_samples(SAMPLES)[0], "unit-test-only")
    record["tests"] = [{"test_id": "fake", "category": "security", "outcome": "passed", "message": ""}]
    with pytest.raises(ValidationError):
        validate("analysis", record)
