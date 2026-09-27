import hashlib

import numpy as np

from appfit.config import EMBEDDING_DIM, FAKE_EMBEDDER_TRIGRAM_WEIGHT
from appfit.text import content_tokens, stems

FAKE_MODEL_NAME = "fake-hash-v1"
_DIGEST_BYTES = 8
_SIGN_BIT = _DIGEST_BYTES * 8 - 1
_NGRAM = 3


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=_DIGEST_BYTES).digest()
    value = int.from_bytes(digest, "little")
    return value % dim, (1.0 if (value >> _SIGN_BIT) & 1 else -1.0)


class FakeEmbedder:
    """Deterministic feature-hashing embedder for tests and model-free development.

    Similarity follows lexical overlap (stems plus character trigrams), so pipeline tests stay meaningful."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    @property
    def model_id(self) -> str:
        return FAKE_MODEL_NAME

    @property
    def model_name(self) -> str:
        return FAKE_MODEL_NAME

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        for tok in content_tokens(text):
            for stem in stems(tok):
                idx, sign = _bucket("s:" + stem, self._dim)
                vec[idx] += sign
            padded = f"#{tok}#"
            for i in range(len(padded) - _NGRAM + 1):
                idx, sign = _bucket("t:" + padded[i : i + _NGRAM], self._dim)
                vec[idx] += sign * FAKE_EMBEDDER_TRIGRAM_WEIGHT
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec

    def _embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        return np.stack([self._embed_one(t) for t in texts]).astype(np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)
