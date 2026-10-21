"""A4.1 tests: scrubbed Sentry events are metadata-only, zero chat text."""

import pytest

from app.observability.sentry import init_sentry, scrub_event

LEAKS = (
    "let's meet Saturday 6pm",
    "Priya owes the group zoodles",
    "send booking amount by Friday",
)


def seeded_event() -> dict[str, object]:
    return {
        "event_id": "abc123",
        "level": "error",
        "timestamp": 1761067200.0,
        "message": f"digest included: {LEAKS[0]}",
        "logentry": {"message": f"llm saw {LEAKS[1]}", "params": [LEAKS[2]]},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": f"bad chunk containing {LEAKS[0]}",
                    "module": "app.pipeline.extract",
                }
            ]
        },
        "breadcrumbs": {
            "values": [
                {"type": "default", "category": "query", "message": f"SELECT {LEAKS[1]}"},
                {"type": "http", "category": "http", "level": "info"},
            ]
        },
        "request": {
            "url": "http://localhost:8000/digest/run",
            "method": "POST",
            "query_string": f"q={LEAKS[2]}",
            "data": {"body": LEAKS[0]},
            "cookies": {"session": "sid123"},
        },
        "extra": {"digest_text": LEAKS[0], "message_count": 506},
        "tags": {"conversation_id": "g1", "platform": "whatsapp"},
    }


def assert_no_leaks(event: dict[str, object]) -> None:
    for leak in LEAKS:
        assert leak not in str(event), f"chat text leaked: {leak}"


def test_scrub_keeps_metadata_strips_text() -> None:
    out = scrub_event(seeded_event(), hint={})
    assert_no_leaks(out)
    assert out["exception"]["values"][0]["type"] == "ValueError"
    assert out["exception"]["values"][0]["module"] == "app.pipeline.extract"
    assert out["tags"]["conversation_id"] == "g1"
    assert out["request"]["url"] == "http://localhost:8000/digest/run"
    assert out["request"]["method"] == "POST"
    crumbs = out["breadcrumbs"]["values"]
    assert crumbs[1] == {"type": "http", "category": "http", "level": "info"}
    assert out["level"] == "error"
    assert out["timestamp"] == 1761067200.0


def test_scrub_is_idempotent_on_clean_events() -> None:
    clean = {"level": "info", "tags": {"model": "gemma3:4b"}}
    assert scrub_event(clean, {}) == clean


def test_init_off_by_default() -> None:
    class FakeSettings:
        sentry_enabled = False
        sentry_dsn = ""

    assert init_sentry(FakeSettings()) is False


def test_init_with_dsn_reports_active(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("sentry_sdk")

    calls: list[str] = []

    def fake_init(**kwargs: object) -> None:
        calls.append(str(kwargs.get("dsn")))

    monkeypatch.setattr("sentry_sdk.init", fake_init)

    class FakeSettings:
        sentry_enabled = True
        sentry_dsn = "https://test@example.com/1"

    assert init_sentry(FakeSettings()) is True
    assert calls and calls[0].startswith("https://")
