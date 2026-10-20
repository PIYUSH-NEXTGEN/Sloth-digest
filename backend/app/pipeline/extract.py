"""Map step (A2.2): per-chunk structured extraction via the LLM.

The LLM returns strict JSON (see llm/prompts/v1_extract.md). This module
formats the chunk, parses + shape-checks the reply, and produces typed
``ChunkExtract`` objects. Retries and fallback live in validate.py (A2.5);
attribution is enforced later there too - the LLM only *references* message
ids and never decides senders (AGENTS.md 7.4).
"""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.llm.client import LLMClient
from app.llm.prompts import PROMPT_VERSION, get_prompt
from app.pipeline.chunk import Chunk

GENERIC_EXTRACT_KEYS = {
    "topics",
    "decisions",
    "questions_for_user",
    "deadlines",
    "per_person",
}


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=400)
    message_ids: list[str] = Field(min_length=1)


class QuestionForUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    question: str = Field(max_length=240)


class Deadline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=240)
    when: str | None = None
    message_ids: list[str] = Field(min_length=1)


class PersonPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    points: list[str] = Field(min_length=1)


class ChunkExtract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[str] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    questions_for_user: list[QuestionForUser] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    per_person: list[PersonPoint] = Field(default_factory=list)


def format_chunk(chunk: Chunk) -> str:
    """Render messages as `<id> [<HH:MM>] <sender>: <text>`."""
    lines: list[str] = []
    for message in chunk.messages:
        hhmm = message.timestamp.strftime("%H:%M")
        prefix = "[system] " if message.is_system else ""
        lines.append(f"{message.id} [{hhmm}] {prefix}{message.sender}: {message.text}")
    return "\n".join(lines)


def build_extract_prompt(chunk: Chunk, version: str = PROMPT_VERSION) -> str:
    template = get_prompt("extract", version)
    return template + "\n\n## Chunk\n" + format_chunk(chunk)


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Extract the JSON object from model output (tolerates fences/prose)."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence is not None:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("model output contained no JSON object")
        text = text[start : end + 1]
    payload: dict[str, Any] = json.loads(text)
    return payload


async def extract_chunk(
    client: LLMClient,
    chunk: Chunk,
    *,
    version: str = PROMPT_VERSION,
    temperature: float = 0.0,
    max_tokens: int = 1200,
) -> ChunkExtract:
    """Run one map step. Raises ValueError on unusable output (retry upstream)."""
    prompt = build_extract_prompt(chunk, version)
    raw = await client.complete(prompt, max_tokens=max_tokens, temperature=temperature)
    try:
        data = parse_llm_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"unparseable model output: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("model output JSON was not an object")
    unexpected = set(data) - GENERIC_EXTRACT_KEYS
    if unexpected:
        raise ValueError(f"unexpected extract keys: {sorted(unexpected)}")
    try:
        return ChunkExtract.model_validate(data)
    except Exception as exc:
        raise ValueError(f"extract JSON failed validation: {exc}") from exc
