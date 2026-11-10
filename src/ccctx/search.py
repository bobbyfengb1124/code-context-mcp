"""Search the index. Modes share one signature and are looked up by name."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from . import embed, store
from .embed import Embedder

MIN_SIMILARITY = 0.3  # below this a match is noise; better to return nothing


@dataclass
class Hit:
    id: int
    repo: str
    path: str
    name: str
    kind: str
    language: str | None
    start_line: int
    end_line: int
    score: float
    code: str


Mode = Callable[[sqlite3.Connection, str, list[str] | None, int, Embedder], list[tuple[int, float]]]


def vector(conn, query, repos, limit, embedder) -> list[tuple[int, float]]:
    """(symbol id, cosine similarity) for the closest symbols at or above MIN_SIMILARITY."""
    # shortcut: brute-force over every embedding in numpy; fine to ~200k symbols, then move to sqlite-vec
    ids, blobs = store.embeddings(conn, repos)
    if not ids:
        return []
    sims = embed.from_blobs(blobs) @ embedder.embed([query])[0]
    top = np.argsort(-sims)[:limit]
    return [(ids[i], float(sims[i])) for i in top if sims[i] >= MIN_SIMILARITY]


MODES: dict[str, Mode] = {"vector": vector}


def search(conn: sqlite3.Connection, query: str, repos: list[str] | None = None, limit: int = 10,
           mode: str = "vector", embedder: Embedder | None = None) -> list[Hit]:
    scored = MODES[mode](conn, query, repos, limit, embedder or embed.default())
    rows = store.symbols_by_id(conn, [i for i, _ in scored])
    return [
        Hit(i, r["repo"], r["path"], r["name"], r["kind"], r["language"],
            r["start_line"], r["end_line"], score, r["code"])
        for i, score in scored if (r := rows.get(i))
    ]
