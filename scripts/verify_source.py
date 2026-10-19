"""Verify selected prompts against the pinned upstream file; never execute dataset code."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from security_eval.contracts import load_samples


def verify(samples_path: Path, source_path: Path) -> int:
    samples = load_samples(samples_path)
    raw = source_path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    rows = {}
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row["ID"] in rows:
                raise ValueError("Duplicate upstream ID")
            rows[row["ID"]] = row
    for sample in samples:
        source = sample["source"]
        if source_hash != source["dataset_sha256"]:
            raise ValueError("Dataset hash mismatch")
        original = rows[source["record_id"]]["Prompt"]
        if original != sample["original_prompt"]:
            raise ValueError("Original prompt mismatch: " + sample["sample_id"])
        if hashlib.sha256(original.encode()).hexdigest() != source["prompt_sha256"]:
            raise ValueError("Prompt hash mismatch")
    return len(samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=Path("data/samples.jsonl"))
    parser.add_argument("--source", type=Path, default=Path("data/raw/dataset.jsonl"))
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        sources = {s["source"]["revision"] for s in load_samples(args.samples)}
        if len(sources) != 1:
            raise ValueError("Expected one pinned revision")
        revision = sources.pop()
        url = f"https://raw.githubusercontent.com/s2e-lab/SecurityEval/{revision}/dataset.jsonl"
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read()
        expected = {s["source"]["dataset_sha256"] for s in load_samples(args.samples)}
        if expected != {hashlib.sha256(raw).hexdigest()}:
            raise ValueError("Downloaded dataset hash mismatch; nothing written")
        args.source.parent.mkdir(parents=True, exist_ok=True)
        args.source.write_bytes(raw)
    print(f"Verified {verify(args.samples, args.source)} original prompts against pinned upstream data")


if __name__ == "__main__":
    main()
