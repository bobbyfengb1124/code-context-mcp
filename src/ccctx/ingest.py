"""Ingest a registered repository into the index."""

import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter_language_pack import detect_language_from_path

from . import chunk, git, store, walk
from .languages import for_path


class IngestError(ValueError):
    pass


@dataclass
class Summary:
    scanned: int = 0
    skipped: Counter = field(default_factory=Counter)
    files: int = 0
    symbols: int = 0
    seconds: float = 0.0


def language_of(path: str) -> str | None:
    spec = for_path(path)
    if spec:
        return spec.name
    if path.lower().endswith(".txt"):
        return "text"  # the pack's detector calls every .txt "vimdoc"
    try:
        return detect_language_from_path(path)
    except Exception:  # unknown extension: label only, never fatal
        return None


def ingest(conn: sqlite3.Connection, name: str) -> Summary:
    repo = store.get_repo(conn, name)
    if repo is None:
        raise IngestError(f"no repository named '{name}' (see `ccctx repo list`)")
    root = Path(repo["path"])
    started = time.perf_counter()
    sha = git.run(root, "rev-parse", "HEAD").strip()
    scan = walk.scan(root)
    summary = Summary(scanned=scan.scanned, skipped=scan.skipped)

    with conn:
        store.clear_repo(conn, repo["id"])
        for path in scan.files:
            language = language_of(path)
            chunks = chunk.chunk_file(path, (root / path).read_bytes())
            if not chunks:
                summary.skipped["empty"] += 1
                continue
            file_id = store.insert_file(conn, repo["id"], path, language)
            store.insert_symbols(conn, [
                (repo["id"], file_id, path, language, c.name, c.kind, c.start_line, c.end_line, sha, c.code)
                for c in chunks
            ])
            summary.files += 1
            summary.symbols += len(chunks)
        store.set_indexed(conn, repo["id"], sha)

    summary.seconds = time.perf_counter() - started
    return summary
