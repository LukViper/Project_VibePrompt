"""RQ5 prompt variants A / B / C — C uses the real VibePrompt pipeline."""

from __future__ import annotations

from typing import Any

VARIANTS = ("A_raw", "B_structured", "C_vibeprompt")


def build_variant_prompts(task: dict) -> dict[str, str]:
    """Build A/B prompts (and a C fallback text). Prefer build_prompts_with_provenance for C."""
    result = build_prompts_with_provenance(task)
    return {k: v["prompt"] for k, v in result.items()}


def build_prompts_with_provenance(task: dict) -> dict[str, dict[str, Any]]:
    """Return prompts plus provenance. C invokes production VibePrompt services."""
    conversation = list(task.get("conversation") or [])
    if not conversation and task.get("problem_statement"):
        conversation = [
            f"I need: {task['problem_statement']}",
            *[f"Requirement: {r}" for r in task.get("gold_requirements") or []],
        ]
    requirements = list(task.get("gold_requirements") or [])
    constraints = list(task.get("constraints") or [])
    acceptance = list(task.get("acceptance_criteria") or requirements)
    rejected = list(task.get("rejected_features") or [])

    raw = "You are a senior software engineer.\n\n" + "\n".join(conversation)
    structured = (
        "You are a senior software engineer.\n\nREQUIREMENTS\n"
        + "\n".join(f"- {r}" for r in requirements)
        + "\n\nCONSTRAINTS\n"
        + "\n".join(f"- {c}" for c in constraints)
        + "\n\nREJECTED / OUT OF SCOPE\n"
        + "\n".join(f"- {r}" for r in rejected)
        + "\n\nACCEPTANCE CRITERIA\n"
        + "\n".join(f"- {a}" for a in acceptance)
    )

    c_result = _build_c(conversation, task)
    return {
        "A_raw": {
            "prompt": raw,
            "method": "direct_conversation",
            "provenance": {"pipeline": ["conversation", "direct_prompt"]},
        },
        "B_structured": {
            "prompt": structured,
            "method": "structured_requirements",
            "provenance": {"pipeline": ["conversation", "structured_requirements_prompt"]},
        },
        "C_vibeprompt": c_result,
    }


def _build_c(conversation: list[str], task: dict) -> dict[str, Any]:
    from evaluation.rq5_agent_execution.c_pipeline import run_vibeprompt_c_pipeline

    out = run_vibeprompt_c_pipeline(conversation, task=task)
    return {
        "prompt": out["prompt"],
        "method": out["method"],
        "provenance": out["provenance"],
        "specification_markdown": out.get("specification_markdown"),
        "state_summary": {
            "n_compilable": out["provenance"].get("n_compilable_requirements"),
            "gate": out["provenance"].get("gate"),
            "excluded": out["provenance"].get("excluded_non_compilable"),
        },
    }
