"""SQLite connection and schema migrations.

Each step that needs new tables/columns appends one script to MIGRATIONS;
PRAGMA user_version records how many have been applied.
"""

import os
import sqlite3
from pathlib import Path

MIGRATIONS = [
    # 1: repositories, files, symbols
    """
    CREATE TABLE repos (
        id         INTEGER PRIMARY KEY,
        name       TEXT NOT NULL UNIQUE,
        path       TEXT NOT NULL,
        last_sha   TEXT,
        indexed_at TEXT
    );
    CREATE TABLE files (
        id       INTEGER PRIMARY KEY,
        repo_id  INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
        path     TEXT NOT NULL,          -- repo-relative, forward slashes
        language TEXT,
        UNIQUE (repo_id, path)
    );
    CREATE TABLE symbols (
        id         INTEGER PRIMARY KEY,
        repo_id    INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
        file_id    INTEGER REFERENCES files(id) ON DELETE CASCADE,  -- NULL only for wiki pages
        path       TEXT NOT NULL,
        language   TEXT,
        name       TEXT NOT NULL,
        kind       TEXT NOT NULL,        -- function | method | class | window | wiki
        start_line INTEGER NOT NULL,
        end_line   INTEGER NOT NULL,
        commit_sha TEXT,
        code       TEXT NOT NULL
    );
    CREATE INDEX symbols_repo ON symbols(repo_id);
    CREATE INDEX symbols_file ON symbols(file_id);
    CREATE INDEX symbols_name ON symbols(name);
    """,
    # 2: embeddings (existing rows get NULL until re-ingested)
    """
    ALTER TABLE symbols ADD COLUMN search_text TEXT;
    ALTER TABLE symbols ADD COLUMN embedding BLOB;  -- 384 x float32, unit length
    """,
]


def db_path() -> Path:
    return Path(os.environ.get("CCCTX_DB") or Path.home() / ".ccctx" / "ccctx.db")


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # CLI ingest and MCP server can overlap
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, script in enumerate(MIGRATIONS[version:], start=version + 1):
        with conn:
            conn.executescript(script)
            conn.execute(f"PRAGMA user_version = {i}")
