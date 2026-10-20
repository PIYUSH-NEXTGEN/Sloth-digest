"""Prompt file loader (llm/prompts/, AGENTS.md 12).

Prompt files are versioned (``v1_extract.md``). Changing a prompt bumps its
version and re-runs eval (AGENTS.md 12 standards).
"""

from functools import lru_cache
from importlib import resources
from typing import Literal

PromptKind = Literal["extract"]


@lru_cache(maxsize=16)
def _load(kind: str, version: str) -> str:
    path = resources.files("app") / "llm" / "prompts" / f"{version}_{kind}.md"
    return path.read_text(encoding="utf-8")


def get_prompt(kind: PromptKind, version: str) -> str:
    return _load(kind, version)


PROMPT_VERSION = "v1"
