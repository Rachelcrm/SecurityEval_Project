def remove_user(conn, username):
    cursor = conn.execute(
        "DELETE FROM users WHERE username = ?",
        (username,),
    )
    return cursor.rowcount