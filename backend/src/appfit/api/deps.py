from fastapi import Request

from appfit.ml.embedder import Embedder, expected_model_id
from appfit.services.errors import UnavailableError


def get_embedder(request: Request) -> Embedder:
    embedder: Embedder | None = request.app.state.embedder
    if embedder is None:
        error = request.app.state.embedder_error
        raise UnavailableError(
            f"Embedding model failed to load: {error}" if error else "Embedding model is still loading"
        )
    return embedder


def active_model_id(request: Request) -> str:
    embedder: Embedder | None = request.app.state.embedder
    return embedder.model_id if embedder is not None else expected_model_id(request.app.state.settings)
