"""Reduce step (A2.3, A2.4): merge chunk extracts into per-group digests.

Two paths:
- one chunk   -> no reduce prompt; merge deterministically,
- many chunks -> one reduce LLM call (llm/prompts/v1_reduce.md), output
  shape-checked like the map step (strict keys, no inventions).

``needs_you`` is never the LLM's job: score.py (A2.4) computes it
deterministically. Draft replies (A2.7) attach here, as suggestions only -
SlothDigest never sends anything.

``skipped_count`` counts window messages no extract referenced
(the 'Skipped (N banter messages)' line in the digest).
"""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.llm.client import LLMClient
from app.llm.prompts import PROMPT_VERSION
from app.models import (
    Deadline,
    Decision,
    GroupDigest,
    Message,
    NeedsYouItem,
    PersonPoints,
    Platform,
    Window,
)
from app.pipeline.extract import ChunkExtract, QuestionForUser, parse_llm_json
from app.pipeline.score import ScoringConfig, score_messages, suggested_reply_draft

REDUCE_KEYS = {"tldr", "topics", "decisions", "deadlines", "per_person"}


class ReduceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tldr: str = Field(default="", max_length=400)
    topics: list[str] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    per_person: list[PersonPoints] = Field(default_factory=list)


def _merge_extracts(extracts: list[ChunkExtract]) -> ReduceResult:
    decisions: dict[str, Decision] = {}
    deadlines: list[Deadline] = []
    per_person: dict[str, PersonPoints] = {}
    topics: list[str] = []
    for extract in extracts:
        topics.extend(t for t in extract.topics if t)
        for decision in extract.decisions:
            key = decision.text.strip().lower()
            existing = decisions.get(key)
            if existing is None:
                decisions[key] = Decision(
                    text=decision.text, message_ids=list(decision.message_ids)
                )
            else:
                merged_ids = existing.message_ids + [
                    mid for mid in decision.message_ids if mid not in existing.message_ids
                ]
                decisions[key] = Decision(text=decision.text, message_ids=merged_ids)
        for deadline in extract.deadlines:
            deadlines.append(
                Deadline(
                    text=deadline.text, when=deadline.when, message_ids=list(deadline.message_ids)
                )
            )
        for person in extract.per_person:
            person_existing: PersonPoints | None = per_person.get(person.name)
            if person_existing is None:
                per_person[person.name] = PersonPoints(name=person.name, points=list(person.points))
            else:
                per_person[person.name] = PersonPoints(
                    name=person.name,
                    points=person_existing.points
                    + [p for p in person.points if p not in person_existing.points],
                )
    return ReduceResult(
        topics=topics,
        decisions=list(decisions.values()),
        deadlines=deadlines,
        per_person=list(per_person.values()),
    )


def heuristic_reduce(extracts: list[ChunkExtract]) -> ReduceResult:
    """LLM-free merge (agent.md A2.5 fallback): mechanical merge + tl;dr."""
    merged = _merge_extracts(extracts)
    merged.tldr = merged.tldr or _fallback_tldr(merged)
    return merged


def _fallback_tldr(result: ReduceResult, topic_cap: int = 3) -> str:
    parts: list[str] = []
    topics = result.topics[:topic_cap]
    if topics:
        parts.append("Topics: " + ", ".join(topics))
    first_decisions = [d.text for d in result.decisions[:2]]
    if first_decisions:
        parts.append("Decided: " + " | ".join(first_decisions))
    return ". ".join(parts)[:400] or "Chat had little worth summarizing."


def _referenced_ids(extracts: list[ChunkExtract], questions: list[QuestionForUser]) -> set[str]:
    ids: set[str] = set()
    for extract in extracts:
        for decision in extract.decisions:
            ids.update(decision.message_ids)
        for deadline in extract.deadlines:
            ids.update(deadline.message_ids)
    for question in questions:
        ids.add(question.message_id)
    return ids


def build_reduce_prompt(
    *,
    conversation_name: str,
    window: Window,
    extracts: list[ChunkExtract],
    version: str = PROMPT_VERSION,
) -> str:
    summaries = [
        extract.model_dump(mode="json", exclude={"questions_for_user"}) for extract in extracts
    ]
    window_text = (
        f"{window.start.isoformat(timespec='minutes')}"
        f" .. {window.end.isoformat(timespec='minutes')}"
    )
    payload = json.dumps(
        {
            "conversation": conversation_name,
            "window": window_text,
            "chunk_summaries": summaries,
        },
        ensure_ascii=False,
        indent=2,
    )
    return get_reduce_template(version) + "\n\n## Input\n```json\n" + payload + "\n```"


def get_reduce_template(version: str) -> str:
    from importlib import resources

    path = resources.files("app") / "llm" / "prompts" / f"{version}_reduce.md"
    return path.read_text(encoding="utf-8")


def parse_reduce_json(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = parse_llm_json(raw)
    unexpected = set(data) - REDUCE_KEYS
    if unexpected:
        raise ValueError(f"unexpected reduce keys: {sorted(unexpected)}")
    if "tldr" not in data:
        raise ValueError("reduce output missing tldr")
    return data


async def reduce_extract(
    client: LLMClient,
    *,
    extracts: list[ChunkExtract],
    conversation_name: str,
    window: Window,
    max_tokens: int = 1200,
    temperature: float = 0.0,
) -> tuple[ReduceResult, bool]:
    """Returns (merged result, reduce_prompt_used). Single chunk skips the prompt."""
    if not extracts:
        return ReduceResult(tldr="No messages in this conversation."), False
    if len(extracts) == 1:
        merged = _merge_extracts(extracts)
        merged.tldr = merged.tldr or _fallback_tldr(merged)
        return merged, False
    prompt = build_reduce_prompt(
        conversation_name=conversation_name, window=window, extracts=extracts
    )
    raw = await client.complete(prompt, max_tokens=max_tokens, temperature=temperature)
    try:
        data = parse_reduce_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"unparseable reduce output: {exc}") from exc
    try:
        result = ReduceResult.model_validate(data)
    except Exception as exc:
        raise ValueError(f"reduce JSON failed validation: {exc}") from exc
    if not result.tldr:
        result = result.model_copy(update={"tldr": _fallback_tldr(result)})
    return result, True


def build_group_digest(
    *,
    conversation_id: str,
    platform: Platform,
    name: str,
    messages: list[Message],
    extracts: list[ChunkExtract],
    window: Window,
    scoring_config: ScoringConfig,
    result: ReduceResult,
) -> GroupDigest:
    """Needs-you ranking is deterministic; skipped count counts unreferenced msgs."""
    questions: list[QuestionForUser] = []
    for extract in extracts:
        questions.extend(extract.questions_for_user)
    scored = score_messages(messages, questions, scoring_config)
    needs_you: list[NeedsYouItem] = []
    for _score, item in scored[:10]:
        needs_you.append(item.model_copy(update={"suggested_reply": suggested_reply_draft(item)}))
    referenced = _referenced_ids(extracts, questions)
    skipped = sum(1 for m in messages if m.id not in referenced and not m.is_system)
    return GroupDigest(
        conversation_id=conversation_id,
        platform=platform,
        name=name,
        message_count=len(messages),
        skipped_count=skipped,
        tldr=result.tldr[:400],
        needs_you=needs_you,
        decisions=result.decisions,
        by_person=result.per_person,
        deadlines=result.deadlines,
    )
