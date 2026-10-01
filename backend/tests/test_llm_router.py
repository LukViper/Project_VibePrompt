"""Phase 2 — LLM routing and provider interfaces."""

from app.llm.base import TaskKind
from app.llm.gemini import GeminiProvider
from app.llm.research import ResearchProvider
from app.llm.router import TASK_ROUTE, get_provider, resolve_model


def test_task_routes_cover_all_kinds():
    for kind in TaskKind:
        assert kind in TASK_ROUTE


def test_resolve_model_uses_configured_slots(monkeypatch):
    from app.config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_FAST_MODEL", "fast-model")
    monkeypatch.setenv("GEMINI_REASONING_MODEL", "reason-model")
    monkeypatch.setenv("GEMINI_RESEARCH_MODEL", "research-model")
    settings_mod.get_settings.cache_clear()
    assert resolve_model(TaskKind.CHAT) == "fast-model"
    assert resolve_model(TaskKind.EXTRACTION) == "fast-model"
    assert resolve_model(TaskKind.GRILL) == "reason-model"
    assert resolve_model(TaskKind.ARCHITECTURE) == "reason-model"
    assert resolve_model(TaskKind.RESEARCH) == "research-model"
    settings_mod.get_settings.cache_clear()


def test_get_provider_research_returns_research_provider():
    provider = get_provider(TaskKind.RESEARCH)
    assert isinstance(provider, ResearchProvider)
    assert provider.name == "research"


def test_get_provider_chat_returns_configured_vendor():
    provider = get_provider(TaskKind.CHAT)
    assert provider.name in {"gemini", "openai"}
    assert provider.__class__.__name__ in {"GeminiProvider", "OpenAIProvider"}


def test_generate_structured_requires_key():
    provider = GeminiProvider(api_key="")
    assert provider.available is False
    try:
        provider.generate_structured("hi", {"type": "object"})
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "not configured" in str(exc)
