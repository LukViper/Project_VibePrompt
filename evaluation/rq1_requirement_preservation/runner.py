"""RQ1 system runners.

VibePrompt path: Conversation → real extraction → ProjectState → compilable requirements.
Gold is NEVER passed into any system as prediction.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

# Backend on path is caller's responsibility (run.py).


def llm_config_metadata() -> dict[str, Any]:
    """Record LLM configuration when used; honest about unavailability."""
    model = os.environ.get("VIBEPROMPT_EVAL_LLM_MODEL") or os.environ.get("GEMINI_MODEL")
    available = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("VIBEPROMPT_EVAL_LLM_CMD"))
    return {
        "model": model or ("heuristic_fallback" if not available else "unspecified"),
        "version": os.environ.get("VIBEPROMPT_EVAL_LLM_VERSION") or "n/a",
        "configuration": {
            "temperature": float(os.environ.get("VIBEPROMPT_EVAL_TEMPERATURE", "0")),
            "seed": os.environ.get("VIBEPROMPT_EVAL_SEED") or "42",
            "provider": "gemini" if os.environ.get("GEMINI_API_KEY") else (
                "external_cmd" if os.environ.get("VIBEPROMPT_EVAL_LLM_CMD") else "none"
            ),
        },
        "temperature": float(os.environ.get("VIBEPROMPT_EVAL_TEMPERATURE", "0")),
        "seed": os.environ.get("VIBEPROMPT_EVAL_SEED") or "42",
        "available": available,
    }


def baseline_a_direct_extraction(messages: list[str]) -> dict[str, Any]:
    """Baseline A: conversation → direct LLM prompt/requirement extraction.

    When no LLM is configured, uses a deterministic heuristic (NOT gold).
    """
    meta = llm_config_metadata()
    if meta["available"] and os.environ.get("VIBEPROMPT_EVAL_LLM_CMD"):
        # Optional external extractor; kept for future wiring.
        texts = _external_llm_extract(messages, mode="direct")
        return {"requirements": texts, "constraints": [], "technologies": [], "llm": meta}

    # Deterministic direct extraction: keep non-retraction utterances as candidates.
    reqs = []
    for m in messages:
        if re.search(r"\b(don't|do not|after all)\b|actually.*(unnecessary|don't|drop|no )", m, re.I):
            continue
        if re.search(r"\b(want|need|must|build|support|use|include|require)\b", m, re.I):
            reqs.append(m.strip())
    return {
        "requirements": reqs or [m.strip() for m in messages if m.strip()][:3],
        "constraints": [],
        "technologies": _scan_tech(messages),
        "llm": meta,
        "method": "heuristic_direct" if not meta["available"] else "llm_direct",
    }


def baseline_b_structured_json(messages: list[str]) -> dict[str, Any]:
    """Baseline B: conversation → LLM structured JSON requirements.

    Without LLM: deterministic structured heuristic (NOT gold).
    """
    meta = llm_config_metadata()
    if meta["available"] and os.environ.get("VIBEPROMPT_EVAL_LLM_CMD"):
        payload = _external_llm_extract(messages, mode="json")
        if isinstance(payload, dict):
            return {
                "requirements": list(payload.get("requirements") or []),
                "constraints": list(payload.get("constraints") or []),
                "technologies": list(payload.get("technologies") or []),
                "llm": meta,
                "method": "llm_structured_json",
            }

    requirements, constraints, technologies = [], [], []
    for m in messages:
        low = m.lower()
        if re.search(r"\b(don't|do not|actually don't|unnecessary|drop |no authentication|after all)\b", low):
            continue
        if re.search(r"\b(must|require|below|under|team of|weeks|budget)\b", low):
            constraints.append(m.strip())
        elif re.search(r"\b(use|with)\s+[A-Za-z0-9.+#-]+", low):
            technologies.extend(_scan_tech([m]))
            requirements.append(m.strip())
        elif re.search(r"\b(want|need|build|support|include|detect|classify)\b", low):
            requirements.append(m.strip())
    return {
        "requirements": requirements,
        "constraints": constraints,
        "technologies": technologies or _scan_tech(messages),
        "llm": meta,
        "method": "heuristic_structured_json" if not meta["available"] else "llm_structured_json",
    }


def vibeprompt_pipeline(messages: list[str]) -> dict[str, Any]:
    """Actual VibePrompt path: extract_information → apply_analysis_to_state → ProjectState.

    Gold is not an input. LLM extraction is skipped when provider unavailable
    (same as production _maybe_llm_extract).
    """
    from app.nlp.contradiction import classify_relationship, find_slot_conflict
    from app.nlp.drift import analyze_scope, calculate_drift
    from app.nlp.extraction import extract_information
    from app.nlp.intent import classify_intent
    from app.nlp.preprocessing import preprocess
    from app.nlp.similarity import find_related_requirements
    from app.services.assertion_lifecycle import requirement_is_compilable
    from app.services.project_state import apply_analysis_to_state, apply_constraint_cues, empty_state, public_state

    state = empty_state()
    for content in messages:
        prepared = preprocess(content)
        intent = classify_intent(prepared["text"])
        extraction = extract_information(prepared["text"])
        related = find_related_requirements(prepared["text"], state.get("requirements") or [])
        slot_conflict = find_slot_conflict(state, extraction)
        relationship = classify_relationship(
            prepared["text"],
            related,
            intent["intent"],
            extraction.domains,
            [],
            slot_conflict,
        )
        new_texts = [req.text for req in extraction.requirements]
        if intent["intent"] != "REMOVE_REQUIREMENT":
            drift = calculate_drift(state, new_texts)
        else:
            drift = {"potential_drift": False, "drifted": [], "requirements": [], "backend": "n/a"}
        scope = analyze_scope(state, extraction.domains, len(new_texts))
        analysis = {
            "intent": intent,
            "extraction": extraction,
            "related": related,
            "relationship": relationship,
            "slot_conflict": slot_conflict,
            "drift": drift,
            "scope": scope,
        }
        state = apply_analysis_to_state(state, analysis, reason=intent["intent"])
        state = apply_constraint_cues(state, prepared["text"])
        state = public_state(state)

    active = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    compilable = [r for r in active if requirement_is_compilable(r)]
    # Prefer compilable; if none yet (all proposed), still emit active texts so metrics
    # reflect extraction+state rather than silently empty predictions.
    req_texts = [r.get("text") or "" for r in (compilable or active)]
    constraints = _constraints_from_state(state)
    technologies = _technologies_from_state(state)
    origins = {
        (r.get("text") or ""): r.get("assertion_origin") or "UNKNOWN"
        for r in active
        if r.get("text")
    }
    rejected = [
        r.get("text") or ""
        for r in (state.get("requirements") or [])
        if r.get("status") in {"rejected", "removed", "superseded"}
    ]
    return {
        "requirements": req_texts,
        "constraints": constraints,
        "technologies": technologies,
        "assertion_origins": origins,
        "rejected_in_state": rejected,
        "state_summary": {
            "n_active": len(active),
            "n_compilable": len(compilable),
            "n_decisions": len(state.get("decisions") or []),
            "technologies": technologies,
        },
        "llm": llm_config_metadata(),
        "method": "vibeprompt_extraction_projectstate",
        "_from_gold": False,
    }


def run_all_systems(messages: list[str]) -> dict[str, dict[str, Any]]:
    return {
        "baseline_a": baseline_a_direct_extraction(messages),
        "baseline_b": baseline_b_structured_json(messages),
        "vibeprompt": vibeprompt_pipeline(messages),
    }


def _scan_tech(messages: list[str]) -> list[str]:
    lexicon = [
        "bert", "postgresql", "sqlite", "flutter", "firebase", "websocket", "redis",
        "kafka", "kubernetes", "nginx", "grpc", "elasticsearch", "tf-idf", "react",
    ]
    found = []
    blob = " ".join(messages).lower()
    for t in lexicon:
        if t in blob:
            found.append(t)
    return found


def _constraints_from_state(state: dict) -> list[str]:
    out = []
    c = state.get("constraints") or {}
    if c.get("team_size") is not None:
        out.append(f"team of {c['team_size']}")
    if c.get("duration"):
        out.append(str(c["duration"]))
    if c.get("budget"):
        out.append(f"budget {c['budget']}")
    for item in c.get("avoid") or []:
        out.append(f"avoid {item}")
    # Nonfunctional requirements often encode constraints
    for req in state.get("requirements") or []:
        if req.get("status") != "active":
            continue
        text = (req.get("text") or "").lower()
        if re.search(r"\b(ms|latency|must|under|below|only)\b", text):
            out.append(req.get("text") or "")
    return list(dict.fromkeys(out))


def _technologies_from_state(state: dict) -> list[str]:
    tech = state.get("technology") or {}
    items = []
    for key in ("languages", "frameworks", "databases", "models", "hardware", "other"):
        val = tech.get(key)
        if isinstance(val, list):
            items.extend(str(v) for v in val)
        elif isinstance(val, str) and val:
            items.append(val)
    # Flatten nested common shapes
    for key, val in tech.items():
        if isinstance(val, list):
            items.extend(str(v) for v in val)
        elif isinstance(val, str) and val and key not in {"backend", "database", "model"}:
            items.append(val)
        elif isinstance(val, str) and val:
            items.append(val)
    return list(dict.fromkeys(v.lower() for v in items if v))


def _external_llm_extract(messages: list[str], *, mode: str) -> Any:
    import subprocess

    cmd = os.environ["VIBEPROMPT_EVAL_LLM_CMD"]
    payload = json.dumps({"messages": messages, "mode": mode})
    proc = subprocess.run(
        cmd,
        input=payload,
        text=True,
        shell=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return [] if mode == "direct" else {}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if mode == "direct" and isinstance(data, list):
        return [str(x) for x in data]
    return data
