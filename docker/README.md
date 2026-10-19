# Member 3: isolated execution handoff

The Docker runner is intentionally **not implemented**. DockerPytestAnalyzer returns
status=not_run. No sandbox or candidate test result is claimed by this scaffold.

Implement a Python 3.11 image with pinned test dependencies, a non-root UID, and
read-only candidate/test mounts. At runtime use --network none, --read-only,
--cap-drop ALL, --security-opt no-new-privileges, --pids-limit, --memory, --cpus,
and a bounded writable /tmp tmpfs. Do not mount the Docker socket, home directory,
API keys, or the whole repository. Add a host-side wall-clock deadline that kills
and removes a timed-out container; a subprocess timeout alone is insufficient.

Pin the image digest for recorded experiments. Capture image identity, pytest
version, actual command, exit code, stdout/stderr and test evidence. Translate
timeouts, unavailable Docker, import errors and pytest collection errors into
status=error. A completed test run may contain failed tests; use the tests array
to preserve the distinction. Docker isolation reduces exposure but is not a proof
of containment; use only this small, controlled local dataset for the initial demo.
