"""Gemini provider over the public generateContent API.

The API key is read from the environment. It is never returned to Flutter.
Supports optional JSON-oriented generation for structured outputs.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.config.settings import get_settings
from app.llm.base import LLMProvider, TaskKind


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())

    def generate(self, prompt, context, *, task: TaskKind | str | None = None):
        return self._call(prompt, context, json_mode=False)

    def generate_structured(self, prompt, schema: dict[str, Any], context=None, *, task: TaskKind | str | None = None):
        schema_text = json.dumps(schema, indent=2)
        wrapped = (
            f"{prompt}\n\nReturn JSON only that matches this schema:\n{schema_text}\n"
            "Do not wrap in markdown fences."
        )
        raw = self._call(wrapped, context, json_mode=True)
        data = extract_json(raw)
        if not isinstance(data, dict) and not isinstance(data, list):
            raise ValueError("Structured output was not a JSON object or array")
        return data

    def _call(self, prompt: str, context, *, json_mode: bool) -> str:
        if not self.available:
            raise RuntimeError("Gemini API key is not configured")
        context_text = ""
        if context:
            context_text = "\nContext:\n" + json.dumps(context, default=str)[:4000]
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        generation: dict[str, Any] = {"temperature": 0.4}
        if json_mode:
            generation["responseMimeType"] = "application/json"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{prompt}{context_text}"}]}],
            "generationConfig": generation,
        }
        response = httpx.post(url, params={"key": self.api_key}, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts") or []
        return "\n".join(part.get("text", "") for part in parts).strip()


class FutureProviderA(LLMProvider):
    name = "future_a"

    def generate(self, prompt, context, *, task: TaskKind | str | None = None):
        raise NotImplementedError("FutureProviderA is an extension point and is not configured in V1")

    def generate_structured(self, prompt, schema, context=None, *, task: TaskKind | str | None = None):
        raise NotImplementedError("FutureProviderA is an extension point and is not configured in V1")


class FutureProviderB(LLMProvider):
    name = "future_b"

    def generate(self, prompt, context, *, task: TaskKind | str | None = None):
        raise NotImplementedError("FutureProviderB is an extension point and is not configured in V1")

    def generate_structured(self, prompt, schema, context=None, *, task: TaskKind | str | None = None):
        raise NotImplementedError("FutureProviderB is an extension point and is not configured in V1")


def extract_json(text: str):
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if not match:
        raise ValueError("No JSON in model output")
    return json.loads(match.group(1))


def get_provider() -> LLMProvider:
    """Backward-compatible default. Prefer app.llm.router.get_provider(task)."""
    from app.llm.router import get_provider as routed

    return routed()
