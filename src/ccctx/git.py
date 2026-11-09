"""Thin wrappers over the git CLI."""

import subprocess
from pathlib import Path


def run(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def toplevel(path: Path) -> Path | None:
    """The repo root containing `path`, or None if it is not inside a git work tree."""
    try:
        return Path(run(path, "rev-parse", "--show-toplevel").strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return None
