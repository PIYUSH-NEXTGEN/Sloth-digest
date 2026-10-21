"""Sentry tracing with metadata-only scrubbing (A4.1, agent.md 4.x rules).

Rules:
- OFF by default: init only when SLOTH_SENTRY_DSN is non-empty.
- Metadata-only: no message text, no digest content, no chat payload leaves
  the machine. scrub_event drops text payloads globally before sending;
  exception *values*, log messages, breadcrumbs, request query/body/cookies
  and all extras are stripped. Kept: exception type, level, timestamp,
  request URL path, tags, and synthetic ids (SHA-like topic ids only).
- Unit test proves scrubbed events contain none of the seeded chat text.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_TEXTY_KEYS = {"message", "value", "data", "query", "query_string", "cookies", "params", "extra"}
_KEEP_BREADCRUMB_KEYS = {"type", "category", "level", "timestamp"}


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """before_send hook: metadata-only event. Pure function (unit-tested)."""
    out = dict(event)
    out.pop("message", None)
    out.pop("logentry", None)

    exc = out.get("exception")
    if isinstance(exc, dict):
        values = []
        for item in exc.get("values", []):
            if isinstance(item, dict):
                kept = {k: item[k] for k in item if k not in {"value", "stacktrace"}}
                values.append(kept)
        out["exception"] = {**exc, "values": values}

    crumbs = out.get("breadcrumbs")
    if isinstance(crumbs, dict):
        keep = [
            {k: v for k, v in crumb.items() if k in _KEEP_BREADCRUMB_KEYS}
            for crumb in crumbs.get("values", [])
            if isinstance(crumb, dict)
        ]
        out["breadcrumbs"] = {**crumbs, "values": keep}

    request = out.get("request")
    if isinstance(request, dict):
        out["request"] = {k: request[k] for k in request if k in {"url", "method"}}

    for key in _TEXTY_KEYS:
        if key == "extra":
            continue
        out.pop(key, None)
    out.pop("extra", None)
    return out


def init_sentry(settings: Any) -> bool:
    """No-op unless DSN set and SDK importable; returns True when active."""
    if not getattr(settings, "sentry_enabled", False):
        return False
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("SLOTH_SENTRY_DSN set but sentry-sdk not installed; staying off")
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        before_send=scrub_event,
        default_integrations=False,
    )
    logger.info("Sentry tracing enabled (metadata-only scrubbing)")
    return True
