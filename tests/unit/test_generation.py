"""Synthetic API fixtures validate the harness, never benchmark model performance."""
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from security_eval.cli import main
from security_eval.contracts import load_samples, validate
from security_eval.generation import extract_code, generate, prepare, run_batch


@pytest.fixture
def sample():
    return load_samples(Path(__file__).resolve().parents[2] / "data/samples.jsonl")[0]


class FixtureResponse:
    def __init__(self, text, status="completed"):
        self.output_text = text
        self.status = status

    def model_dump(self, **kwargs):
        return {"id": "unit-test-fixture", "model": "fixture-only", "status": self.status,
                "usage": None, "output": []}


def fixture_client(text, status="completed"):
    return SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: FixtureResponse(text, status)))


def test_dry_run_does_not_create_code_or_claim_generation(tmp_path, sample):
    out = tmp_path / "prepared"
    record = prepare(sample, out, "fixture-only")
    assert record["status"] == "prepared"
    assert not (out / "code.py").exists()
    assert "temperature" not in json.loads((out / "request.json").read_text())
    with pytest.raises(FileExistsError):
        prepare(sample, out, "fixture-only")


@pytest.mark.parametrize("text, expected", [("def f():\n    pass", "def f():\n    pass\n"),
                                            ("```python\ndef f():\n    pass\n```", "def f():\n    pass\n")])
def test_code_extraction(text, expected):
    assert extract_code(text) == expected


def test_generation_saves_but_never_executes_code(tmp_path, sample):
    marker = tmp_path / "must-not-exist"
    code = f"from pathlib import Path\nPath({str(marker)!r}).touch()\ndef remove_user(conn, username):\n    return 0\n"
    out = tmp_path / "fixture"
    record = generate(sample, out, "fixture-only", client=fixture_client(code))
    assert record["status"] == "generated"
    assert not marker.exists()
    assert (out / "code.py").read_text() == code
    assert (out / "completion.txt").read_text() == code
    validate("generation", record)


@pytest.mark.parametrize("text,status", [("", "completed"), ("def broken(:", "completed"),
                                        ("pass", "completed"), ("def remove_user(): pass", "incomplete")])
def test_bad_or_incomplete_output_is_an_error(tmp_path, sample, text, status):
    record = generate(sample, tmp_path / "fixture", "fixture-only", client=fixture_client(text, status))
    assert record["status"] == "error"
    assert record["error"] is not None


def test_api_error_does_not_persist_sensitive_exception_text(tmp_path, sample):
    def fail(**kwargs):
        raise RuntimeError("secret-key-must-not-leak")
    out = tmp_path / "fixture"
    record = generate(sample, out, "fixture-only", client=SimpleNamespace(responses=SimpleNamespace(create=fail)))
    assert record["status"] == "error"
    assert "secret-key" not in (out / "generation.json").read_text()


def test_missing_key_fails_without_network_or_artifacts(tmp_path, sample, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        generate(sample, tmp_path / "missing", "fixture-only")
    assert not (tmp_path / "missing").exists()


def test_real_sdk_serialization_with_mock_transport(tmp_path, sample):
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert payload["store"] is False
        assert payload["input"] == sample["adapted_prompt"]
        assert payload["max_output_tokens"] == 4096
        assert payload["reasoning"] == {"effort": "none"}
        return httpx.Response(200, json={
            "id": "unit-test-sdk-fixture", "object": "response", "created_at": 0,
            "status": "completed", "model": "fixture-only", "parallel_tool_calls": False,
            "tools": [], "tool_choice": "auto", "output": [{"id": "msg_fixture", "type": "message",
            "role": "assistant", "status": "completed", "content": [{"type": "output_text",
            "text": "def remove_user(conn, username):\n    return 0\n", "annotations": []}]}]})
    with OpenAI(api_key="unit-test-placeholder", base_url="https://api.openai.com/v1",
                max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        record = generate(sample, tmp_path / "fixture", "fixture-only", client=client, reasoning_effort="none")
    assert record["status"] == "generated"
    assert record["response_id"] == "unit-test-sdk-fixture"


def test_cli_dry_run_and_validation(tmp_path, sample):
    samples = tmp_path / "samples.jsonl"
    samples.write_text(json.dumps(sample) + "\n")
    out = tmp_path / "run"
    assert main(["generate", sample["sample_id"], "--samples", str(samples), "--model", "fixture-only",
                 "--out", str(out), "--dry-run"]) == 0
    assert main(["validate", "generation", str(out / "generation.json")]) == 0
    assert main(["generate", "unknown", "--samples", str(samples), "--model", "fixture-only",
                 "--out", str(tmp_path / "bad"), "--dry-run"]) == 2


def test_batch_dry_run_prepares_every_sample_without_code(tmp_path):
    samples = load_samples(Path(__file__).resolve().parents[2] / "data/samples.jsonl")
    out = tmp_path / "batch"
    manifest = run_batch(samples, out, "fixture-only", dry_run=True, reasoning_effort="none")
    assert manifest["status"] == "complete"
    assert [item["sample_id"] for item in manifest["results"]] == [
        "sql_delete_user", "command_allowlist", "path_read_file"
    ]
    assert all(item["status"] == "prepared" and item["code"] is None for item in manifest["results"])
    assert not list(out.rglob("code.py"))
    assert json.loads((out / "manifest.json").read_text())["dry_run"] is True


def test_batch_generation_records_one_candidate_per_sample(tmp_path):
    samples = load_samples(Path(__file__).resolve().parents[2] / "data/samples.jsonl")
    code_by_entry = {
        "remove_user": "def remove_user(conn, username):\n    return 0\n",
        "execute_command": "def execute_command(command):\n    return ''\n",
        "read_file": "def read_file(base_dir, filename):\n    return b''\n",
    }

    def create(**request):
        code = next(code for entry, code in code_by_entry.items() if entry in request["input"])
        return FixtureResponse(code)

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    out = tmp_path / "batch"
    manifest = run_batch(samples, out, "fixture-only", client=client, reasoning_effort="none")
    assert manifest["status"] == "complete"
    assert all(item["status"] == "generated" and item["code"] for item in manifest["results"])
    for sample in samples:
        assert (out / sample["sample_id"] / "code.py").exists()


def test_batch_missing_key_fails_before_creating_output(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    samples = load_samples(Path(__file__).resolve().parents[2] / "data/samples.jsonl")
    out = tmp_path / "batch"
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        run_batch(samples, out, "fixture-only")
    assert not out.exists()


def test_cli_batch_dry_run(tmp_path):
    samples = Path(__file__).resolve().parents[2] / "data/samples.jsonl"
    out = tmp_path / "batch"
    assert main(["generate-batch", "--samples", str(samples), "--model", "fixture-only",
                 "--out", str(out), "--reasoning-effort", "none", "--dry-run"]) == 0
    assert json.loads((out / "manifest.json").read_text())["status"] == "complete"
