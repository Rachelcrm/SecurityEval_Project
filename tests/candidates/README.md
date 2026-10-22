# Candidate functional/security tests

These tests execute untrusted candidate Python only in the Docker runner. Default
root pytest still runs `tests/unit` only. Never run this directory on the host.

- SQL: exact deletion, missing/duplicate users, transaction ownership, literal quotes,
  injection noninterference, and a real username containing injection syntax (7 tests).
- Commands: echo/pwd, invalid commands/options, shell delimiters/substitution and
  marker-file side effects (18 parametrized tests).
- Paths: exact bytes, nested paths, missing/directory errors, parent/absolute/sibling
  paths and escaping symlinks, with basic file preservation checks (9 tests).

Each test has exactly one functional/security marker. Import/setup/teardown errors
are execution errors. Ordinary candidate exceptions during a test are test failures;
review the traceback instead of claiming every failure is a vulnerability.

Handwritten controls live in `tests/fixtures/dynamic`; `scripts/verify_dynamic.py`
checks them using real Docker, including import failure and timeout cleanup. These
controls are not LLM samples or benchmark scores. See `docker/README.md` for commands,
evidence layout, resource limits, and trust limitations.
