# Scaffold validation — 2026-10-19

These are actual local harness checks on macOS arm64, Python **3.11.17**.
They are not candidate functionality/security results and are not GitHub CI results.

| Check | Observed result |
|---|---|
| Install pinned requirements and editable package | Successful |
| `python -m pytest -q` | **23 passed in 1.03s** in the installed project |
| `python -m pip check` | No broken requirements found |
| `python scripts/verify_source.py --download` | 3 original prompts verified against pinned upstream data |
| `security-eval samples` | 3 validated sample records listed |
| Dry-run preparation for each of the 3 samples | `prepared`; no API call and no generated code |
| `git diff --check` | No whitespace errors |

The tests exercise contract rejection, duplicate sample handling, pending analyzer
states, code extraction, missing credentials, API failure, empty/invalid/incomplete
outputs, preservation of raw output, prevention of candidate execution, the real
OpenAI SDK with an explicitly mocked HTTP transport, and pipeline hash checks.
Synthetic fixture responses exist only in temporary test directories.

## Not run / not implemented

- No live model request: API credentials and final model choice are pending.
- No Bandit or custom AST scan of an LLM-generated candidate (none exists yet); see below
  for the rule-fixture validation.
- No candidate functional/security pytest or Docker execution: Member 3 integration is pending.
- No security score, vulnerability discovery, detector comparison, or repair claim.

Prepared local artifacts are ignored by Git. Repeatable commands and interfaces are
in the README and INTERFACES.md. Run the next real experiment in a fresh output
directory to preserve the original records.

## Static analysis (Member 2) — 2026-10-19

Python 3.11.17, Bandit 1.9.4, AST rule set 0.1.0. These are rule tests on hand-written
fixtures, not results on generated candidates.

| Check | Observed result |
|---|---|
| `python -m pytest -q` (harness + static tests) | **35 passed** |
| Rule fixtures: exact expected (rule, line) pairs | `AST-SQL-001`: 5 reported in unsafe, 0 in safe; `AST-CMD-001`: 6 in unsafe, 0 in safe |
| Mutants of the rule code (5 deliberate breakages) | Each made at least one static test fail |
| `security-eval static tests/fixtures/static does_not_exist.py` | Completed scans; syntax-error file and missing path reported as errors without stopping the batch (exit 1) |
| Contracts written by that run | All pass `security-eval validate analysis` |
| `python -m pip check` | No broken requirements found |
