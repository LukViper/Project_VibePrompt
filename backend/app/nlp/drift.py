"""Requirement drift and scope-creep analysis.

Similarity thresholds are selected from validation data when that file is
present. A hard-coded cutoff is never described as universal.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config.settings import get_settings
from app.nlp.embeddings import create_embedding, get_embedder
from app.nlp.extraction import detect_domains
from app.nlp.lexicon import DOMAIN_LABELS, SCOPE_EXPANSION_DOMAINS, domains_conflict
from app.nlp.similarity import cosine_similarity

_THRESHOLD_CACHE: dict[str, float] | None = None


def _validation_rows() -> list[dict]:
    path = Path(get_settings().dataset_dir) / "drift_validation.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def select_drift_threshold(rows: list[dict] | None = None) -> dict:
    """Choose a threshold that maximises F1 on labeled validation pairs.

    Each row is ``{"objective": "", "requirement": "", "drift": 0 or 1}``.
    The score used is ``1 - cosine similarity``. Higher means more drift.
    """
    rows = rows if rows is not None else _validation_rows()
    embedder = get_embedder().name
    if len(rows) < 4:
        return {
            "threshold": 0.55,
            "status": "provisional",
            "backend": embedder,
            "note": "Not a universal threshold. Select one using validation data.",
        }
    scored = []
    for row in rows:
        similarity = cosine_similarity(create_embedding(row["objective"]), create_embedding(row["requirement"]))
        scored.append((1.0 - similarity, int(row["drift"])))
    best = {"threshold": 0.55, "f1": -1.0}
    for step in range(20, 90):
        cutoff = step / 100
        tp = fp = fn = 0
        for score, label in scored:
            predicted = int(score >= cutoff)
            tp += int(predicted == 1 and label == 1)
            fp += int(predicted == 1 and label == 0)
            fn += int(predicted == 0 and label == 1)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best["f1"]:
            best = {"threshold": cutoff, "f1": f1, "precision": precision, "recall": recall}
    return {
        "threshold": best["threshold"],
        "status": "selected_from_validation_data",
        "backend": embedder,
        "selection_f1": best.get("f1"),
        "note": "Threshold selected on the supplied validation rows for this embedding backend. It is not a universal constant.",
    }


def drift_threshold() -> dict:
    global _THRESHOLD_CACHE
    if _THRESHOLD_CACHE is None:
        _THRESHOLD_CACHE = select_drift_threshold()
    return _THRESHOLD_CACHE


def _core_domains(state: dict) -> set[str]:
    found = set()
    core = state.get("core_idea") or {}
    if core.get("primary_domain"):
        label = str(core["primary_domain"]).lower()
        if "nlp" in label or label == "nlp":
            found.add("nlp")
        else:
            found.update(detect_domains(label))
    academic = (state.get("academic") or {}).get("subject") or ""
    found.update(detect_domains(str(academic)))
    found.update(detect_domains(str((state.get("project") or {}).get("objective") or "")))
    found.update(detect_domains(str((state.get("project") or {}).get("problem") or "")))
    found.update(state.get("domains") or [])
    return found


def _duration_weeks(duration: str | None) -> int | None:
    if not duration:
        return None
    match = re.search(r"(\d+)\s+week", duration)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s+month", duration)
    if match:
        return int(match.group(1)) * 4
    return None


def calculate_drift(state: dict, new_texts: list[str]) -> dict:
    core = state.get("core_idea") or {}
    objective = core.get("primary_objective") or (state.get("project") or {}).get("objective") or ""
    original = [
        req for req in state.get("requirements") or []
        if req.get("status") == "active" and req.get("origin") == "original" and req.get("text")
    ]
    reference = objective or " ".join(req["text"] for req in original)
    selected = drift_threshold()
    per_requirement = []
    drifted = []
    core_domains = _core_domains(state)
    for text in new_texts:
        if not text or not reference:
            continue
        similarity = cosine_similarity(create_embedding(reference), create_embedding(text))
        domains = detect_domains(text)
        unrelated = domains_conflict(core_domains, set(domains))
        score = 1.0 - similarity
        # Similarity is reported for every new requirement. The operational drift
        # flag is an unrelated domain, not a universal cosine cutoff.
        flagged = unrelated
        entry = {
            "text": text,
            "similarity": round(similarity, 4),
            "drift_score": round(score, 4),
            "domains": [DOMAIN_LABELS.get(item, item) for item in domains],
            "potential_drift": flagged,
        }
        per_requirement.append(entry)
        if flagged:
            drifted.append(entry)
    return {
        "reference": reference,
        "threshold": selected,
        "requirements": per_requirement,
        "potential_drift": bool(drifted),
        "drifted": drifted,
        "backend": get_embedder().name,
    }


def analyze_scope(state: dict, new_domains: list[str], added_count: int) -> dict:
    core_domains = _core_domains(state)
    known = set()
    for req in state.get("requirements") or []:
        if req.get("domain"):
            known.add(req["domain"])
    known.update(core_domains)
    introduced = [domain for domain in new_domains if domain not in known]
    expansion = [domain for domain in introduced if domain in SCOPE_EXPANSION_DOMAINS]
    unrelated = [domain for domain in introduced if domains_conflict(core_domains, {domain})]
    active = [req for req in state.get("requirements") or [] if req.get("status") == "active"]
    weeks = _duration_weeks((state.get("constraints") or {}).get("duration"))
    pressure = False
    if weeks is not None and (len(active) + added_count) > weeks * 3:
        pressure = True
    detected = bool(expansion or unrelated or pressure)
    return {
        "detected": detected,
        "new_domains": [DOMAIN_LABELS.get(item, item) for item in introduced],
        "expansion_domains": [DOMAIN_LABELS.get(item, item) for item in expansion],
        "unrelated_domains": [DOMAIN_LABELS.get(item, item) for item in unrelated],
        "time_pressure": pressure,
        "message": _scope_message(expansion, unrelated, pressure),
    }


def _scope_message(expansion: list[str], unrelated: list[str], pressure: bool) -> str | None:
    names = [DOMAIN_LABELS.get(item, item) for item in expansion + unrelated]
    if not names and not pressure:
        return None
    lines = ["Potential scope expansion detected."]
    if names:
        lines.append("New technical domains:")
        lines.extend(f"- {name}" for name in names)
    if pressure:
        lines.append("The requirement count is high relative to the stated duration.")
    lines.append("The final decision remains with you.")
    return "\n".join(lines)
