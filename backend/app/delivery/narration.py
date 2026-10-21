"""ElevenLabs narration (A4.3): opt-in text-to-speech of the daily digest.

OFF by default: narrate_digest returns None unless SLOTH_ELEVENLABS_API_KEY
is set. The narration script carries digest summaries only (TL;DR + top
needs-you) - never raw chat text. In tests the HTTP layer is faked with
httpx.MockTransport, so nothing touches the network.
"""

import logging

import httpx

from app.models import Digest

logger = logging.getLogger(__name__)

_API_BASE = "https://api.elevenlabs.io"
_DEFAULT_VOICE_ID = "21m00Tcz4TL2s"  # "Rachel" - swappable via settings


def build_narration_script(digest: Digest) -> str:
    """Short spoken script: digest-level, no raw chat lines."""
    lines = [f"Your digest for {digest.generated_at.date().isoformat()}."]
    for group in digest.groups:
        lines.append(f"In {group.name}: {group.tldr}")
        if group.needs_you:
            first = group.needs_you[0]
            lines.append(f"Needs you: a message from {first.from_}.")
        if group.deadlines:
            lines.append(f"{len(group.deadlines)} deadlines noted.")
    return " ".join(lines)[:2000]


async def narrate_digest(
    digest: Digest,
    settings: object,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes | None:
    key = getattr(settings, "elevenlabs_api_key", "")
    if not getattr(settings, "voice_enabled", False) or not key:
        return None
    voice_id = getattr(settings, "elevenlabs_voice_id", _DEFAULT_VOICE_ID) or _DEFAULT_VOICE_ID
    async with httpx.AsyncClient(base_url=_API_BASE, timeout=60.0, transport=transport) as api:
        response = await api.post(
            f"/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": key},
            json={
                "text": build_narration_script(digest),
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
            },
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("ElevenLabs narration failed: %s", exc)
        return None
    return response.content
