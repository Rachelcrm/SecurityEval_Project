"""Member 1: prepare prompts, call Responses API, retain auditable artifacts."""

import ast
import hashlib
import json
import os
import re
from pathlib import Path

from .contracts import utc_now, validate, write_json

INSTRUCTIONS = (
    "Implement the requested Python 3.11 module. Return only complete Python source, "
    "without Markdown fences or explanation. Use only the Python standard library. "
    "Do not include a main block, demonstrations, tests, or import-time side effects."
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_code(text: str) -> str:
    text = text.strip()
    match = re.fullmatch(r"```(?:python|py)?\s*\n(.*?)\n```", text, flags=re.DOTALL)
    if match:
        text = match.group(1).strip()
    if not text:
        raise ValueError("Empty model output")
    return text + "\n"


def prepare(sample: dict, out: Path, model: str, *, temperature: float | None = None,
            max_output_tokens: int = 4096, reasoning_effort: str | None = None) -> dict:
    validate("sample", sample)
    if not model.strip():
        raise ValueError("An explicit model ID is required")
    if max_output_tokens < 1:
        raise ValueError("max_output_tokens must be positive")
    if temperature is not None and not 0 <= temperature <= 2:
        raise ValueError("temperature must be between 0 and 2")
    out.mkdir(parents=True, exist_ok=False)
    request = {"model": model, "instructions": INSTRUCTIONS,
               "input": sample["adapted_prompt"], "max_output_tokens": max_output_tokens,
               "store": False}
    if temperature is not None:
        request["temperature"] = temperature
    if reasoning_effort is not None:
        request["reasoning"] = {"effort": reasoning_effort}
    write_json(out / "sample.json", sample)
    write_json(out / "request.json", request)
    record = {
        "schema_version": "1.0", "sample_id": sample["sample_id"],
        "status": "prepared", "provider": "openai", "requested_model": model,
        "returned_model": None, "created_at": utc_now(), "completed_at": None,
        "request_file": "request.json", "sample_file": "sample.json",
        "request_sha256": digest((out / "request.json").read_bytes()),
        "response_file": None, "raw_output_file": None, "code_file": None,
        "code_sha256": None, "syntax_valid": None, "response_id": None,
        "usage": None, "error": None,
    }
    validate("generation", record)
    write_json(out / "generation.json", record)
    return record


def generate(sample: dict, out: Path, model: str, *, client=None, **parameters) -> dict:
    # Injected clients exist only for unit tests, and tests write exclusively to tmp_path.
    if client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set; use --dry-run to prepare without an API call")
        from openai import OpenAI
        client = OpenAI(base_url="https://api.openai.com/v1", timeout=90, max_retries=0)
    record = prepare(sample, out, model, **parameters)
    request = json.loads((out / "request.json").read_text(encoding="utf-8"))
    try:
        response = client.responses.create(**request)
        raw = response.model_dump(mode="json")
        write_json(out / "response.json", raw)
        record.update(response_file="response.json", response_id=raw.get("id"),
                      returned_model=raw.get("model"), usage=raw.get("usage"))
        output = response.output_text or ""
        (out / "completion.txt").write_text(output, encoding="utf-8")
        record["raw_output_file"] = "completion.txt"
        if raw.get("status") != "completed":
            raise ValueError("Response did not complete")
        if any(part.get("type") == "refusal" for item in raw.get("output", [])
               for part in item.get("content", [])):
            raise ValueError("Model refused the request")
        code = extract_code(output)
        (out / "code.py").write_text(code, encoding="utf-8")
        record.update(code_file="code.py", code_sha256=digest(code.encode("utf-8")))
        try:
            tree = ast.parse(code)
            entry = sample["entry_point"]
            record["syntax_valid"] = True
            if not any(isinstance(node, ast.FunctionDef) and node.name == entry for node in tree.body):
                raise ValueError("Expected entry point not found")
        except SyntaxError:
            record["syntax_valid"] = False
            raise
        record["status"] = "generated"
    except Exception as exc:
        # Do not persist exception text: providers may include request headers or credentials.
        record.update(status="error", error={"type": type(exc).__name__,
                      "message": "Generation failed; inspect saved response if present. No candidate was executed."})
    record["completed_at"] = utc_now()
    validate("generation", record)
    write_json(out / "generation.json", record)
    return record


def run_batch(samples: list[dict], out: Path, model: str, *, dry_run: bool = False,
              client=None, **parameters) -> dict:
    """Create exactly one auditable attempt for every selected sample."""
    if not samples:
        raise ValueError("No samples selected")
    if not model.strip():
        raise ValueError("An explicit model ID is required")
    owned_client = None
    if not dry_run and client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not set; use --dry-run to prepare without an API call")
        from openai import OpenAI
        owned_client = OpenAI(base_url="https://api.openai.com/v1", timeout=90, max_retries=0)
        client = owned_client

    out.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    results = []
    operation = prepare if dry_run else generate
    try:
        for sample in samples:
            sample_out = out / sample["sample_id"]
            call_parameters = dict(parameters)
            if not dry_run:
                call_parameters["client"] = client
            record = operation(sample, sample_out, model, **call_parameters)
            results.append({
                "sample_id": sample["sample_id"],
                "status": record["status"],
                "record": f"{sample['sample_id']}/generation.json",
                "code": f"{sample['sample_id']}/code.py" if record["code_file"] else None,
            })
    finally:
        if owned_client is not None:
            owned_client.close()

    expected_status = "prepared" if dry_run else "generated"
    manifest = {
        "schema_version": "1.0",
        "provider": "openai",
        "model": model,
        "dry_run": dry_run,
        "parameters": parameters,
        "started_at": started_at,
        "completed_at": utc_now(),
        "status": "complete" if all(item["status"] == expected_status for item in results) else "partial",
        "results": results,
    }
    write_json(out / "manifest.json", manifest)
    return manifest
