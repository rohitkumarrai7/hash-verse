from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from config import get_settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# Known output dimensions for supported models (avoids loading model at startup)
MODEL_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-small-en-v1.5": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "intfloat/multilingual-e5-small": 384,
}


def get_embedding_dimension(model_name: str | None = None) -> int:
    settings = get_settings()
    name = model_name or settings.embedding_model
    return MODEL_DIMENSIONS.get(name, 384)


@lru_cache
def get_embedding_model() -> TextEmbedding:
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise ImportError(
            "fastembed is not installed. Run: cd backend && .venv\\Scripts\\pip install -r requirements.txt"
        ) from exc

    settings = get_settings()
    logger.info("Loading FastEmbed model: %s", settings.embedding_model)
    return TextEmbedding(model_name=settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    return [np.asarray(vector, dtype=np.float32).tolist() for vector in embeddings]
