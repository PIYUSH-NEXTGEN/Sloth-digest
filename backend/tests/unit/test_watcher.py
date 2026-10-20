"""DropFolderWatcher tests: scan_once picks up new files, id canned reprocess."""

from pathlib import Path

from app.ingest.watcher import DropFolderWatcher
from app.store.db import Store

SAMPLE = "12/03/2026, 21:45 - Asha: cafe at 6?"


def test_scan_once_processes_new_files(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "watch.db"))
    folder = tmp_path / "drop"
    folder.mkdir()
    (folder / "trip.txt").write_text(SAMPLE, encoding="utf-8")
    watcher = DropFolderWatcher(store, str(folder), interval_seconds=600)
    result = watcher.scan_once()
    assert result.processed == ["trip.txt"]
    assert not result.failed
    sources = store.list_conversations()
    assert len(sources) == 1 and sources[0]["message_count"] == 1
    assert store.participants_of(sources[0]["id"]) == ["Asha"]

    # same mtime -> no reprocess
    again = watcher.scan_once()
    assert again.processed == []

    # touch (new mtime) and reprocess -> idempotent import adds nothing
    (folder / "trip.txt").write_text(SAMPLE + "\n12/03/2026, 21:46 - Sam: yes", encoding="utf-8")
    third = watcher.scan_once()
    assert third.processed == ["trip.txt"]
    assert store.list_conversations()[0]["message_count"] == 2
    store.close()


def test_scan_once_reports_failures(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "watch.db"))
    folder = tmp_path / "drop"
    folder.mkdir()
    (folder / "broken.json").write_text('{"messages": "not-a-list"}', encoding="utf-8")
    watcher = DropFolderWatcher(store, str(folder))
    result = watcher.scan_once()
    assert result.processed == []
    assert "broken.json" in result.failed
    store.close()
