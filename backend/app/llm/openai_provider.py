"""OpenAI-compatible chat completions provider.

API key stays on the server. Works with OpenAI and compatible gateways.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config.settings import get_settings
from app.llm.base import LLMProvider, TaskKind
from app.llm.gemini import extract_json


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.openai_model
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")

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
        if not isinstance(data, (dict, list)):
            raise ValueError("Structured output was not a JSON object or array")
        return data

    def _call(self, prompt: str, context, *, json_mode: bool) -> str:
        if not self.available:
            raise RuntimeError("OpenAI API key is not configured")
        context_text = ""
        if context:
            context_text = "\nContext:\n" + json.dumps(context, default=str)[:4000]
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": f"{prompt}{context_text}"}],
            "temperature": 0.4,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI returned no choices")
        message = choices[0].get("message") or {}
        return str(message.get("content") or "").strip()
