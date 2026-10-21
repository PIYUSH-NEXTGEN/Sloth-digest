"""Temporal wrapper (A4.2) + shared LLM-call retry logic.

Temporal stays an optional extra (``pip install .[temporal]`` -> the
``temporal`` extra). When SLOTH_TEMPORAL_ENABLED and temporalio are both
present, digest runs can be wrapped as workflow activities with the retry
policy below (gives mid-run resumability). Without temporalio, runs execute
directly; ``run_with_retry`` then provides the same retry behaviour inline.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.05  # seconds; exponential backoff multiplies


async def run_with_retry(
    job: Callable[[], Awaitable[T]],
    *,
    attempts: int = RETRY_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY,
    retry_on: tuple[type[BaseException], ...] = (ValueError,),
) -> T:
    """Retry ``job`` with exponential backoff when it raises ``retry_on``.

    ValueError covers the pipeline's validation failures (bad model JSON,
    unexpected keys, failed schema checks). Non-listed errors propagate
    immediately. Under Temporal (when installed + enabled) the same policy is
    expressed as a RetryPolicy on the activity.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await job()
        except retry_on:
            if attempt == attempts:
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
    raise RuntimeError("unreachable")  # pragma: no cover - defensive


def temporal_enabled(settings: Any) -> bool:
    if not getattr(settings, "temporal_enabled", False):
        return False
    try:
        import temporalio  # noqa: F401
    except ImportError:
        logger.warning(
            "SLOTH_TEMPORAL_ENABLED=true but temporalio not installed "
            "(pip install .[temporal]); running direct without workflows"
        )
        return False
    return True


def heartbeat(activity: Callable[[], float], progress_fn: Callable[[], str]) -> str:
    """Metadata-only progress hook for workflow heartbeats (no text payloads)."""
    return f"{activity.__name__}: {progress_fn()}"


def start_temporal_workflow() -> None:
    """Placeholder worker bootstrap (only callable with temporalio installed)."""
    try:
        import temporalio  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "temporal extra not installed - SLOTH_TEMPORAL_ENABLED works only "
            "with the [temporal] optional extra"
        ) from exc
    raise NotImplementedError(
        "temporal worker bootstrap lands with the MVP demo; the retry policy "
        "above is already shared with direct runs"
    )
