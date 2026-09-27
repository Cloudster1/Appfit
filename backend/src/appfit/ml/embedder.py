from typing import Protocol

import numpy as np

from appfit.config import Settings


class Embedder(Protocol):
    """Produces L2-normalized float32 vectors; queries and passages may be encoded differently."""

    @property
    def model_id(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def embed_queries(self, texts: list[str]) -> np.ndarray: ...

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...


def expected_model_name(settings: Settings) -> str:
    if settings.embedding_backend == "fake":
        from appfit.ml.fake_embedder import FAKE_MODEL_NAME

        return FAKE_MODEL_NAME
    return settings.embedding_model


def expected_model_id(settings: Settings) -> str:
    """Model id the configured embedder will report, known before the model is loaded."""
    if settings.embedding_backend == "fake":
        from appfit.ml.fake_embedder import FAKE_MODEL_NAME

        return FAKE_MODEL_NAME
    rev = settings.embedding_model_revision
    return f"{settings.embedding_model}@{rev}" if rev else settings.embedding_model


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedding_backend == "fake":
        from appfit.ml.fake_embedder import FakeEmbedder

        return FakeEmbedder()

    from appfit.ml.st_embedder import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(
        model_name=settings.embedding_model,
        revision=settings.embedding_model_revision,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_seq_length=settings.embedding_max_seq_length,
    )
