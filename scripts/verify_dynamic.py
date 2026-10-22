"""Real Docker checks using hand-written controls, never benchmark/model results."""
import argparse
import json
from collections import Counter
from pathlib import Path

from security_eval.analyzers.dynamic import DockerPytestAnalyzer
from security_eval.contracts import load_samples, write_json

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("sql_safe", "sql_delete_user", {"passed": 7}, 30),
    ("sql_unsafe", "sql_delete_user", {"passed": 4, "failed": 3}, 30),
    ("sql_noop", "sql_delete_user", {"passed": 2, "failed": 5}, 30),
    ("command_safe", "command_allowlist", {"passed": 18}, 30),
    ("path_safe", "path_read_file", {"passed": 9}, 30),
    ("import_error", "sql_delete_user", None, 30),
    ("hangs", "sql_delete_user", None, 3),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", default="security-eval-tests:dev")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    samples = {s["sample_id"]: s for s in load_samples(ROOT / "data/samples.jsonl")}
    failed = False
    for fixture, sample_id, expected, timeout in CASES:
        analyzer = DockerPytestAnalyzer(args.out / fixture, image=args.image, timeout=timeout)
        result = analyzer.analyze(ROOT / f"tests/fixtures/dynamic/{fixture}.py", samples[sample_id], "handwritten-control:" + fixture)
        write_json(args.out / (fixture + ".json"), result)
        outcomes = dict(Counter(t["outcome"] for t in result["tests"]))
        environment = json.loads((args.out / fixture / "environment.json").read_text())
        ok = environment["cleanup_confirmed"] and (
            (result["status"] == "completed" and outcomes == expected) if expected is not None
            else result["status"] == "error" and (
                "Timeout" in str(result["error"]) if fixture == "hangs"
                else "setup or teardown" in str(result["error"])
            )
        )
        print(f"{fixture}: {'OK' if ok else 'FAIL'} {result['status']} {outcomes} {result['error']}", flush=True)
        failed |= not ok
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
