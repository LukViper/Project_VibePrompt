"""Cosine similarity, duplicate detection, and requirement linking."""

from __future__ import annotations

import numpy as np

from app.nlp.embeddings import create_embedding, get_embedder


def cosine_similarity(left: list[float] | np.ndarray, right: list[float] | np.ndarray) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def pairwise_similarity(texts_a: list[str], texts_b: list[str] | None = None) -> np.ndarray:
    embedder = get_embedder()
    if texts_b is None:
        matrix = embedder.encode(texts_a)
        return matrix @ matrix.T
    left = embedder.encode(texts_a)
    right = embedder.encode(texts_b)
    return left @ right.T


def find_related_requirements(
    text: str,
    requirements: list[dict],
    limit: int = 5,
) -> list[dict]:
    active = [req for req in requirements if req.get("status", "active") == "active" and req.get("text")]
    if not active:
        return []
    query = create_embedding(text)
    ranked = []
    for req in active:
        score = cosine_similarity(query, create_embedding(req["text"]))
        ranked.append({
            "id": req.get("id"),
            "text": req.get("text"),
            "similarity": round(score, 4),
            "type": req.get("type"),
            "slot": req.get("slot"),
            "slot_value": req.get("slot_value"),
            "domain": req.get("domain"),
        })
    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return ranked[:limit]


def is_near_duplicate(score: float, threshold: float) -> bool:
    return score >= threshold


def cluster_by_similarity(items: list[dict], text_key: str, threshold: float) -> list[list[dict]]:
    """Greedy single-link clustering. Retains insertion order within clusters."""
    clusters: list[list[dict]] = []
    centroids: list[list[float]] = []
    for item in items:
        vector = create_embedding(str(item.get(text_key, "")))
        placed = False
        for index, centroid in enumerate(centroids):
            if cosine_similarity(vector, centroid) >= threshold:
                clusters[index].append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
            centroids.append(vector)
    return clusters


def most_complete(items: list[dict]) -> dict:
    def richness(item: dict) -> int:
        return sum(len(item.get(key) or []) for key in ("features", "technology", "required_concepts", "extensions")) + len(item.get("problem") or "")
    return max(items, key=richness)
