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
- No Bandit or custom AST scan: Member 2 adapters are placeholders returning `not_run`.
- No candidate functional/security pytest or Docker execution: Member 3 integration is pending.
- No security score, vulnerability discovery, detector comparison, or repair claim.

Prepared local artifacts are ignored by Git. Repeatable commands and interfaces are
in the README and INTERFACES.md. Run the next real experiment in a fresh output
directory to preserve the original records.

## Member 3 dynamic execution — 2026-10-21

- Offline harness: **31 passed**; `git diff --check` clean.
- Seven real Docker handwritten-control checks completed with expected outcomes:
  SQL safe 7 passed; SQL unsafe 3 failed/4 passed; SQL noop 5 failed/2 passed;
  command safe 18 passed; path safe 9 passed; import failure recorded as error;
  infinite loop recorded as timeout error with a three-second execution deadline.
- Container removal was confirmed by querying Docker for every control, including
  timeout and import failure. Results are local validation, not model/benchmark scores.
- Evidence: local ignored `artifacts/member3-validation-20261021/`; each case has
  normalized analysis JSON, environment/commands, logs, and report when available.
- Full Dockerfile rebuild waited on remote Python base-image metadata and was canceled.
  Real checks used `security-eval-tests:validation`, derived from the existing local
  `security-eval-tests:dev` image with the new runner and current tests copied in.
  Exact built image identity is retained in each environment record. A clean online
  Dockerfile build remains to be verified; no clean-build success is claimed.
- Static analysis and automatic repair remain unimplemented. No live LLM evaluation
  was performed during this Member 3 validation.
