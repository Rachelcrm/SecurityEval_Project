"""Handwritten reference fixture; static filesystem only."""
from pathlib import Path


def read_file(base_dir, filename):
    relative = Path(filename)
    if not filename or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invalid path")
    base = Path(base_dir).resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base):
        raise ValueError("outside base")
    return target.read_bytes()
