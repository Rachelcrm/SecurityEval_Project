import argparse
import json
import os
import sys
from pathlib import Path

from jsonschema.exceptions import ValidationError

from .contracts import load_samples, validate
from .generation import generate, prepare
from .pipeline import evaluate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SecurityEval project (Python 3.11)")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("samples", help="Validate and list selected samples")
    listing.add_argument("--samples", type=Path, default=Path("data/samples.jsonl"))
    validation = commands.add_parser("validate", help="Validate one JSON contract")
    validation.add_argument("kind", choices=["sample", "generation", "analysis"])
    validation.add_argument("file", type=Path)
    evaluation = commands.add_parser("evaluate", help="Run available adapters; unfinished adapters report not_run")
    evaluation.add_argument("run_dir", type=Path)
    evaluation.add_argument("--out", type=Path, required=True)
    generation = commands.add_parser("generate", help="Generate one candidate or prepare a dry run")
    generation.add_argument("sample_id")
    generation.add_argument("--samples", type=Path, default=Path("data/samples.jsonl"))
    generation.add_argument("--model", default=os.environ.get("OPENAI_MODEL"))
    generation.add_argument("--out", required=True, type=Path, help="New directory; existing results are never overwritten")
    generation.add_argument("--dry-run", action="store_true")
    generation.add_argument("--temperature", type=float)
    generation.add_argument("--max-output-tokens", type=int, default=4096)
    generation.add_argument("--reasoning-effort", choices=["none", "minimal", "low", "medium", "high", "xhigh"])
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            validate(args.kind, json.loads(args.file.read_text(encoding="utf-8")))
            print("Valid " + args.kind + " contract")
        elif args.command == "samples":
            for sample in load_samples(args.samples):
                print(f'{sample["sample_id"]}\t{sample["cwe"]}\t{sample["signature"]}')
        elif args.command == "evaluate":
            results = evaluate(args.run_dir, args.out)
            print(json.dumps({r["tool"]: r["status"] for r in results}))
            return 0 if all(r["status"] == "completed" for r in results) else 1
        else:
            if not args.model:
                raise ValueError("Set --model or OPENAI_MODEL explicitly")
            samples = {s["sample_id"]: s for s in load_samples(args.samples)}
            if args.sample_id not in samples:
                raise ValueError("Unknown sample_id")
            operation = prepare if args.dry_run else generate
            record = operation(samples[args.sample_id], args.out, args.model,
                               temperature=args.temperature, max_output_tokens=args.max_output_tokens,
                               reasoning_effort=args.reasoning_effort)
            print(json.dumps({"status": record["status"], "record": str(args.out / "generation.json")}))
            return 1 if record["status"] == "error" else 0
        return 0
    except (ValueError, OSError, ValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
