"""Shared JSON validation used by all three members."""

import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate(kind: str, record: dict) -> None:
    if kind not in {"sample", "generation", "analysis"}:
        raise ValueError(f"Unknown contract: {kind}")
    schema = json.loads(files("security_eval").joinpath(f"schemas/{kind}.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_samples(path: Path) -> list[dict]:
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    if not samples:
        raise ValueError("No samples found")
    for sample in samples:
        validate("sample", sample)
        if sample["sample_id"] in seen:
            raise ValueError("Duplicate sample_id")
        seen.add(sample["sample_id"])
    return samples
