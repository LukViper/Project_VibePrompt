"""LLM provider interface with task-aware generation."""

from __future__ import annotations

from enum import Enum
from typing import Any


class TaskKind(str, Enum):
    CHAT = "chat"
    EXTRACTION = "extraction"
    IDEATION = "ideation"
    RESEARCH = "research"
    ARCHITECTURE = "architecture"
    GRILL = "grill"
    COMPILE = "compile"
    VALIDATION = "validation"


class LLMProvider:
    name = "base"

    def generate(self, prompt, context, *, task: TaskKind | str | None = None):
        raise NotImplementedError

    def generate_structured(self, prompt, schema: dict[str, Any], context=None, *, task: TaskKind | str | None = None):
        """Ask for JSON matching schema. Subclasses should validate before return."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        return False
