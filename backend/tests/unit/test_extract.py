"""Extract (map) step tests: prompt building, JSON parsing, FakeLLM round-trip."""

import pytest

from app.ingest.base import build_message
from app.llm.client import FakeLLMClient
from app.models import Message
from app.pipeline.chunk import Chunk
from app.pipeline.extract import (
    build_extract_prompt,
    extract_chunk,
    format_chunk,
    parse_llm_json,
)


def build_chunk(sequence_start: int = 1) -> Chunk:
    from datetime import datetime

    messages: list[Message] = [
        build_message(
            platform="whatsapp",
            conversation_id="c1",
            seq=sequence_start + i,
            sender="Asha",
            timestamp=datetime(2026, 10, 20, 21, i),
            text="choosing venue" if i else "let's meet Saturday 6pm",
        )
        for i in range(3)
    ]
    return Chunk(messages=messages)


def test_format_chunk_lines() -> None:
    chunk = build_chunk()
    formatted = format_chunk(chunk)
    lines = formatted.splitlines()
    assert lines[0].startswith("whatsapp:c1:000001 [21:00] Asha: ")
    assert lines[1].startswith("whatsapp:c1:000002 [21:01]")


def test_parse_llm_json_code_fence_and_prose() -> None:
    assert parse_llm_json('{"topics": []}') == {"topics": []}
    assert parse_llm_json('```json\n{"topics": ["a"]}\n```') == {"topics": ["a"]}
    assert parse_llm_json('Sure! here you go:\n{"topics": ["a"]} bye') == {"topics": ["a"]}
    with pytest.raises(ValueError):
        parse_llm_json("no json here")


@pytest.mark.asyncio
async def test_extract_chunk_with_fake_llm() -> None:
    canned = (
        '{"topics": ["venue"], "decisions": [{"text": "Sat 7pm",'
        ' "message_ids": ["whatsapp:c1:000002"]}], "questions_for_user": [],'
        ' "deadlines": [], "per_person": [{"name": "Asha", "points": ["proposed 6pm"]}]}'
    )
    client = FakeLLMClient([canned])
    result = await extract_chunk(client, build_chunk())
    assert result.topics == ["venue"]
    assert result.decisions[0].text == "Sat 7pm"
    assert result.per_person[0].name == "Asha"
    assert client.calls[0]["prompt"].startswith("# Extract one chat chunk")


@pytest.mark.asyncio
async def test_extract_chunk_rejects_bad_output() -> None:
    client = FakeLLMClient(["not json"])
    with pytest.raises(ValueError, match="unparseable"):
        await extract_chunk(client, build_chunk())

    client = FakeLLMClient(['{"rogue_key": 1}'])
    with pytest.raises(ValueError, match="unexpected extract keys"):
        await extract_chunk(client, build_chunk())


def test_prompt_references_chunk() -> None:
    built = build_extract_prompt(build_chunk())
    assert "# Extract one chat chunk (prompt v1)" in built
    assert "whatsapp:c1:000001" in built
