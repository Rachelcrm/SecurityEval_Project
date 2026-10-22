# HAND-WRITTEN RULE-TEST FIXTURE for AST-SQL-001 (not a SecurityEval sample or LLM output).
import sqlite3


def remove_user_fstring(conn: sqlite3.Connection, username: str) -> int:
    cur = conn.execute(f"DELETE FROM users WHERE username = '{username}'")  # expect: AST-SQL-001
    return cur.rowcount


def remove_user_concat_variable(conn, username):
    query = "DELETE FROM users WHERE username = '" + username + "'"
    cursor = conn.cursor()
    cursor.execute(query)  # expect: AST-SQL-001
    return cursor.rowcount


def remove_user_percent_two_hops(conn, username):
    condition = "username = '%s'" % username
    sql = "DELETE FROM users WHERE " + condition
    return conn.execute(sql).rowcount  # expect: AST-SQL-001


def remove_user_format_script(conn, username):
    conn.executescript("DELETE FROM users WHERE username = '{}';".format(username))  # expect: AST-SQL-001


def remove_from_prompt(conn):
    name = input("user: ")
    conn.execute("DELETE FROM users WHERE username = '%s'" % name)  # expect: AST-SQL-001
