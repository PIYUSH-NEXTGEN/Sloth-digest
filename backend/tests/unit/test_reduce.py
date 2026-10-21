"""Reduce tests: single-chunk shortcut, reduce prompt path, needs-you merge."""

import json
from datetime import datetime

import pytest

from app.ingest.base import build_message
from app.llm.client import FakeLLMClient
from app.models import Message, Platform, Window
from app.pipeline.extract import ChunkExtract
from app.pipeline.reduce import (
    ReduceResult,
    build_group_digest,
    build_reduce_prompt,
    parse_reduce_json,
    reduce_extract,
)
from app.pipeline.score import ScoringConfig

WINDOW = Window(start=datetime(2026, 3, 13, 20, 0), end=datetime(2026, 3, 13, 23, 0))


def messages() -> list[Message]:
    out = []
    for i in range(4):
        out.append(
            build_message(
                platform="whatsapp",
                conversation_id="g1",
                seq=i + 1,
                sender=["Ishita", "Sam", "Ishita", "Aman"][i],
                timestamp=datetime(2026, 3, 13, 21, i),
                text=[
                    "venue park tomorrow",
                    "Priya you in?",
                    "actually make it 7",
                    "lol banter meme",
                ][i],
            )
        )
    return out


def extract(decision: bool = True) -> ChunkExtract:
    return ChunkExtract.model_validate(
        {
            "topics": ["venue"],
            "decisions": (
                [{"text": "Venue: park", "message_ids": ["whatsapp:g1:000003"]}] if decision else []
            ),
            "questions_for_user": [{"message_id": "whatsapp:g1:000002", "question": "you in?"}],
            "deadlines": [],
            "per_person": [{"name": "Ishita", "points": ["picked park"]}],
        }
    )


CONFIG = ScoringConfig(user_names=["Priya"], vip_people=["Aman"])


@pytest.mark.asyncio
async def test_single_chunk_skips_reduce_prompt() -> None:
    client = FakeLLMClient([])  # dry: would raise if a prompt was sent
    result, used = await reduce_extract(
        client,
        extracts=[extract()],
        conversation_name="Trip",
        window=WINDOW,
    )
    assert used is False
    assert result.tldr
    assert result.decisions[0].text == "Venue: park"
    assert client.calls == []


@pytest.mark.asyncio
async def test_multi_chunk_uses_reduce_prompt_and_dedupes() -> None:
    canned = {
        "tldr": "Venue settled: park, 7pm.",
        "topics": ["venue"],
        "decisions": [{"text": "Venue: park (later 7pm)", "message_ids": ["whatsapp:g1:000003"]}],
        "deadlines": [],
        "per_person": [{"name": "Ishita", "points": ["picked park"]}],
    }
    client = FakeLLMClient([json.dumps(canned)])
    result, used = await reduce_extract(
        client,
        extracts=[extract(), extract(decision=False)],
        conversation_name="Trip",
        window=WINDOW,
    )
    assert used is True
    assert result.tldr == "Venue settled: park, 7pm."


def test_reduce_prompt_strict_keys() -> None:
    with pytest.raises(ValueError, match="unexpected reduce keys"):
        parse_reduce_json('{"tldr": "x", "bananza": true}')
    with pytest.raises(ValueError, match="missing tldr"):
        parse_reduce_json('{"topics": []}')


def test_reduce_prompt_contains_summaries() -> None:
    prompt = build_reduce_prompt(conversation_name="Trip", window=WINDOW, extracts=[extract()])
    assert "# Reduce chunk extracts" in prompt
    assert '"conversation": "Trip"' in prompt
    assert "Venue: park" in prompt
    assert "questions_for_user" not in prompt  # hidden from reduce per prompt rules


def test_build_group_digest_needs_you_and_skipped() -> None:
    result = ReduceResult.model_validate(
        {
            "tldr": "topic banter",
            "topics": ["venue"],
            "decisions": extract().model_dump().get("decisions", []),
        }
    )
    dig = build_group_digest(
        conversation_id="g1",
        platform=Platform.WHATSAPP,
        name="Trip",
        messages=messages(),
        extracts=[extract()],
        window=WINDOW,
        scoring_config=CONFIG,
        result=result,
    )
    assert dig.message_count == 4
    assert dig.needs_you, "question to Priya must be surfaced"
    top = dig.needs_you[0]
    assert top.message_id == "whatsapp:g1:000002"
    assert top.from_ == "Sam"  # rebuilt from store, never the LLM
    assert top.suggested_reply  # draft attached, but it is only a suggestion
    # ids referenced: 000003 (decision), 000002 (question). 000001 & 00004
    # (plain statement + banter) are skipped -> 2
    assert dig.skipped_count == 2
    assert dig.tldr == "topic banter"
