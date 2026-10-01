"""Command-line NLP prototype. It does not require the database or UI."""

from __future__ import annotations

import argparse
import json

from app.nlp.contradiction import classify_relationship, find_slot_conflict
from app.nlp.drift import analyze_scope, calculate_drift
from app.nlp.extraction import extract_information
from app.nlp.intent import classify_intent
from app.nlp.preprocessing import preprocess
from app.nlp.similarity import find_related_requirements
from app.services.project_state import empty_state


def run_pipeline(text: str, state: dict | None = None) -> dict:
    state = state or empty_state()
    prepared = preprocess(text)
    intent = classify_intent(prepared["text"])
    extraction = extract_information(prepared["text"])
    related = find_related_requirements(prepared["text"], state.get("requirements") or [])
    conflict = find_slot_conflict(state, extraction)
    relationship = classify_relationship(
        prepared["text"],
        related,
        intent["intent"],
        extraction.domains,
        [],
        conflict,
    )
    drift = calculate_drift(state, [req.text for req in extraction.requirements])
    scope = analyze_scope(state, extraction.domains, len(extraction.requirements))
    return {
        "preprocessing": {"method": prepared["method"], "sentences": prepared["sentences"], "prompt_injection": prepared["prompt_injection"]},
        "intent": intent,
        "extraction": extraction.model_dump(),
        "related": related,
        "relationship": relationship,
        "slot_conflict": conflict,
        "drift": drift,
        "scope": scope,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="VibePrompt NLP prototype")
    parser.add_argument("--text", help="Single message to analyse")
    args = parser.parse_args()
    if args.text:
        print(json.dumps(run_pipeline(args.text), indent=2, default=str))
        return
    print("VibePrompt NLP prototype. Empty line to exit.")
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            break
        if not text:
            break
        print(json.dumps(run_pipeline(text), indent=2, default=str))


if __name__ == "__main__":
    main()
