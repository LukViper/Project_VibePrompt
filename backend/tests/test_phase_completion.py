"""Phase completion coverage: providers, summary, streaming, spec, production."""

from app.config import settings as settings_mod
from app.llm.base import TaskKind
from app.llm.openai_provider import OpenAIProvider
from app.llm.router import get_provider, provider_status, resolve_model
from app.services.analytics import track, snapshot, ALLOWED_EVENTS
from app.services.specification import SECTION_ORDER


def test_openai_provider_unavailable_without_key():
    provider = OpenAIProvider(api_key="")
    assert provider.available is False


def test_router_selects_openai_when_configured(monkeypatch):
    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    settings_mod.get_settings.cache_clear()
    assert resolve_model(TaskKind.CHAT) == "gpt-test"
    provider = get_provider(TaskKind.CHAT)
    assert isinstance(provider, OpenAIProvider)
    assert provider_status()["active"] == "openai"
    settings_mod.get_settings.cache_clear()


def test_analytics_allow_list_and_snapshot():
    before = snapshot().get("project_created", 0)
    track("project_created")
    track("not_a_real_event")
    assert "project_created" in ALLOWED_EVENTS
    assert snapshot()["project_created"] == before + 1


def test_project_summary_endpoint(client):
    created = client.post("/projects", json={"description": "NLP project, solo, five weeks, no login."})
    pid = created.json()["id"]
    summary = client.get(f"/projects/{pid}/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert "summary" in body and "narrative" in body
    assert body["summary"]["project"]


def test_stream_messages_endpoint(client):
    created = client.post("/projects", json={"description": "I need an NLP project."})
    pid = created.json()["id"]
    response = client.post(
        f"/projects/{pid}/messages/stream",
        json={"content": "Suggest detailed project ideas"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    text = response.text
    assert "event: meta" in text
    assert "event: done" in text


def test_specification_uses_master_sections(client):
    created = client.post(
        "/projects",
        json={"description": "NLP phishing detector. Alone, five weeks."},
    )
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/messages", json={"content": "Maybe an NLP-based phishing detector."})
    ideas = client.post(f"/projects/{pid}/ideas").json()
    client.post(f"/projects/{pid}/ideas/{ideas[0]['id']}/select")
    spec = client.post(f"/projects/{pid}/specification")
    assert spec.status_code == 200
    markdown = spec.json()["markdown"]
    assert "## PROJECT OBJECTIVE" in markdown
    assert "## FUNCTIONAL REQUIREMENTS" in markdown
    assert "## ACCEPTANCE CRITERIA" in markdown


def test_readyz_ok_in_development(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_health_reports_providers(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert "llm_configured" in body


def test_section_order_covers_master_spec():
    titles = [title for title, _ in SECTION_ORDER]
    assert "PROJECT OBJECTIVE" in titles
    assert "KNOWN RISKS" in titles
