"""Relationship and contradiction detection.

A rule baseline covers technology-slot conflicts. A pretrained NLI model,
when installed, supplies SUPPORTS / CONTRADICTS evidence. The LLM may explain
a conflict later; it does not own the classification.
"""

from __future__ import annotations

import re

from app.config.settings import get_settings
from app.nlp.lexicon import domains_conflict

RELATIONSHIPS = ["SUPPORTS", "CONTRADICTS", "MODIFIES", "EXTENDS", "UNRELATED"]

_NLI = None
_NLI_TRIED = False
_TOKENIZER = None


def _nli():
    global _NLI, _NLI_TRIED, _TOKENIZER
    if _NLI_TRIED:
        return _NLI, _TOKENIZER
    _NLI_TRIED = True
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        name = get_settings().nli_model
        _TOKENIZER = AutoTokenizer.from_pretrained(name)
        _NLI = AutoModelForSequenceClassification.from_pretrained(name)
        _NLI.eval()
        _NLI._torch = torch
    except Exception:
        _NLI = None
        _TOKENIZER = None
    return _NLI, _TOKENIZER


def nli_label(premise: str, hypothesis: str) -> dict | None:
    model, tokenizer = _nli()
    if model is None or tokenizer is None:
        return None
    torch = model._torch
    encoded = tokenizer(premise, hypothesis, return_tensors="pt", truncation=True)
    with torch.no_grad():
        logits = model(**encoded).logits
        probs = torch.softmax(logits, dim=-1)[0]
    labels = [model.config.id2label[i] for i in range(len(probs))]
    index = int(torch.argmax(probs))
    raw = labels[index].lower()
    if "contradict" in raw:
        mapped = "CONTRADICTS"
    elif "entail" in raw:
        mapped = "SUPPORTS"
    else:
        mapped = "UNRELATED"
    return {
        "label": mapped,
        "raw_label": labels[index],
        "confidence": round(float(probs[index]), 4),
        "method": "nli",
    }


def _modify_cue(text: str) -> bool:
    return bool(re.search(r"\b(instead|switch|replace|change|modify|update|now use)\b", text, re.I))


def _extend_cue(text: str) -> bool:
    return bool(re.search(r"\b(add|also|include|additionally|as well|let's add|and let's)\b", text, re.I))


def classify_relationship(
    message: str,
    related: list[dict],
    intent: str,
    extracted_domains: list[str],
    core_domains: list[str],
    slot_conflict: dict | None,
) -> dict:
    top = related[0] if related else None
    similarity = top["similarity"] if top else 0.0
    nli = None
    if top and top.get("text"):
        nli = nli_label(top["text"], message)

    if slot_conflict and not _modify_cue(message) and intent != "MODIFY_REQUIREMENT":
        label = "CONTRADICTS"
    elif slot_conflict and (_modify_cue(message) or intent == "MODIFY_REQUIREMENT"):
        label = "MODIFIES"
    elif intent == "REMOVE_REQUIREMENT" and top:
        label = "MODIFIES"
    elif nli and nli["label"] == "CONTRADICTS" and nli["confidence"] >= 0.6 and not _extend_cue(message):
        label = "CONTRADICTS"
    elif domains_conflict(set(core_domains), set(extracted_domains)) and _extend_cue(message):
        label = "UNRELATED"
    elif _extend_cue(message):
        label = "EXTENDS"
    elif nli and nli["label"] == "SUPPORTS" and nli["confidence"] >= 0.55:
        label = "SUPPORTS"
    elif similarity >= 0.72:
        label = "SUPPORTS"
    elif intent == "MODIFY_REQUIREMENT":
        label = "MODIFIES"
    else:
        label = "UNRELATED"

    impact = "low"
    if label == "UNRELATED":
        impact = "high"
    elif extracted_domains and any(domain in {"browser_extension", "mobile", "web"} for domain in extracted_domains):
        impact = "moderate"
    elif label == "EXTENDS":
        impact = "moderate" if extracted_domains else "low"
    elif label == "CONTRADICTS":
        impact = "high"

    return {
        "relationship": label,
        "impact": impact,
        "similarity": similarity,
        "nli": nli,
        "method": "rules+nli" if nli else "rules",
    }


def find_slot_conflict(state: dict, extraction) -> dict | None:
    technology = state.get("technology") or {}
    constraints = []
    for req in extraction.requirements:
        if not req.slot or not req.slot_value:
            continue
        current = technology.get(req.slot)
        if current and current.lower() != req.slot_value.lower():
            constraints.append({
                "slot": req.slot,
                "existing": current,
                "incoming": req.slot_value,
            })
    for req in state.get("requirements") or []:
        if req.get("status") != "active" or not req.get("slot"):
            continue
        for new in extraction.requirements:
            if new.slot and new.slot == req.get("slot") and new.slot_value and req.get("slot_value"):
                if new.slot_value.lower() != str(req.get("slot_value")).lower():
                    return {
                        "slot": new.slot,
                        "existing": req.get("slot_value"),
                        "incoming": new.slot_value,
                        "requirement_id": req.get("id"),
                    }
    if constraints:
        return constraints[0]
    # Exclusion violated by a new requirement.
    avoid = [item.lower() for item in (state.get("constraints") or {}).get("avoid") or []]
    for new in extraction.requirements:
        for banned in avoid:
            if banned and banned in new.text.lower():
                return {"slot": "exclusion", "existing": banned, "incoming": new.text, "requirement_id": None}
    return None


def rule_contradiction(text_a: str, text_b: str) -> str:
    """Small labeled baseline used by evaluation, independent of project state."""
    pair = text_a.lower() + " || " + text_b.lower()
    languages = ["python", "java", "javascript", "go", "rust"]
    hits = [lang for lang in languages if lang in pair]
    if "must use" in text_a.lower() and "must use" in text_b.lower() and len(hits) >= 2:
        return "CONTRADICTS"
    if text_a.lower().strip() == text_b.lower().strip():
        return "SUPPORTS"
    return "UNRELATED"
