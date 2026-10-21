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
    max_tokens: int = 3200,
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
        extract = ChunkExtract.model_validate(data)
    except Exception as exc:
        raise ValueError(f"extract JSON failed validation: {exc}") from exc
    return _resolve_ids(extract, chunk)


def _resolve_ids(extract: ChunkExtract, chunk: Chunk) -> ChunkExtract:
    """Fix model-shortened ids: a unique suffix of one chunk message id resolves.

    Models keep shortening `whatsapp:conv:hash` to the hash despite rules. An
    id that matches no chunk message (or matches ambiguously) is dropped, so
    invented ids can never survive reconstruction.
    """
    known = {m.id for m in chunk.messages}
    by_suffix: dict[str, set[str]] = {}
    for message_id in known:
        for i in range(6, len(message_id) + 1):
            by_suffix.setdefault(message_id[-i:], set()).add(message_id)

    def resolve(real_ids: list[str]) -> list[str]:
        resolved: list[str] = []
        for raw_id in real_ids:
            if raw_id in known:
                resolved.append(raw_id)
            else:
                matches = by_suffix.get(raw_id, set())
                if len(matches) == 1:
                    resolved.append(matches.pop())
                elif len(matches) > 1:
                    raise ValueError(f"ambiguous message id suffix: {raw_id}")
        return list(dict.fromkeys(resolved))

    decisions = []
    for decision in extract.decisions:
        message_ids = resolve(decision.message_ids)
        if message_ids:
            decisions.append(Decision(text=decision.text, message_ids=message_ids))
    deadlines = []
    for deadline in extract.deadlines:
        message_ids = resolve(deadline.message_ids)
        if message_ids:
            deadlines.append(
                Deadline(text=deadline.text, when=deadline.when, message_ids=message_ids)
            )
    questions = [q for q in extract.questions_for_user if q.message_id in known]
    extract = extract.model_copy(
        update={
            "decisions": decisions,
            "deadlines": deadlines,
            "questions_for_user": questions,
        }
    )
    return extract
