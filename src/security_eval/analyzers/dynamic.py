"""Member 3 owns Docker execution and functional/security pytest mapping here."""
from pathlib import Path
from .base import pending


class DockerPytestAnalyzer:
    def analyze(self, code_path: Path, sample: dict, run_id: str) -> dict:
        return pending(code_path, sample, run_id, "pytest-docker")
