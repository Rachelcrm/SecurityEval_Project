# Member 1 Handoff

## Scope and status

Member 1 owns sample selection, prompt adaptation, code generation, and generation
records. The framework, three sample contracts, source verification, and batch-generation
command are complete. Live generation remains pending until a local OpenAI API key is
available. No live output or security result is claimed before that run finishes.

## Fixed first-run configuration

| Setting | Value |
|---|---|
| Provider | OpenAI Responses API |
| Model | `gpt-5.4-mini-2026-03-17` |
| Reasoning effort | `none` |
| Maximum output tokens | `4096` |
| Temperature | Omitted |
| Storage | `false` |
| Retry policy | No automatic retries |
| Attempts | One initial attempt per sample |

The snapshot model keeps the first comparison reproducible. All three samples must use
the same settings. Preserve failed, refused, incomplete, or syntactically invalid outputs
as recorded errors; do not silently regenerate or select a more favorable candidate.

## Selected sample contracts

| Sample ID | Required entry point | Primary test focus |
|---|---|---|
| `sql_delete_user` | `remove_user(conn, username) -> int` | Exact deletion, quoted usernames, SQL injection input, caller-owned transaction |
| `command_allowlist` | `execute_command(command) -> str` | `pwd` and `echo`, unsupported commands, shell metacharacters, command substitution |
| `path_read_file` | `read_file(base_dir, filename) -> bytes` | In-base files, missing files, traversal, absolute paths, escaping symlinks |

The complete requirements and the original/adapted prompt distinction are in
`data/samples.jsonl`. Changes to signatures or expected behavior must be agreed on before
Member 2 or Member 3 writes analysis logic or candidate tests.

## Live generation

From the repository root, activate the Python 3.11 environment, enter the key locally,
and run one batch. The key must never be pasted into chat, written to a file, or committed.

```bash
source .venv/bin/activate
read -s "OPENAI_API_KEY?OpenAI API key: "
export OPENAI_API_KEY
printf '\n'
security-eval generate-batch \
  --model gpt-5.4-mini-2026-03-17 \
  --reasoning-effort none \
  --max-output-tokens 4096 \
  --out artifacts/member1-live-001
unset OPENAI_API_KEY
```

Success requires `manifest.json` to report `complete` and all three records to report
`generated`. A `generated` record proves only that the response completed, parsed as
Python, and contained the expected top-level function. It does not prove functional
correctness or security.

## Review and teammate delivery

Before sharing any artifact:

1. Confirm that `request.json` contains no credential and matches the fixed settings.
2. Confirm that each `response.json`, `completion.txt`, `code.py`, and `generation.json`
   exists and that the recorded code hash matches the candidate bytes.
3. Read the candidates without importing or executing them on the host.
4. Copy the reviewed batch into a tracked experiment directory or share it through the
   agreed team channel. The default `artifacts/` directory is intentionally Git-ignored.
5. Tell Members 2 and 3 to use the exact same `code.py` files and verify their hashes.

Start the integrated demo with `sql_delete_user`. Member 2 should run Bandit and the
custom AST rules. Member 3 should run functional and security tests only in the restricted
Docker environment. The team should report actual outcomes, including failures and tool
errors, without treating an empty finding list as proof of security.
