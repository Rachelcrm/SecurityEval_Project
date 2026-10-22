# HAND-WRITTEN RULE-TEST FIXTURE for AST-CMD-001 (not a SecurityEval sample or LLM output).
import subprocess


def print_working_directory() -> str:
    return subprocess.run(["pwd"], capture_output=True, text=True, timeout=2).stdout


def echo_words(command: str) -> str:
    # Program name is a constant; only arguments come from input (argument injection is
    # outside this rule's scope) and no shell is used.
    words = command.split()[1:]
    return subprocess.run(["echo", *words], capture_output=True, text=True, timeout=2).stdout


def constant_shell() -> str:
    return subprocess.check_output("pwd", shell=True, text=True)


def explicit_no_shell(command: str) -> str:
    return subprocess.run(["echo", command], shell=False, capture_output=True, text=True).stdout
