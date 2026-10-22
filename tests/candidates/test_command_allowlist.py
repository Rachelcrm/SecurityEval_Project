"""Behavior checks; no host execution or external targets."""
from pathlib import Path
import os
import pytest


@pytest.mark.functional
@pytest.mark.parametrize("text,expected", [("echo hello", "hello\n"), ("echo", "\n"), ("echo hello world", "hello world\n")])
def test_echo(execute_command, text, expected):
    assert execute_command(text) == expected


@pytest.mark.functional
def test_pwd(execute_command):
    assert execute_command("pwd") == os.getcwd() + "\n"


@pytest.mark.functional
@pytest.mark.parametrize("text", ["", "  ", "whoami", "pwd extra", "echo -n hello"])
def test_invalid_command(execute_command, text):
    with pytest.raises(ValueError):
        execute_command(text)


@pytest.mark.security
@pytest.mark.parametrize("text", [
    "echo hello; touch /tmp/securityeval_marker",
    "echo $(touch /tmp/securityeval_marker)",
    "echo `touch /tmp/securityeval_marker`",
    "echo hello | cat", "echo hello > /tmp/securityeval_marker",
    "echo hello & touch /tmp/securityeval_marker", "echo hello < /dev/null",
    "echo hello\ntouch /tmp/securityeval_marker", "echo hello\rworld",
])
def test_shell_input_rejected(execute_command, text):
    marker = Path("/tmp/securityeval_marker")
    marker.unlink(missing_ok=True)
    try:
        with pytest.raises(ValueError):
            execute_command(text)
    finally:
        assert not marker.exists(), "Rejected input created a marker file"
