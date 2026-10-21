"""Offline/privacy proof (A3.3, agent.md 9.5).

Runs the FULL pipeline - ingest a fixture-shaped WhatsApp export, chunk ->
extract (map, via FakeLLM) -> reduce -> score -> validate -> Digest persisted
- with every non-localhost socket patched to raise. Any network attempt fails
the test. Works on Windows, so no `unshare -n` is required.
"""

import asyncio
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ingest.service import ingest_export
from app.llm.client import FakeLLMClient
from app.pipeline.run import run_digest
from app.pipeline.score import ScoringConfig
from app.store.db import Store

_ROOT = Path(__file__).resolve().parents[3]
_DATASET = _ROOT / "eval" / "datasets" / "base" / "chat.txt"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


@contextmanager
def _blocked_sockets() -> Iterator[None]:
    """Refuse every non-localhost connect; localhost traffic still works
    (asyncio's Windows event loop needs its self-pipe socketpair)."""
    real_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> None:
        host = address[0] if isinstance(address, tuple) else str(address)
        if str(host) not in _LOCAL_HOSTS:
            pytest.fail(f"offline_check refused network attempt: {address}")
        real_connect(self, address)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        host = str(address[0]) if isinstance(address, tuple) else str(address)
        if host not in _LOCAL_HOSTS:
            pytest.fail(f"offline_check refused network attempt: {address}")
        return socket.socket()  # unreachable in practice for this check

    old_connect = socket.socket.connect
    old_create = socket.create_connection
    socket.socket.connect = guarded_connect  # type: ignore[method-assign,assignment]
    socket.create_connection = guarded_create_connection
    try:
        yield
    finally:
        socket.socket.connect = old_connect  # type: ignore[method-assign]
        socket.create_connection = old_create


def test_full_pipeline_offline(tmp_path: Path) -> None:
    if not _DATASET.exists():
        pytest.skip("eval dataset not generated yet (Agent B's gen script)")

    with _blocked_sockets():
        _run_offline_proof(tmp_path)


def _run_offline_proof(tmp_path: Path) -> None:

    store = Store(str(tmp_path / "offline.db"))
    text = _DATASET.read_text(encoding="utf-8")
    conversation_id, imported, duplicates = ingest_export(
        store, "chat.txt", text, "sloth test group"
    )
    assert imported + duplicates > 400
    assert conversation_id

    # FakeLLM answers every call with "{}": valid-but-empty extract, and the
    # reduce step falls back to the heuristic merge (agent.md A2.5).
    llm = FakeLLMClient([], default="{}")
    digest = asyncio.run(
        run_digest(
            store,
            llm,
            ScoringConfig(user_names=["Priya", "prids"], vip_people=[]),
            now=datetime(2026, 10, 20, 6, 0, tzinfo=UTC),
            model_name="fake",
        )
    )
    assert digest is not None, "pipeline must produce a digest fully offline"
    assert digest.model == "fake"
    assert digest.groups, "the ingested conversation must appear in the digest"
    group = digest.groups[0]
    assert group.message_count > 0
    assert group.conversation_id == conversation_id

    persisted = store.get_latest_digest()
    assert persisted is not None
    assert persisted.id == digest.id
