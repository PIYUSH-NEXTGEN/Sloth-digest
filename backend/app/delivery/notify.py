"""Optional desktop notification (A3.2). Opt-in via settings.desktop_notify.

Uses plyer when importable; otherwise a silent no-op (returns False). This
never sends anything over the network - a local OS toast at most.
"""

import logging

logger = logging.getLogger(__name__)


def send_desktop_notification(title: str, message: str) -> bool:
    try:
        from plyer import notification  # type: ignore[import-not-found]
    except ImportError:
        logger.info("desktop notification skipped (plyer not installed): %s", title)
        return False
    try:
        notification.notify(title=title[:64], message=message[:240], timeout=10)
        return True
    except Exception as exc:  # pragma: no cover - OS-dependent toast failures
        logger.warning("desktop notification failed: %s", exc)
        return False
