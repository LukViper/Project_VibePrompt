"""Embedding backends.

Sentence Transformers are preferred. A hashing vectorizer remains available
so similarity, linking, and evaluation still run without a downloaded model.
The active backend name is always reported; scores are never fabricated.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from app.config.settings import get_settings
from app.nlp.preprocessing import preprocess

_ST_MODEL = None
_ST_TRIED = False


def _sentence_transformer():
    global _ST_MODEL, _ST_TRIED
    if _ST_TRIED:
        return _ST_MODEL
    _ST_TRIED = True
    try:
        from sentence_transformers import SentenceTransformer

        _ST_MODEL = SentenceTransformer(get_settings().embedding_model, device="cpu")
    except Exception:
        _ST_MODEL = None
    return _ST_MODEL


class EmbeddingBackend:
    def __init__(self) -> None:
        self._hasher = HashingVectorizer(
            n_features=512,
            alternate_sign=False,
            norm="l2",
            ngram_range=(1, 2),
        )

    @property
    def name(self) -> str:
        return "sentence-transformers" if _sentence_transformer() is not None else "hashing-vectorizer"

    def encode(self, texts: list[str]) -> np.ndarray:
        prepared = [preprocess(text, for_transformer=True)["text"] for text in texts]
        model = _sentence_transformer()
        if model is not None:
            vectors = model.encode(prepared, normalize_embeddings=True)
            return np.asarray(vectors, dtype=float)
        if not prepared:
            return np.zeros((0, 512))
        return self._hasher.transform(prepared).toarray()


@lru_cache
def get_embedder() -> EmbeddingBackend:
    return EmbeddingBackend()


def create_embedding(text: str) -> list[float]:
    vector = get_embedder().encode([text or ""])[0]
    return vector.tolist()


def stable_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
