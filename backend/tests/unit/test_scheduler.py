"""Scheduler (A3.1) + delivery (A3.2) tests. No real waiting: the job is
invoked directly; cron parsing and reschedule are checked via labels."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.ingest.base import build_message
from app.ingest.watcher import DropFolderWatcher
from app.llm.client import FakeLLMClient
from app.main import create_app
from app.scheduler import DigestScheduler, parse_digest_time
from app.store.db import Store
from app.store.user_settings import UserSettings


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SLOTH_DB_PATH", str(tmp_path / "sloth.db"))
    monkeypatch.setenv("SLOTH_DROP_FOLDER", str(tmp_path / "drop"))
    return Settings()


def seed(store: Store) -> None:
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


def make_scheduler(env: Settings, digests_dir: Path) -> DigestScheduler:
    store = Store(env.db_path)
    seed(store)
    user_settings = UserSettings(env)
    user_settings.update({"user_names": ["Ishita"], "desktop_notify": False})
    watcher = DropFolderWatcher(store, env.drop_folder)
    llm = FakeLLMClient(
        [],
        default=json.dumps(
            {
                "topics": [],
                "decisions": [],
                "questions_for_user": [],
                "deadlines": [],
                "per_person": [],
            }
        ),
    )
    return DigestScheduler(store, llm, user_settings, watcher, digests_dir=str(digests_dir))


def test_parse_digest_time() -> None:
    assert parse_digest_time("06:00") == (6, 0)
    assert parse_digest_time("23:59") == (23, 59)
    with pytest.raises(ValueError):
        parse_digest_time("06:00pm")
    with pytest.raises(ValueError):
        parse_digest_time("24:00")


@pytest.mark.asyncio
async def test_scheduled_job_writes_markdown_and_html(env: Settings, tmp_path: Path) -> None:
    digests_dir = tmp_path / "digests"
    scheduler = make_scheduler(env, digests_dir)
    digest_id = await scheduler.run_scheduled_job()
    assert digest_id is not None
    files = sorted(p.name for p in digests_dir.iterdir())
    expected_date = datetime.now(UTC).date().isoformat()
    assert f"{expected_date}.md" in files
    assert f"{expected_date}.html" in files

    md = (digests_dir / f"{expected_date}.md").read_text(encoding="utf-8")
    assert "# SlothDigest -" in md
    assert "## crew (whatsapp)" in md
    assert "Ishita hello there" in md  # needs-you surfaced
    assert "Generated locally" in md

    html = (digests_dir / f"{expected_date}.html").read_text(encoding="utf-8")
    assert "<h1>SlothDigest" in html
    assert "Ishita hello there" in html
    assert "<script" not in html


@pytest.mark.asyncio
async def test_scheduled_job_nothing_to_digest(env: Settings, tmp_path: Path) -> None:
    digests_dir = tmp_path / "digests"
    scheduler = make_scheduler(env, digests_dir)
    # seeded messages are inside the last 24h, so this run still digests
    digest_id = await scheduler.run_scheduled_job()
    assert digest_id is not None
    # fresh store without messages
    empty_dir = tmp_path / "d2"
    empty_settings = env.model_copy(update={"db_path": str(tmp_path / "empty.db")})
    scheduler2 = DigestScheduler(
        Store(empty_settings.db_path),
        FakeLLMClient([]),
        UserSettings(empty_settings),
        DropFolderWatcher(Store(empty_settings.db_path), empty_settings.drop_folder),
        digests_dir=str(empty_dir),
    )
    assert await scheduler2.run_scheduled_job() is None
    assert not empty_dir.exists()


def test_reschedule_updates_label(env: Settings, tmp_path: Path) -> None:
    scheduler = make_scheduler(env, tmp_path / "d3")
    assert scheduler.schedule_label == env.digest_time
    scheduler.reschedule("07:30")
    assert scheduler.schedule_label == "07:30"
    with pytest.raises(ValueError):
        scheduler.reschedule("25:00")


def test_settings_put_reschedules_live_scheduler(env: Settings, tmp_path: Path) -> None:
    app = create_app(store=Store(env.db_path), llm=FakeLLMClient([]), settings=env)
    with TestClient(app) as client:
        response = client.put("/settings", json={"digest_time": "09:15"})
        assert response.status_code == 200
        assert response.json()["digest_time"] == "09:15"
        scheduler = app.state.digest_scheduler
        assert scheduler.schedule_label == "09:15"
        persisted = json.loads(
            Path(env.db_path).with_name("settings.json").read_text(encoding="utf-8")
        )
        assert persisted["digest_time"] == "09:15"
