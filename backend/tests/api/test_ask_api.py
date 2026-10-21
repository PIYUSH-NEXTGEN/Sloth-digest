"""A5.1 ask tests: hybrid retrieval, citations, endpoint contract."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.ingest.base import build_message
from app.llm.client import FakeLLMClient
from app.main import create_app
from app.pipeline.ask import answer_question, extract_citations, format_context
from app.retrieval.embeddings import FakeEmbedder, ensure_embeddings
from app.store.db import Store


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(str(tmp_path / "ask.db"))
    s.upsert_conversation("g1", "whatsapp", "crew")
    start = datetime.now(UTC) - timedelta(hours=3)
    msgs = [
        build_message(
            platform="whatsapp",
            conversation_id="g1",
            seq=i + 1,
            sender=["Riya", "Ishita", "Sam", "Aman"][i % 4],
            timestamp=start + timedelta(minutes=i),
            text=[
                "venue decided: city park gate 3 Saturday 7pm",
                "who brings music speakers, bluetooth only",
                "Priya you driving or taking the bus to the gate",
                "meme banter lol nothing here",
            ][i],
        )
        for i in range(4)
    ]
    s.import_messages("g1", "whatsapp", msgs)
    yield s
    s.close()


def test_format_context_lines(store: Store) -> None:
    msgs = store.all_messages()
    context = format_context(msgs)
    lines = context.splitlines()
    assert all(line.startswith("whatsapp:g1:") for line in lines)
    assert any("Riya:" in line for line in lines)


def test_extract_citations_only_uses_context_ids() -> None:
    available = {"whatsapp:g1:000001"}
    text = "venue [whatsapp:g1:000001] plus fake [discord:x:999999]"
    assert extract_citations(text, available) == ["whatsapp:g1:000001"]


def test_ensure_embeddings_idempotent(store: Store) -> None:
    embedder = FakeEmbedder()

    async def run() -> tuple[int, int]:
        first = await ensure_embeddings(store, embedder, batch_limit=100)
        second = await ensure_embeddings(store, embedder, batch_limit=100)
        return first, second

    first, second = asyncio.run(run())
    assert first == 4
    assert second == 0


@pytest.mark.asyncio
async def test_answer_question_with_fake_llm(store: Store) -> None:
    embedder = FakeEmbedder()
    ids = [m.id for m in store.all_messages(10)]
    answer_text = (
        f"Riya asked for speakers [{ids[0]}]; venue is the park {ids[2]} "
        f"and Priya was asked about the bus [{ids[1]}]"
    )
    client = FakeLLMClient([answer_text])
    result = await answer_question(store, embedder, client, "who brings the speakers?")
    assert "Riya" in result.text
    assert result.sources, "cited ids must be returned as sources"
    all_ids = {m.id for m in store.all_messages()}
    assert set(result.sources).issubset(all_ids)


@pytest.mark.asyncio
async def test_answer_no_context(store: Store) -> None:
    embedder = FakeEmbedder()
    client = FakeLLMClient([])
    result = await answer_question(store, embedder, client, "quantum physics help")
    assert result.text == "No messages in your chats cover this."
    assert result.sources == []


def test_ask_endpoint_contract(store: Store) -> None:
    app = create_app(store=store, llm=FakeLLMClient([], default="All good"), settings=Settings())
    app.state.embedder = FakeEmbedder()
    with TestClient(app) as client:
        response = client.post("/ask", json={"question": "who drives"})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"answer", "sources"}
        assert isinstance(body["sources"], list)


def test_ask_endpoint_rejects_empty_question(store: Store) -> None:
    store.upsert_conversation("g1", "whatsapp", "crew")
    app = create_app(store=store, llm=FakeLLMClient([]))
    with TestClient(app) as client:
        response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422
