"""Member 2 owns Bandit parsing and custom AST rules here."""
from pathlib import Path
from .base import pending


class BanditAnalyzer:
    def analyze(self, code_path: Path, sample: dict, run_id: str) -> dict:
        return pending(code_path, sample, run_id, "bandit")


class ASTAnalyzer:
    def analyze(self, code_path: Path, sample: dict, run_id: str) -> dict:
        return pending(code_path, sample, run_id, "ast")
