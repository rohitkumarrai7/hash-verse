from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from config import get_settings


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()
