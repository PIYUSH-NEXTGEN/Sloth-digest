"""Digest endpoint tests (contract: openapi.yaml /digest/*). Uses FakeLLMClient."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.llm.client import FakeLLMClient
from app.main import create_app
from app.store.db import Store


@pytest.fixture
def seeded(tmp_path: Path) -> Store:
    store = Store(str(tmp_path / "digest.db"))
    from app.ingest.base import build_message
    from app.models import Message

    start = datetime.now(UTC) - timedelta(hours=2)
    store.upsert_conversation("g1", "whatsapp", "Trip crew")
    msgs: list[Message] = []
    for i in range(4):
        msgs.append(
            build_message(
                platform="whatsapp",
                conversation_id="g1",
                seq=i + 1,
                sender=["Ishita", "Sam"][i % 2],
                timestamp=start + timedelta(minutes=i),
                text=[
                    "plan: park tomorrow, Priya are you in?",
                    "yes 7pm works",
                    "Priya bring snacks please",
                    "lol meme banter",
                ][i],
            )
        )
    store.import_messages("g1", "whatsapp", msgs)
    return store


def extract_json_decisions() -> str:
    return json.dumps(
        {
            "topics": ["outings"],
            "decisions": [],
            "questions_for_user": [],
            "deadlines": [],
            "per_person": [],
        }
    )


def fake_llm_with_reduce() -> FakeLLMClient:
    reduce_out = json.dumps(
        {"tldr": "Trip planning and snacks.", "decisions": [], "deadlines": [], "per_person": []}
    )
    return FakeLLMClient([extract_json_decisions(), reduce_out])


def make_client(store: Store, llm: FakeLLMClient) -> TestClient:
    app = create_app(store=store, llm=llm)
    # tests must not create real Ollama connections
    return TestClient(app, raise_server_exceptions=True)


def test_run_returns_202_with_digest_id(seeded: Store) -> None:
    with make_client(seeded, fake_llm_with_reduce()) as client:
        response = client.post("/digest/run", json={})
    body = response.json()
    assert response.status_code == 202
    assert set(body) == {"digest_id"}
    assert body["digest_id"].startswith("digest-")


def test_run_persists_and_get_by_id_roundtrip(seeded: Store) -> None:
    with make_client(seeded, fake_llm_with_reduce()) as client:
        digest_id = client.post("/digest/run", json={}).json()["digest_id"]
        fetched = client.get(f"/digest/{digest_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == digest_id
        assert fetched.json()["groups"][0]["name"] == "Trip crew"
        assert fetched.json()["prompt_version"] == "v1"
        unknown = client.get("/digest/nope")
        assert unknown.status_code == 404


def test_no_messages_in_window_is_400(seeded: Store) -> None:
    # since in the future excludes every stored message
    body = {"since": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}
    with make_client(seeded, fake_llm_with_reduce()) as client:
        response = client.post("/digest/run", json=body)
    assert response.status_code == 400
    assert "nothing to digest" in response.json()["detail"]


def test_latest_digest_404_then_200(seeded: Store) -> None:
    with make_client(seeded, fake_llm_with_reduce()) as client:
        assert client.get("/digest/latest").status_code == 404
        client.post("/digest/run", json={})
        latest = client.get("/digest/latest")
        assert latest.status_code == 200
        assert latest.json()["groups"][0]["conversation_id"] == "g1"


def test_run_needs_you_surface_and_attribution(seeded: Store) -> None:
    with make_client(seeded, fake_llm_with_reduce()) as client:
        digest_id = client.post("/digest/run", json={}).json()["digest_id"]
        digest = client.get(f"/digest/{digest_id}").json()
    group = digest["groups"][0]
    assert group["needs_you"], "messages mentioning Priya must surface"
    for item in group["needs_you"]:
        assert item["from"] in {"Ishita", "Sam"}
        assert item["message_id"].startswith("whatsapp:g1:")
