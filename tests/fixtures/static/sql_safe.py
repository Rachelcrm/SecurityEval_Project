# HAND-WRITTEN RULE-TEST FIXTURE for AST-SQL-001 (not a SecurityEval sample or LLM output).
import sqlite3

TABLE = "users"


def remove_user(conn: sqlite3.Connection, username: str) -> int:
    cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
    return cur.rowcount


def remove_user_named(conn, username):
    query = "DELETE FROM users WHERE username = :name"
    return conn.cursor().execute(query, {"name": username}).rowcount


def count_rows(conn):
    # Built dynamically, but only from a module constant, not from input.
    return conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]


def remove_many(conn, usernames):
    conn.executemany("DELETE FROM users WHERE username = ?", [(u,) for u in usernames])
