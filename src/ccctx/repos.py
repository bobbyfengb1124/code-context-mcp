"""Repository registration service (shared by CLI and MCP)."""

import sqlite3
from pathlib import Path

from . import git, store


class RepoError(ValueError):
    pass


def add(conn: sqlite3.Connection, path: str, name: str | None = None) -> tuple[str, Path]:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise RepoError(f"not a directory: {root}")
    if git.toplevel(root) != root:
        raise RepoError(f"not the root of a git repository: {root}")
    name = name or root.name
    if store.get_repo(conn, name):
        raise RepoError(f"a repository named '{name}' is already registered")
    store.add_repo(conn, name, str(root))
    return name, root


def list_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return store.list_repos(conn)
