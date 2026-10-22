# Member 3: isolated candidate execution

Build from the repository root (Docker Desktop/Engine must be running):

```bash
docker build -f docker/Dockerfile -t security-eval-tests:dev .
python scripts/verify_dynamic.py --out artifacts/dynamic-controls-001
```

The verification command executes seven **handwritten controls**, not model outputs:
SQL safe/unsafe/noop, command/path safe implementations, import failure, and an
infinite loop. It checks expected outcomes and container removal. Use a fresh output
path each time. Actual LLM generations are evaluated with the normal CLI:

```bash
security-eval evaluate artifacts/sql-live-001 --out artifacts/sql-analysis-001
```

`DockerPytestAnalyzer(evidence_dir=...)` enables execution; without an evidence
directory it explicitly returns `not_run`. The pipeline supplies that directory.
No Docker fallback executes candidates on the host. The pipeline runs Bandit, AST rules, and Docker testing. Infrastructure errors in
any adapter make the evaluate command return nonzero. Inspect each tool report;
`completed` does not imply that every test passed or that there are no findings.

The runner snapshots candidate bytes, verifies the hash, resolves the image to an
immutable local image ID, and never pulls an image during candidate execution. It
uses a non-root UID, read-only root/candidate mount, no network, dropped capabilities,
no-new-privileges, bounded tmpfs, CPU/memory/PID/descriptor limits and bounded Docker
logs. Only the candidate snapshot is mounted; no repo, credentials, or Docker socket.
A host deadline bounds `docker start -a`; `finally` forcibly removes the named
container and queries Docker to confirm its absence. Cleanup failure is an error.
Docker CLI calls also have deadlines and a 2 MiB capture limit (polled every 50 ms;
this is not an instantaneous disk quota). Do not use this harness for arbitrary
adversarial submissions; Docker isolation and in-process pytest are not containment
or tamper-proof guarantees.

The container entry point emits a JSON report after pytest finishes, before tmpfs is
lost. The host validates its structure and saves raw stdout/stderr, report JSON,
command logs, and environment metadata including image ID/digests, exit code,
cleanup result, and candidate hash. The report records Python/pytest versions and
hashes of baked-in Python tests. All report contents can potentially be influenced
by candidate execution; retain raw evidence and review observed violations.

A finished assertion-failure run is `completed`, not an infrastructure error.
Timeouts, unavailable Docker/image, missing/malformed/contradictory reports, empty
runs, collection errors, and setup/teardown errors are `error`. Skips remain skips.
Findings are not automatically inferred from failing tests. Passing checks is not
proof of security. Tests cover the three adapted contracts, not the entire original
SecurityEval benchmark. Command timeout internals and concurrent filesystem races
are not established by these behavioral tests. No fuzzing or repair is implemented.

The base tag is a development convenience. For published experiments pin `FROM`
to a reviewed digest, pin test dependencies, retain the built image, and archive
its identity plus all test/configuration/source files with the evidence.
