"""API integration tests: /health, /ingest/file, /sources (A1.5)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.db import Store


def make_app(tmp_path: Path) -> TestClient:
    store = Store(str(tmp_path / "api-test.db"))
    return TestClient(create_app(store=store))


WHATSAPP_SAMPLE = "12/03/2026, 21:45 - Asha: cafe at 6?\n12/03/2026, 21:46 - Sam: yes see you there"


def test_ingest_whatsapp_txt_then_sources(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    resp = client.post(
        "/ingest/file",
        files={"file": ("trip.txt", WHATSAPP_SAMPLE.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["duplicates"] == 0
    conv_id = data["conversation_id"]

    sources = client.get("/sources").json()["conversations"]
    assert len(sources) == 1
    assert sources[0]["id"] == conv_id
    assert sources[0]["platform"] == "whatsapp"
    assert sources[0]["message_count"] == 2


def test_reimport_adds_no_duplicates(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    payload = {"file": ("trip.txt", WHATSAPP_SAMPLE.encode("utf-8"), "text/plain")}
    first = client.post("/ingest/file", files=payload).json()
    second = client.post("/ingest/file", files=payload).json()
    assert second["imported"] == 0
    assert second["duplicates"] == 2
    assert second["conversation_id"] == first["conversation_id"]


def test_ingest_discord_json(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    body = {
        "channel": {"name": "cricket"},
        "messages": [
            {
                "id": "1",
                "timestamp": "2026-01-01T10:00:00Z",
                "author": {"name": "Priya"},
                "content": "hi",
            }
        ],
    }
    resp = client.post(
        "/ingest/file",
        files={"file": ("cricket.json", json.dumps(body).encode(), "application/json")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1


def test_ingest_unsupported_file(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    resp = client.post(
        "/ingest/file", files={"file": ("x.json", b'{"hello": 1}', "application/json")}
    )
    assert resp.status_code == 400


def test_health(tmp_path: Path) -> None:
    client = make_app(tmp_path)
    assert client.get("/health").json()["status"] == "ok"
