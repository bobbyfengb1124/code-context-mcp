"""All SQL lives here; callers get plain rows back."""

import sqlite3


def add_repo(conn: sqlite3.Connection, name: str, path: str) -> None:
    with conn:
        conn.execute("INSERT INTO repos (name, path) VALUES (?, ?)", (name, path))


def get_repo(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM repos WHERE name = ?", (name,)).fetchone()


def list_repos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT r.name, r.path, r.last_sha, r.indexed_at,
               (SELECT COUNT(*) FROM files f WHERE f.repo_id = r.id) AS files,
               (SELECT COUNT(*) FROM symbols s WHERE s.repo_id = r.id AND s.kind != 'wiki') AS symbols
        FROM repos r ORDER BY r.name
        """
    ).fetchall()
