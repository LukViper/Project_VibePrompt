"""Model routing by task complexity and configured provider.

Callers use the router — never hard-code a single vendor throughout the app.
"""

from __future__ import annotations

from app.config.settings import get_settings
from app.llm.base import LLMProvider, TaskKind
from app.llm.gemini import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.research import ResearchProvider


TASK_ROUTE = {
    TaskKind.CHAT: "fast",
    TaskKind.EXTRACTION: "fast",
    TaskKind.IDEATION: "fast",
    TaskKind.GRILL: "reasoning",
    TaskKind.ARCHITECTURE: "reasoning",
    TaskKind.COMPILE: "reasoning",
    TaskKind.VALIDATION: "reasoning",
    TaskKind.RESEARCH: "research",
}


def resolve_model(task: TaskKind | str | None) -> str:
    settings = get_settings()
    provider_name = _selected_provider_name()
    if provider_name == "openai":
        return settings.openai_model
    if task is None:
        return settings.gemini_model
    kind = TaskKind(task) if isinstance(task, str) else task
    route = TASK_ROUTE.get(kind, "fast")
    if route == "research":
        return settings.gemini_research_model or settings.gemini_model
    if route == "reasoning":
        return settings.gemini_reasoning_model or settings.gemini_model
    return settings.gemini_fast_model or settings.gemini_model


def _selected_provider_name() -> str:
    settings = get_settings()
    choice = (settings.llm_provider or "auto").strip().lower()
    if choice == "openai":
        return "openai" if settings.openai_configured else "gemini"
    if choice == "gemini":
        return "gemini"
    # auto: prefer Gemini when configured, else OpenAI
    if settings.gemini_configured:
        return "gemini"
    if settings.openai_configured:
        return "openai"
    return "gemini"


def get_provider(task: TaskKind | str | None = None) -> LLMProvider:
    kind = None
    if task is not None:
        kind = TaskKind(task) if isinstance(task, str) else task
    if kind == TaskKind.RESEARCH:
        # ResearchProvider wraps Gemini research path; still usable when Gemini key present.
        # If only OpenAI is configured, fall back to OpenAIProvider for research prompts.
        settings = get_settings()
        if settings.gemini_configured or _selected_provider_name() == "gemini":
            return ResearchProvider(model=resolve_model(kind))
        return OpenAIProvider(model=resolve_model(kind))
    if _selected_provider_name() == "openai":
        return OpenAIProvider(model=resolve_model(kind))
    return GeminiProvider(model=resolve_model(kind))


def get_chat_provider() -> LLMProvider:
    return get_provider(TaskKind.CHAT)


def provider_status() -> dict:
    settings = get_settings()
    return {
        "active": _selected_provider_name(),
        "llm_provider_setting": settings.llm_provider,
        "gemini_configured": settings.gemini_configured,
        "openai_configured": settings.openai_configured,
    }
