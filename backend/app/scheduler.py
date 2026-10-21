"""Scheduled digest job (A3.1): APScheduler cron at digest_time (default 06:00).

The job = drop-folder scan -> digest run -> delivery files (+ optional OS
toast). Runs inside the FastAPI event loop via AsyncIOScheduler, so
`run_digest` (async) is awaited directly. `reschedule` is called when the
user changes digest_time in PUT /settings.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings
from app.delivery.narration import narrate_digest
from app.delivery.notify import send_desktop_notification
from app.delivery.render import write_digest_files
from app.ingest.watcher import DropFolderWatcher
from app.llm.client import LLMClient
from app.models import Digest
from app.pipeline.run import run_digest
from app.pipeline.score import ScoringConfig
from app.store.db import Store
from app.store.user_settings import UserSettings

logger = logging.getLogger(__name__)

JOB_ID = "daily-digest"


def parse_digest_time(hhmm: str) -> tuple[int, int]:
    """'06:00' -> (6, 0). Raises ValueError on anything else."""
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"digest_time must be HH:MM, got {hhmm!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"digest_time out of range: {hhmm!r}")
    return hour, minute


class DigestScheduler:
    def __init__(
        self,
        store: Store,
        client: LLMClient,
        user_settings: UserSettings,
        watcher: DropFolderWatcher,
        *,
        digests_dir: str = "digests",
        env_settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._user_settings = user_settings
        self._watcher = watcher
        self._digests_dir = digests_dir
        self._env_settings = env_settings
        hour, minute = parse_digest_time(user_settings.view()["digest_time"])
        self._scheduler = AsyncIOScheduler()
        self._hour = hour
        self._minute = minute

    @property
    def schedule_label(self) -> str:
        return f"{self._hour:02d}:{self._minute:02d}"

    def start(self) -> None:
        self._scheduler.add_job(
            self.run_scheduled_job,
            CronTrigger(hour=self._hour, minute=self._minute),
            id=JOB_ID,
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("digest scheduled daily at %02d:%02d local", self._hour, self._minute)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def reschedule(self, digest_time: str) -> None:
        hour, minute = parse_digest_time(digest_time)
        self._hour, self._minute = hour, minute
        if self._scheduler.running:
            self._scheduler.reschedule_job(JOB_ID, trigger=CronTrigger(hour=hour, minute=minute))
            logger.info("digest rescheduled to %02d:%02d local", hour, minute)

    async def run_scheduled_job(self) -> str | None:
        """One scheduled pass: scan drop folder, digest, deliver."""
        self._watcher.scan_once()
        view = self._user_settings.view()
        digest = await run_digest(
            self._store,
            self._client,
            ScoringConfig(
                user_names=list(view["user_names"]),
                vip_people=list(view["vip_people"]),
                keywords=list(view["keywords"]),
            ),
            model_name=str(view["model"]),
        )
        if digest is None:
            logger.info("scheduled digest: nothing to digest")
            return None
        md_path, html_path = write_digest_files(digest, self._digests_dir)
        logger.info("scheduled digest written: %s / %s", md_path, html_path)
        if self._env_settings is not None and self._env_settings.voice_enabled:
            await self._narrate(digest)
        if bool(view.get("desktop_notify", False)):
            first = digest.groups[0] if digest.groups else None
            summary = first.tldr[:120] if first else "your daily digest is ready"
            send_desktop_notification("SlothDigest", summary)
        return digest.id

    async def _narrate(self, digest: Digest) -> None:
        """A4.3: optional ElevenLabs mp3 next to the digest files."""
        if self._env_settings is None or not self._env_settings.voice_enabled:
            return
        audio = await narrate_digest(digest, self._env_settings)
        if audio:
            date = datetime.now(UTC).date().isoformat()
            out = Path(self._digests_dir) / f"{date}.mp3"
            out.write_bytes(audio)
            logger.info("narration written: %s", out)
