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


class LexicalFallbackProvider:
    """Hashing vectorizer — availability fallback, not semantic equivalence."""

    name = "LexicalFallback"
    model = "HashingVectorizer"
    model_version = "sklearn"
    dimension = 512

    def __init__(self) -> None:
        self._hasher = HashingVectorizer(
            n_features=self.dimension,
            alternate_sign=False,
            norm="l2",
            ngram_range=(1, 2),
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        prepared = [preprocess(text, for_transformer=True)["text"] for text in texts]
        if not prepared:
            return np.zeros((0, self.dimension))
        return self._hasher.transform(prepared).toarray()


class SentenceTransformerProvider:
    name = "SentenceTransformerProvider"

    def __init__(self, model) -> None:
        self._model = model
        settings = get_settings()
        self.model = settings.embedding_model
        self.model_version = getattr(model, "model_card", None) or self.model

    @property
    def dimension(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        prepared = [preprocess(text, for_transformer=True)["text"] for text in texts]
        vectors = self._model.encode(prepared, normalize_embeddings=True)
        return np.asarray(vectors, dtype=float)


class EmbeddingBackend:
    def __init__(self) -> None:
        self._lexical = LexicalFallbackProvider()
        self._provider = self._resolve_provider()

    def _resolve_provider(self):
        model = _sentence_transformer()
        if model is not None:
            return SentenceTransformerProvider(model)
        return self._lexical

    @property
    def name(self) -> str:
        return self._provider.name

    def metadata(self) -> dict:
        return {
            "provider": self._provider.name,
            "model": getattr(self._provider, "model", "unknown"),
            "model_version": getattr(self._provider, "model_version", "unknown"),
            "dimension": getattr(self._provider, "dimension", 512),
            "is_lexical_fallback": self._provider.name == LexicalFallbackProvider.name,
        }

    def encode(self, texts: list[str]) -> np.ndarray:
        prepared = [preprocess(text, for_transformer=True)["text"] for text in texts]
        return self._provider.encode(prepared)


@lru_cache
def get_embedder() -> EmbeddingBackend:
    return EmbeddingBackend()


def embedding_metadata() -> dict:
    return get_embedder().metadata()


def create_embedding(text: str) -> list[float]:
    vector = get_embedder().encode([text or ""])[0]
    return vector.tolist()


def stable_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
