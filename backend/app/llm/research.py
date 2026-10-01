"""Research provider.

Uses Gemini with research-oriented prompting. When a dedicated grounded-search
model/API is configured, this provider is the integration point.
Findings are returned as structured dicts; callers validate and store provenance.
"""

from __future__ import annotations

from typing import Any

from app.config.settings import get_settings
from app.llm.base import LLMProvider, TaskKind
from app.llm.gemini import GeminiProvider, extract_json


class ResearchProvider(LLMProvider):
    name = "research"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._inner = GeminiProvider(
            api_key=api_key,
            model=model or settings.gemini_research_model or settings.gemini_model,
        )

    @property
    def available(self) -> bool:
        return self._inner.available

    def generate(self, prompt, context, *, task: TaskKind | str | None = None):
        research_prompt = (
            "You are a research assistant for a student software project planner.\n"
            "Prefer verifiable, commonly known facts. If you are unsure, say so.\n"
            "Do not invent paper titles, URLs, or datasets.\n\n"
            f"{prompt}"
        )
        return self._inner.generate(research_prompt, context, task=TaskKind.RESEARCH)

    def generate_structured(self, prompt, schema: dict[str, Any], context=None, *, task: TaskKind | str | None = None):
        research_prompt = (
            "You are a research assistant. Return JSON only.\n"
            "Each finding must include source text if known; use empty string if unknown.\n"
            "Never invent URLs or paper titles.\n\n"
            f"{prompt}"
        )
        return self._inner.generate_structured(research_prompt, schema, context, task=TaskKind.RESEARCH)

    def research(self, query: str, project_context: dict | None = None) -> list[dict[str, Any]]:
        """Return list of finding dicts suitable for ProjectState.research."""
        schema = {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding": {"type": "string"},
                            "source": {"type": "string"},
                            "source_type": {"type": "string"},
                            "relevance": {"type": "string"},
                            "confidence": {"type": "number"},
                            "project_impact": {"type": "string"},
                            "verification_status": {"type": "string"},
                        },
                        "required": ["finding"],
                    },
                }
            },
            "required": ["findings"],
        }
        if not self.available:
            return []
        try:
            data = self.generate_structured(
                f"Research question: {query}",
                schema,
                project_context,
                task=TaskKind.RESEARCH,
            )
        except Exception:
            return []
        findings = data.get("findings") if isinstance(data, dict) else None
        if not isinstance(findings, list):
            return []
        cleaned = []
        for item in findings:
            if not isinstance(item, dict) or not item.get("finding"):
                continue
            cleaned.append({
                "finding": str(item["finding"]),
                "source": str(item.get("source") or ""),
                "source_type": str(item.get("source_type") or "unknown"),
                "relevance": item.get("relevance"),
                "confidence": item.get("confidence"),
                "project_impact": item.get("project_impact"),
                "verification_status": str(item.get("verification_status") or "unverified"),
            })
        return cleaned
