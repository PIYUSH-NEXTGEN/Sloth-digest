"""Drop-folder watcher (A1.5): picks up new chat exports placed in a folder.

Dependency-free polling: every ``interval_seconds`` the folder is scanned for
files with supported suffixes; new/changed files (mtime) are parsed and
imported into the store. Import is idempotent (dedupe in the store), so a file
being reprocessed is always harmless.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.ingest.service import SUPPORTED_SUFFIXES, ingest_file_path
from app.store.db import Store


@dataclass
class WatchResult:
    processed: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class DropFolderWatcher:
    def __init__(
        self,
        store: Store,
        folder: str,
        interval_seconds: float = 5.0,
    ) -> None:
        self.store = store
        self.folder = Path(folder)
        self.interval_seconds = interval_seconds
        self._signature: dict[str, float] = {}
        self._task: asyncio.Task[None] | None = None
        self.folder.mkdir(parents=True, exist_ok=True)

    def scan_once(self) -> WatchResult:
        """One poll cycle; returns what was processed/failed (for tests/logs)."""
        result = WatchResult()
        if not self.folder.exists():
            return result
        for path in sorted(self.folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            signature = path.stat().st_mtime
            previous = self._signature.get(path.name)
            if previous is not None and previous == signature:
                continue
            try:
                ingest_file_path(self.store, path)
                result.processed.append(path.name)
            except (ValueError, OSError) as exc:
                result.failed[path.name] = str(exc)
            self._signature[path.name] = signature
        return result

    async def run_forever(self) -> None:
        while True:
            with contextlib.suppress(Exception):
                self.scan_once()
            await asyncio.sleep(self.interval_seconds)

    def start(self) -> None:
        self._task = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


def watcher_from_settings(store: Store) -> DropFolderWatcher:
    from app.config import get_settings

    settings = get_settings()
    return DropFolderWatcher(store, settings.drop_folder)


def describe_cycle(result: WatchResult) -> str:
    ts = datetime.now().isoformat(timespec="seconds")
    return f"{ts} processed={result.processed} failed={result.failed}"
