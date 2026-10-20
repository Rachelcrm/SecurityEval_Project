# HAND-WRITTEN RULE-TEST FIXTURE for AST-CMD-001 (not a SecurityEval sample or LLM output).
import os
import shlex
import subprocess
import subprocess as sp
from subprocess import check_output


def execute_command_shell(command: str) -> str:
    return subprocess.run(command, shell=True, capture_output=True, text=True, timeout=2).stdout  # expect: AST-CMD-001


def execute_command_os_system(command):
    os.system("echo " + command)  # expect: AST-CMD-001


def execute_command_split(command):
    parts = shlex.split(command)
    return check_output(parts, timeout=2).decode()  # expect: AST-CMD-001


def execute_command_alias_popen(command):
    proc = sp.Popen(command.split(), stdout=sp.PIPE)  # expect: AST-CMD-001
    return proc.communicate()[0].decode()


def execute_command_os_popen(command):
    return os.popen(command).read()  # expect: AST-CMD-001


def execute_command_list_head(command):
    program = command.split()[0]
    return subprocess.run([program, "--version"], capture_output=True, timeout=2).stdout  # expect: AST-CMD-001
