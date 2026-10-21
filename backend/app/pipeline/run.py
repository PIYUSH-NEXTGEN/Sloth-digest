"""Digest pipeline orchestration (A2.6): run shorts are synchronous.

Pipeline per conversation: window -> chunk -> extract (map, one retry
per chunk on bad output) -> reduce -> build needs-you -> validate ->
Digest. Digests persist via store.save_digest; POST /digest/run returns
the digest_id immediately (contract: DigestRunResult, 202).
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from app.llm.client import LLMClient
from app.llm.prompts import PROMPT_VERSION
from app.models import Digest, GroupDigest, Message, Window
from app.pipeline.chunk import Chunk, chunk_messages
from app.pipeline.extract import ChunkExtract, extract_chunk
from app.pipeline.reduce import ReduceResult, build_group_digest, heuristic_reduce, reduce_extract
from app.pipeline.retry import run_with_retry
from app.pipeline.score import ScoringConfig
from app.pipeline.validate import validate_group_digest
from app.store.db import Store

logger = logging.getLogger(__name__)

_EXTRACT_ATTEMPTS = 2
_DEFAULT_HOURS = 24


def _make_attempt(client: LLMClient, chunk: Chunk) -> Callable[[], Awaitable[ChunkExtract]]:
    async def attempt() -> ChunkExtract:
        return await extract_chunk(client, chunk)

    return attempt


async def _extracts_for_chunks(client: LLMClient, chunks: list[Chunk]) -> list[ChunkExtract]:
    """Map step with per-chunk retry; a chunk failing every attempt is skipped."""
    extracts: list[ChunkExtract] = []
    for chunk in chunks:
        try:
            result: ChunkExtract = await run_with_retry(
                _make_attempt(client, chunk),
                attempts=_EXTRACT_ATTEMPTS,
                retry_on=(ValueError,),
            )
        except ValueError as exc:
            logger.warning("extract failed for chunk %s; skipping: %s", chunk, exc)
            continue
        extracts.append(result)
    return extracts


async def run_digest(
    store: Store,
    client: LLMClient,
    scoring_config: ScoringConfig,
    *,
    since: datetime | None = None,
    conversation_ids: list[str] | None = None,
    now: datetime | None = None,
    model_name: str | None = None,
) -> Digest | None:
    """Run the whole pipeline over the window; returns None when nothing to digest."""
    end = (now or datetime.now(UTC)).astimezone(UTC)
    start = since or end - timedelta(hours=_DEFAULT_HOURS)
    window = Window(start=start, end=end)

    conversations = store.list_conversations()
    if conversation_ids is not None:
        allowed = set(conversation_ids)
        conversations = [c for c in conversations if c["id"] in allowed]

    groups: list[GroupDigest] = []
    for conv in conversations:
        messages: list[Message] = store.messages_in_window(
            conv["id"], start, end, include_system=False
        )
        if not messages:
            continue
        chunks = chunk_messages(messages)
        extracts = await _extracts_for_chunks(client, chunks)
        result: ReduceResult
        try:
            result, _used_prompt = await reduce_extract(
                client,
                extracts=extracts,
                conversation_name=conv["name"],
                window=window,
            )
        except ValueError as exc:
            # Heuristic fallback (agent.md A2.5): LLM keeps failing -> merge
            # mechanically, still scoring needs-you deterministically.
            logger.warning("reduce failed, using heuristic merge: %s", exc)
            result = heuristic_reduce(extracts)
        group = build_group_digest(
            conversation_id=conv["id"],
            platform=conv["platform"],
            name=conv["name"],
            messages=messages,
            extracts=extracts,
            window=window,
            scoring_config=scoring_config,
            result=result,
        )
        groups.append(validate_group_digest(group, messages))

    if not groups:
        return None
    model = model_name or str(getattr(client, "model", "unknown") or "unknown")
    digest = Digest(
        id=f"digest-{uuid.uuid4().hex[:12]}",
        generated_at=end,
        window=window,
        model=model,
        prompt_version=PROMPT_VERSION,
        groups=groups,
    )
    store.save_digest(digest)
    return digest
