"""A4.2 retry-policy tests + A4.3 narration tests (MockTransport, no network)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.delivery.narration import build_narration_script, narrate_digest
from app.models import Digest
from app.pipeline.retry import run_with_retry, temporal_enabled

NOW = datetime.now(UTC)
DIGEST = Digest.model_validate(
    {
        "id": "digest-test",
        "generated_at": NOW.isoformat(),
        "window": {
            "start": (NOW - timedelta(hours=24)).isoformat(),
            "end": NOW.isoformat(),
        },
        "model": "gemma3:4b",
        "prompt_version": "v1",
        "groups": [
            {
                "conversation_id": "g1",
                "platform": "whatsapp",
                "name": "crew",
                "message_count": 10,
                "skipped_count": 2,
                "tldr": "Trip planning settled.",
                "needs_you": [
                    {
                        "message_id": "m1",
                        "from": "Sam",
                        "summary": "drive or bus?",
                        "reason": "asked you a question",
                    }
                ],
                "decisions": [{"text": "Venue: park", "message_ids": ["m2"]}],
                "by_person": [],
                "deadlines": [{"text": "booking by Friday", "when": None, "message_ids": ["m3"]}],
            }
        ],
    }
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SLOTH_DB_PATH", str(tmp_path / "sloth.db"))
    monkeypatch.setenv("SLOTH_DROP_FOLDER", str(tmp_path / "drop"))
    return Settings()


@pytest.mark.asyncio
async def test_run_with_retry_succeeds_after_failures() -> None:
    calls = {"n": 0}

    async def job() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("bad model output")
        return "ok"

    result = await run_with_retry(job, attempts=3, base_delay=0, retry_on=(ValueError,))
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_run_with_retry_exhausts_and_raises() -> None:
    calls = {"n": 0}

    async def job() -> str:
        calls["n"] += 1
        raise ValueError("never works")

    with pytest.raises(ValueError, match="never works"):
        await run_with_retry(job, attempts=3, base_delay=0, retry_on=(ValueError,))
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_run_with_retry_respects_retry_on_filter() -> None:
    async def job() -> str:
        raise RuntimeError("not retryable")

    with pytest.raises(RuntimeError):
        await run_with_retry(job, attempts=3, base_delay=0, retry_on=(ValueError,))


@pytest.mark.parametrize(
    ("flag", "expected"),
    [(False, False)],
)
def test_temporal_disabled_by_default(flag: bool, expected: bool, env: Settings) -> None:
    settings = env.model_copy(update={"temporal_enabled": flag})
    assert temporal_enabled(settings) is expected


def test_temporal_enabled_without_lib_is_false(env: Settings) -> None:
    if temporal_enabled(env.model_copy(update={"temporal_enabled": True})):
        pytest.skip("temporalio installed; the ImportError path can't be exercised")
    settings = env.model_copy(update={"temporal_enabled": True})
    assert temporal_enabled(settings) is False


def test_narration_script_is_short_and_metadata_only() -> None:
    script = build_narration_script(DIGEST)
    assert script.startswith("Your digest for")
    assert "crew" in script
    assert "Trip planning settled." in script
    assert "drive or bus?" not in script  # raw chat text never narrated
    assert len(script) <= 2000


@pytest.mark.asyncio
async def test_narrate_disabled_returns_none_without_network() -> None:
    settings = Settings()  # no key -> voice_enabled False
    result = await narrate_digest(DIGEST, settings)
    assert result is None


@pytest.mark.asyncio
async def test_narrate_with_key_uses_mock_transport() -> None:
    settings = Settings(elevenlabs_api_key="test-key-123")

    requested: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested["path"] = request.url.path
        requested["key"] = request.headers.get("xi-api-key", "")
        requested["text"] = json.loads(request.content.decode())["text"]
        return httpx.Response(200, content=b"ID3 fake mp3 bytes")

    audio = await narrate_digest(DIGEST, settings, transport=httpx.MockTransport(handler))
    assert audio is not None
    assert audio.startswith(b"ID3")
    assert requested["key"] == "test-key-123"
    assert requested["path"].startswith("/v1/text-to-speech/")
    assert "Trip planning settled." in requested["text"]


@pytest.mark.asyncio
async def test_narrate_http_error_returns_none() -> None:
    settings = Settings(elevenlabs_api_key="test-key-123")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "bad key"})

    result = await narrate_digest(DIGEST, settings, transport=httpx.MockTransport(handler))
    assert result is None
