"""Optional streaming helpers for LLM providers that support chunked output."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from app.config.settings import get_settings
from app.llm.base import LLMProvider, TaskKind
from app.llm.router import get_provider


def stream_text(prompt: str, context: Any = None, *, task: TaskKind | str | None = None) -> Iterator[str]:
    """Yield text chunks. Falls back to a single full generate() if streaming is unavailable."""
    provider = get_provider(task)
    streamer = getattr(provider, "stream", None)
    if callable(streamer):
        yield from streamer(prompt, context, task=task)
        return
    # Fallback: one-shot generation split into coarse chunks for progressive UI.
    text = provider.generate(prompt, context, task=task)
    if not text:
        return
    step = max(40, len(text) // 12)
    for index in range(0, len(text), step):
        yield text[index : index + step]


def openai_stream(prompt: str, context: Any = None, *, model: str | None = None) -> Iterator[str]:
    """Native OpenAI SSE streaming when configured."""
    settings = get_settings()
    if not settings.openai_api_key.strip():
        raise RuntimeError("OpenAI API key is not configured")
    import json

    context_text = ""
    if context:
        context_text = "\nContext:\n" + json.dumps(context, default=str)[:4000]
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model or settings.openai_model,
        "messages": [{"role": "user", "content": f"{prompt}{context_text}"}],
        "temperature": 0.4,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.stream("POST", url, headers=headers, json=payload, timeout=120.0) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                payload_obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = ((payload_obj.get("choices") or [{}])[0].get("delta") or {}).get("content")
            if delta:
                yield delta
