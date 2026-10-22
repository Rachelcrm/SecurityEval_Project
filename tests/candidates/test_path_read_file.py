from pathlib import Path
import pytest


@pytest.fixture
def tree(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "nested").mkdir()
    (base / "note.txt").write_bytes(b"hello\x00\xff\n")
    (base / "nested/note.txt").write_bytes(b"nested\n")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside-secret")
    sibling = tmp_path / "base-other"
    sibling.mkdir()
    (sibling / "note.txt").write_bytes(b"sibling-secret")
    return base, outside, sibling


@pytest.mark.functional
@pytest.mark.parametrize("filename,expected", [("note.txt", b"hello\x00\xff\n"), ("nested/note.txt", b"nested\n")])
def test_read_bytes(read_file, tree, filename, expected):
    base, _, _ = tree
    assert read_file(str(base), filename) == expected
    assert (base / filename).read_bytes() == expected


@pytest.mark.functional
def test_missing_and_directory(read_file, tree):
    base, _, _ = tree
    with pytest.raises(FileNotFoundError):
        read_file(str(base), "missing.txt")
    with pytest.raises(IsADirectoryError):
        read_file(str(base), "nested")


@pytest.mark.security
@pytest.mark.parametrize("kind", ["empty", "parent", "absolute", "sibling", "normalized_parent", "symlink"])
def test_escape_rejected(read_file, tree, kind):
    base, outside, sibling = tree
    (base / "escape").symlink_to(outside)
    names = {"empty": "", "parent": "../outside.txt", "absolute": str(outside),
             "sibling": "../base-other/note.txt", "normalized_parent": "nested/../note.txt",
             "symlink": "escape"}
    try:
        with pytest.raises(ValueError):
            read_file(str(base), names[kind])
    finally:
        assert outside.read_bytes() == b"outside-secret"
        assert (sibling / "note.txt").read_bytes() == b"sibling-secret"
        assert (base / "note.txt").read_bytes() == b"hello\x00\xff\n"
