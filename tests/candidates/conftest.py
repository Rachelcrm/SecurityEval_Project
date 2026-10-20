"""Load candidates only inside the Docker test environment."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def remove_user():
    # Docker runner will mount the candidate at this fixed path.
    # Keep loading inside the fixture, not at module import time.
    candidate_path = Path("/candidate/code.py")
    if not candidate_path.is_file():
        pytest.fail("Candidate missing: run these tests through Docker")

    spec = importlib.util.spec_from_file_location(
        "candidate_under_test", candidate_path
    )
    if spec is None or spec.loader is None:
        pytest.fail("Could not load candidate")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    entry_point = getattr(module, "remove_user", None)
    if not callable(entry_point):
        pytest.fail("Candidate must define callable remove_user")

    return entry_point