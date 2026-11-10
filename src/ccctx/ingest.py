"""Ingest a registered repository into the index."""

import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter_language_pack import detect_language_from_path

from . import chunk, embed, git, store, walk
from .embed import Embedder
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
    phases: dict[str, float] = field(default_factory=dict)  # phase -> seconds


class _Timer:
    def __init__(self, phases: dict[str, float]):
        self.phases, self.last = phases, time.perf_counter()

    def lap(self, phase: str) -> None:
        now = time.perf_counter()
        self.phases[phase] = self.phases.get(phase, 0.0) + now - self.last
        self.last = now


def search_text(c: chunk.Chunk, path: str) -> str:
    """What gets embedded (and, later, keyword-indexed): a short header plus the code."""
    return f"{c.kind} {c.name} in {path}\n{c.code}"


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


def ingest(conn: sqlite3.Connection, name: str, embedder: Embedder | None = None) -> Summary:
    repo = store.get_repo(conn, name)
    if repo is None:
        raise IngestError(f"no repository named '{name}' (see `ccctx repo list`)")
    root = Path(repo["path"])
    started = time.perf_counter()
    summary = Summary()
    timer = _Timer(summary.phases)

    sha = git.run(root, "rev-parse", "HEAD").strip()
    scan = walk.scan(root)
    summary.scanned, summary.skipped = scan.scanned, scan.skipped
    timer.lap("scan")

    parsed: list[tuple[str, str | None, list[chunk.Chunk]]] = []
    for path in scan.files:
        chunks = chunk.chunk_file(path, (root / path).read_bytes())
        if chunks:
            parsed.append((path, language_of(path), chunks))
        else:
            summary.skipped["empty"] += 1
    timer.lap("parse")

    texts = [search_text(c, path) for path, _, chunks in parsed for c in chunks]
    vectors = iter((embedder or embed.default()).embed(texts))
    timer.lap("embed")

    texts_iter = iter(texts)
    with conn:
        store.clear_repo(conn, repo["id"])
        for path, language, chunks in parsed:
            file_id = store.insert_file(conn, repo["id"], path, language)
            store.insert_symbols(conn, [
                (repo["id"], file_id, path, language, c.name, c.kind, c.start_line, c.end_line, sha,
                 c.code, next(texts_iter), embed.to_blob(next(vectors)))
                for c in chunks
            ])
            summary.files += 1
            summary.symbols += len(chunks)
        store.set_indexed(conn, repo["id"], sha)
    timer.lap("write")

    summary.seconds = time.perf_counter() - started
    return summary
