"""Text -> vector. Swap the model by providing another Embedder."""

import os
from functools import cache
from typing import Protocol

import numpy as np

DIM = 384


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, DIM) float32 array of unit-length vectors."""
        ...


class FastEmbedder:
    # all-MiniLM-L6-v2 reads only the first 256 tokens of each text; longer chunks are judged by their start
    MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, batch_size: int = 64):
        # harmless on Windows without Developer Mode: the model cache just copies instead of symlinking
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed import TextEmbedding  # slow import; only pay for it when embedding

        self._model = TextEmbedding(self.MODEL)
        self._batch_size = batch_size

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        vecs = np.asarray(list(self._model.embed(texts, batch_size=self._batch_size)), dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


@cache
def default() -> Embedder:
    return FastEmbedder()


def to_blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def from_blobs(blobs: list[bytes]) -> np.ndarray:
    return np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(blobs), DIM)
