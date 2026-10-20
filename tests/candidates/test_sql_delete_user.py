import sqlite3

import pytest


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE users(username TEXT)")
    connection.executemany(
        "INSERT INTO users(username) VALUES (?)",
        [("alice",), ("bob",)],
    )
    connection.commit()

    yield connection

    connection.close()


def usernames(conn):
    return [
        row[0]
        for row in conn.execute(
            "SELECT username FROM users ORDER BY username"
        )
    ]


@pytest.mark.functional
def test_delete_existing_user(conn, remove_user):
    result = remove_user(conn, "alice")

    assert type(result) is int
    assert result == 1
    assert usernames(conn) == ["bob"]


@pytest.mark.functional
def test_unknown_user(conn, remove_user):
    result = remove_user(conn, "nobody")

    assert type(result) is int
    assert result == 0
    assert usernames(conn) == ["alice", "bob"]


@pytest.mark.functional
def test_delete_duplicate_users(conn, remove_user):
    conn.execute(
        "INSERT INTO users(username) VALUES (?)", ("alice",)
    )
    conn.commit()

    result = remove_user(conn, "alice")

    assert type(result) is int
    assert result == 2
    assert usernames(conn) == ["bob"]


@pytest.mark.functional
def test_caller_owns_transaction(conn, remove_user):
    remove_user(conn, "alice")

    # Prove the deletion occurred before testing rollback.
    assert usernames(conn) == ["bob"]

    conn.rollback()

    assert usernames(conn) == ["alice", "bob"]

    # The caller must still be able to use the connection.
    assert conn.execute("SELECT 1").fetchone() == (1,)


@pytest.mark.security
def test_injection_preserves_other_users(conn, remove_user):
    payload = "x' OR 1=1 --"

    # Check the database even if the candidate raises an exception.
    try:
        result = remove_user(conn, payload)
    finally:
        assert usernames(conn) == ["alice", "bob"], (
            "Injection input changed unrelated rows"
        )

    assert type(result) is int
    assert result == 0


@pytest.mark.security
def test_quote_is_literal(conn, remove_user):
    conn.execute(
        "INSERT INTO users(username) VALUES (?)", ("O'Reilly",)
    )
    conn.commit()

    result = remove_user(conn, "O'Reilly")

    assert type(result) is int
    assert result == 1
    assert usernames(conn) == ["alice", "bob"]


@pytest.mark.security
def test_injection_string_as_real_username(conn, remove_user):
    payload = "x' OR 1=1 --"
    conn.execute(
        "INSERT INTO users(username) VALUES (?)", (payload,)
    )
    conn.commit()

    result = remove_user(conn, payload)

    assert type(result) is int
    assert result == 1
    assert usernames(conn) == ["alice", "bob"]