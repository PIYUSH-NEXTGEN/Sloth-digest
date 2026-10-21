"""A5.x real-model findings: id-suffix resolution in extract + needs-you dedupe.

Gemma shortens `whatsapp:conv:hash` to the hash part despite prompt rules;
extract_chunk must resolve unique suffixes to full ids (never invent) and
needs-you must collapse repeated near-identical asks.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.ingest.base import build_message
from app.llm.client import FakeLLMClient
from app.models import Message, Platform, Window
from app.pipeline.extract import Decision, QuestionForUser, extract_chunk
from app.pipeline.reduce import build_group_digest
from app.pipeline.score import ScoringConfig


def _conv(n: int = 4) -> list[Message]:
    return [
        build_message(
            platform="whatsapp",
            conversation_id="c1",
            seq=i + 1,
            sender="Priya" if i % 2 else "Riya",
            timestamp=datetime(2026, 10, 20, 8, 0, tzinfo=UTC) + timedelta(minutes=i),
            text=[
                "who brings the speakers on Saturday",
                "meeting moves to Saturday 7pm",
                "send the booking amount by Friday",
                "banter only nothing here",
            ][i],
        )
        for i in range(n)
    ]


def test_extract_resolves_shortened_ids() -> None:
    from app.pipeline.chunk import Chunk

    messages = _conv(3)
    full_ids = {m.id.rsplit(":", 1)[-1]: m.id for m in messages}
    speaker_hash = full_ids.get(messages[0].id.rsplit(":", 1)[-1])
    # model cites only the hash part
    shortened = messages[0].id.rsplit(":", 1)[-1]
    raw = (
        '{"topics": ["party"], "decisions": [{"text": "meeting at 7", '
        f'"message_ids": ["{shortened}"]}}], "questions_for_user": [], "deadlines": []}}'
    )
    client = FakeLLMClient([raw])
    result = asyncio.run(extract_chunk(client, Chunk(messages)))
    assert result.decisions[0].message_ids == [messages[0].id]
    assert speaker_hash  # sanity: map built from real ids


def test_extract_drops_invented_ids() -> None:
    from app.pipeline.chunk import Chunk

    messages = _conv(3)
    raw = (
        '{"topics": [], "decisions": [{"text": "vote rig call", '
        '"message_ids": ["zz0000zzzz"]}], "questions_for_user": [], "deadlines": []}'
    )
    client = FakeLLMClient([raw])
    result = asyncio.run(extract_chunk(client, Chunk(messages)))
    assert result.decisions == []


@pytest.mark.asyncio
async def test_need_you_dedupes_identical_summaries() -> None:
    # five near-identical dupe questions; only the first should stay
    messages = _conv(1) * 5
    unique_message = build_message(
        platform="whatsapp",
        conversation_id="c1",
        seq=99,
        sender="Riya",
        timestamp=datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
        text="@Riya can you drive on Saturday or take the bus?",
    )
    messages.append(unique_message)
    questions = [
        QuestionForUser(
            message_id=unique_message.id, question="can you drive on Saturday or take the bus?"
        )
    ]
    extract = type(
        "E",
        (),
        {
            "topics": [],
            "decisions": [Decision(text="meeting at 7", message_ids=[messages[1].id])],
            "questions_for_user": questions,
            "deadlines": [],
            "per_person": [],
        },
    )()
    digest = build_group_digest(
        conversation_id="c1",
        platform=Platform.WHATSAPP,
        name="group",
        messages=messages,
        extracts=[extract],
        window=Window(start=messages[0].timestamp, end=messages[-1].timestamp),
        scoring_config=ScoringConfig(user_names=["Riya"]),
        result=type(
            "R",
            (),
            {
                "tldr": "x",
                "decisions": [],
                "deadlines": [],
                "per_person": [],
                "topics": [],
            },
        )(),
    )
    summaries = [item.summary.strip().lower() for item in digest.needs_you]
    assert len(summaries) == len(set(summaries))
