"""All SQL lives here; callers get plain rows back."""

import sqlite3


def add_repo(conn: sqlite3.Connection, name: str, path: str) -> None:
    with conn:
        conn.execute("INSERT INTO repos (name, path) VALUES (?, ?)", (name, path))


def get_repo(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM repos WHERE name = ?", (name,)).fetchone()


def clear_repo(conn: sqlite3.Connection, repo_id: int) -> None:
    """Remove every indexed file of a repo (symbols cascade)."""
    conn.execute("DELETE FROM files WHERE repo_id = ?", (repo_id,))


def insert_file(conn: sqlite3.Connection, repo_id: int, path: str, language: str | None) -> int:
    return conn.execute(
        "INSERT INTO files (repo_id, path, language) VALUES (?, ?, ?)", (repo_id, path, language)
    ).lastrowid


def insert_symbols(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """rows: (repo_id, file_id, path, language, name, kind, start_line, end_line, commit_sha, code,
              search_text, embedding)"""
    conn.executemany(
        """INSERT INTO symbols (repo_id, file_id, path, language, name, kind,
                                start_line, end_line, commit_sha, code, search_text, embedding)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )


def _repo_filter(repos: list[str] | None) -> tuple[str, list]:
    if not repos:
        return "", []
    return f" AND r.name IN ({','.join('?' * len(repos))})", list(repos)


def embeddings(conn: sqlite3.Connection, repos: list[str] | None) -> tuple[list[int], list[bytes]]:
    where, args = _repo_filter(repos)
    rows = conn.execute(
        "SELECT s.id, s.embedding FROM symbols s JOIN repos r ON r.id = s.repo_id"
        f" WHERE s.embedding IS NOT NULL{where}",
        args,
    ).fetchall()
    return [r[0] for r in rows], [r[1] for r in rows]


def symbols_by_id(conn: sqlite3.Connection, ids: list[int]) -> dict[int, sqlite3.Row]:
    rows = conn.execute(
        f"""SELECT s.id, r.name AS repo, s.path, s.name, s.kind, s.language,
                   s.start_line, s.end_line, s.code
            FROM symbols s JOIN repos r ON r.id = s.repo_id
            WHERE s.id IN ({','.join('?' * len(ids))})""",
        ids,
    ).fetchall() if ids else []
    return {r["id"]: r for r in rows}


def set_indexed(conn: sqlite3.Connection, repo_id: int, sha: str) -> None:
    conn.execute(
        "UPDATE repos SET last_sha = ?, indexed_at = datetime('now') WHERE id = ?", (sha, repo_id)
    )


def list_symbols(conn: sqlite3.Connection, repo: str | None, kind: str | None, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT r.name AS repo, s.path, s.name, s.kind, s.language, s.start_line, s.end_line
           FROM symbols s JOIN repos r ON r.id = s.repo_id
           WHERE (:repo IS NULL OR r.name = :repo) AND (:kind IS NULL OR s.kind = :kind)
             AND s.kind != 'wiki'
           ORDER BY s.kind = 'window', s.path, s.start_line LIMIT :limit""",  # real symbols before windows
        {"repo": repo, "kind": kind, "limit": limit},
    ).fetchall()


def stats_by_language(conn: sqlite3.Connection, repo: str | None) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT r.name AS repo, COALESCE(s.language, '-') AS language,
                  SUM(s.kind != 'window') AS symbols, SUM(s.kind = 'window') AS windows,
                  COUNT(DISTINCT s.file_id) AS files
           FROM symbols s JOIN repos r ON r.id = s.repo_id
           WHERE (:repo IS NULL OR r.name = :repo) AND s.kind != 'wiki'
           GROUP BY r.name, s.language ORDER BY r.name, COUNT(*) DESC""",
        {"repo": repo},
    ).fetchall()


def list_repos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT r.name, r.path, r.last_sha, r.indexed_at,
               (SELECT COUNT(*) FROM files f WHERE f.repo_id = r.id) AS files,
               (SELECT COUNT(*) FROM symbols s WHERE s.repo_id = r.id AND s.kind != 'wiki') AS symbols
        FROM repos r ORDER BY r.name
        """
    ).fetchall()
