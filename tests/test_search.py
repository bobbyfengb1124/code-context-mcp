import numpy as np

from ccctx import db, embed, search, store


class FakeEmbedder:
    """Maps known words to fixed unit vectors so similarities are predictable."""

    AXES = {"route": 0, "cookie": 1, "bread": 2}

    def embed(self, texts):
        out = np.zeros((len(texts), embed.DIM), dtype=np.float32)
        for i, t in enumerate(texts):
            for word, axis in self.AXES.items():
                if word in t:
                    out[i, axis] = 1.0
            out[i, 383] = 0.1  # keep every vector non-zero
        return out / np.linalg.norm(out, axis=1, keepdims=True)


def make_db(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    fake = FakeEmbedder()
    for repo, names in {"a": ["route_one", "cookie_jar"], "b": ["route_two"]}.items():
        store.add_repo(conn, repo, f"/{repo}")
        rid = store.get_repo(conn, repo)["id"]
        with conn:
            fid = store.insert_file(conn, rid, "x.py", "python")
            store.insert_symbols(conn, [
                (rid, fid, "x.py", "python", n, "function", 1, 2, "sha", n, n, embed.to_blob(fake.embed([n])[0]))
                for n in names
            ])
    return conn, fake


def test_vector_ranks_and_applies_floor(tmp_path):
    conn, fake = make_db(tmp_path)
    hits = search.search(conn, "route", embedder=fake)
    assert {h.name for h in hits} == {"route_one", "route_two"}  # tied scores; cookie_jar is below the floor
    assert all(h.score >= search.MIN_SIMILARITY for h in hits)


def test_unrelated_query_returns_nothing(tmp_path):
    conn, fake = make_db(tmp_path)
    assert search.search(conn, "bread", embedder=fake) == []


def test_repo_filter(tmp_path):
    conn, fake = make_db(tmp_path)
    assert [h.repo for h in search.search(conn, "route", repos=["b"], embedder=fake)] == ["b"]
