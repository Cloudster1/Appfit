import logging

import numpy as np

log = logging.getLogger(__name__)

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str,
        revision: str | None,
        device: str,
        batch_size: int,
        max_seq_length: int,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        log.info("Loading embedding model %s (revision=%s, device=%s)", model_name, revision, device)
        self._model = SentenceTransformer(model_name, revision=revision, device=device)
        self._model.max_seq_length = max_seq_length
        get_dim = getattr(self._model, "get_embedding_dimension", None) or (
            self._model.get_sentence_embedding_dimension
        )
        dim = get_dim()
        if dim is None:
            raise RuntimeError(f"Model {model_name} does not report an embedding dimension")
        self._dim = int(dim)
        self._batch_size = batch_size
        self._model_name = model_name
        self._model_id = f"{model_name}@{revision}" if revision else model_name
        self._is_e5 = "e5" in model_name.lower()

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        vecs = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        if self._is_e5:
            texts = [E5_QUERY_PREFIX + t for t in texts]
        return self._encode(texts)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        if self._is_e5:
            texts = [E5_PASSAGE_PREFIX + t for t in texts]
        return self._encode(texts)
