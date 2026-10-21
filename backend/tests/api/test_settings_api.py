"""Settings endpoint tests (A3.4): GET view, PUT partial update persisted."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.client import FakeLLMClient
from app.main import create_app
from app.store.db import Store
from app.store.user_settings import UserSettings


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SLOTH_DB_PATH", str(tmp_path / "sloth.db"))
    monkeypatch.setenv("SLOTH_DROP_FOLDER", str(tmp_path / "drop"))
    return Settings()


def make_client(settings: Settings) -> TestClient:
    app = create_app(store=Store(settings.db_path), llm=FakeLLMClient([]), settings=settings)
    return TestClient(app)


def test_get_returns_env_defaults(env: Settings) -> None:
    with make_client(env) as client:
        response = client.get("/settings")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"user_names", "vip_people", "keywords", "digest_time", "model"}
    assert body["model"] == env.model


def test_put_partial_update_and_persistence(env: Settings, tmp_path: Path) -> None:
    with make_client(env) as client:
        updated = client.put(
            "/settings",
            json={"user_names": ["Piyush", "piyuu"], "keywords": ["assignment"]},
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["user_names"] == ["Piyush", "piyuu"]
        assert body["digest_time"] == env.digest_time  # untouched field kept

        fetched = client.get("/settings").json()
        assert fetched["user_names"] == ["Piyush", "piyuu"]

    overrides_path = tmp_path / "settings.json"
    assert overrides_path.exists()
    user_settings = UserSettings(env, overrides_path)
    assert user_settings.view()["model"] == env.model
    assert user_settings.view()["user_names"] == ["Piyush", "piyuu"]


def test_put_unknown_fields_ignored(env: Settings) -> None:
    with make_client(env) as client:
        response = client.put("/settings", json={"rogue": "x", "model": "gemma3:2b"})
    assert response.status_code == 200
    assert response.json()["model"] == "gemma3:2b"
    data = json.loads(Path(env.db_path).with_name("settings.json").read_text(encoding="utf-8"))
    assert "rogue" not in data


def test_put_bad_digest_time_rejected(env: Settings) -> None:
    with make_client(env) as client:
        response = client.put("/settings", json={"digest_time": "06:00pm"})
    assert response.status_code == 422


def test_digest_run_uses_updated_settings(env: Settings) -> None:
    from app.ingest.base import build_message

    with make_client(env) as client:
        client.put("/settings", json={"user_names": ["Ishita"]})
        store = Store(env.db_path)
        store.upsert_conversation("g1", "whatsapp", "crew")
        start = datetime.now(UTC) - timedelta(hours=2)
        msgs = [
            build_message(
                platform="whatsapp",
                conversation_id="g1",
                seq=i + 1,
                sender=["Sam", "Ishita"][i % 2],
                timestamp=start + timedelta(minutes=i),
                text=["Ishita hello there", "plain banter"][i % 2],
            )
            for i in range(4)
        ]
        store.import_messages("g1", "whatsapp", msgs)
        store.close()

        extract = json.dumps(
            {
                "topics": [],
                "decisions": [],
                "questions_for_user": [],
                "deadlines": [],
                "per_person": [],
            }
        )
        app = create_app(store=Store(env.db_path), llm=FakeLLMClient([extract]), settings=env)
        with TestClient(app) as client2:
            response = client2.post("/digest/run", json={})
            assert response.status_code == 202
            digest = client2.get(f"/digest/{response.json()['digest_id']}").json()
            summaries = [i["summary"] for i in digest["groups"][0]["needs_you"]]
            assert any("Ishita" in s for s in summaries)
