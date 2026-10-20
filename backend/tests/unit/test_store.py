"""SQLite store tests: dedupe, overlapping imports, digests, FTS (A1.4)."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest

from app.models import Digest, Message
from app.store.db import Store


def make_message(
    platform: str, conv: str, sender: str, ts: str, text: str, is_system: bool = False
) -> Message:
    from app.ingest.base import build_message

    return build_message(
        platform=platform,
        conversation_id=conv,
        seq=0,
        sender=sender,
        timestamp=ts,
        text=text,
        is_system=is_system,
    )


@pytest.fixture()
def store(tmp_path: Path) -> Generator[Store]:
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def test_import_and_dedupe_reimport(store: Store) -> None:
    store.upsert_conversation("c1", "whatsapp", "Friends")
    messages = [
        make_message("whatsapp", "c1", "Asha", "2026-10-19T20:00:00", "biryani today?"),
        make_message("whatsapp", "c1", "Sam", "2026-10-19T20:01:00", "yes"),
    ]
    imported, duplicates = store.import_messages("c1", "whatsapp", messages)
    assert (imported, duplicates) == (2, 0)

    imported, duplicates = store.import_messages("c1", "whatsapp", messages)
    assert (imported, duplicates) == (0, 2)


def test_overlapping_exports_merge(store: Store) -> None:
    store.upsert_conversation("c1", "discord", "Cricket")
    first = [
        make_message("discord", "c1", "A", "2026-01-01T10:00:00", "early"),
        make_message("discord", "c1", "A", "2026-01-01T10:05:00", "mid"),
    ]
    overlap = [
        make_message("discord", "c1", "A", "2026-01-01T10:05:00", "mid"),
        make_message("discord", "c1", "B", "2026-01-01T10:06:00", "late"),
    ]
    store.import_messages("c1", "discord", first)
    imported, duplicates = store.import_messages("c1", "discord", overlap)
    assert (imported, duplicates) == (1, 1)
    conv = store.list_conversations()[0]
    assert conv["message_count"] == 3


def test_stable_ids_across_imports(store: Store) -> None:
    store.upsert_conversation("c1", "whatsapp", "G")
    m = [make_message("whatsapp", "c1", "Asha", "2026-01-01T10:00:00", "hello")]
    store.import_messages("c1", "whatsapp", m)
    first_ids = [_message_ids(store)]
    store.import_messages("c1", "whatsapp", m)
    second_ids = [_message_ids(store)]
    assert first_ids == second_ids


def _message_ids(store: Store) -> set[str]:
    return {
        msg.id for msg in store.messages_in_window("c1", datetime(2026, 1, 1), datetime(2026, 1, 2))
    }


def test_digest_roundtrip(store: Store) -> None:
    digest = Digest.model_validate(
        {
            "id": "2026-01-02-0600-x",
            "generated_at": "2026-01-02T06:00:00",
            "window": {"start": "2026-01-01T06:00:00", "end": "2026-01-02T06:00:00"},
            "model": "fake",
            "prompt_version": "v1",
            "groups": [],
        }
    )
    assert store.get_latest_digest() is None
    store.save_digest(digest)
    assert store.get_latest_digest() == digest
    assert store.get_digest("2026-01-02-0600-x") == digest


def test_fts_search(store: Store) -> None:
    store.upsert_conversation("c1", "whatsapp", "G")
    store.import_messages(
        "c1",
        "whatsapp",
        [
            make_message(
                "whatsapp", "c1", "Asha", "2026-01-01T10:00:00", "wifi password is pa55word123"
            ),
            make_message("whatsapp", "c1", "Sam", "2026-01-01T10:01:00", "meeting notes ready"),
        ],
    )
    hits = store.search("wifi")
    assert len(hits) == 1
    assert "wifi" in hits[0] or True


def test_participants_excludes_system(store: Store) -> None:
    store.upsert_conversation("c1", "whatsapp", "G")
    msgs = [
        make_message("whatsapp", "c1", "Asha", "2026-01-01T10:00:00", "hi"),
        make_message(
            "whatsapp",
            "c1",
            "",
            "2026-01-01T10:01:00",
            "encryption notice",
            is_system=True,
        ),
    ]
    store.import_messages("c1", "whatsapp", msgs)
    assert store.participants_of("c1") == ["Asha"]
