def remove_user(conn, username):
    cursor = conn.execute(
        f"DELETE FROM users WHERE username = '{username}'"
    )
    return cursor.rowcount