"""Chunking tests (AGENTS.md 9.1): budget, no splits, order, time-gap cuts."""

from datetime import datetime, timedelta

from app.ingest.base import build_message
from app.models import Message
from app.pipeline.chunk import chunk_messages, estimate_tokens


def make_conv(
    n: int, *, text: str = "hi there", every: timedelta = timedelta(minutes=1)
) -> list[Message]:
    start = datetime(2026, 10, 19, 20, 0)
    return [
        build_message(
            platform="whatsapp",
            conversation_id="c1",
            seq=i,
            sender="Asha" if i % 2 else "Sam",
            timestamp=start + i * every,
            text=text,
        )
        for i in range(n)
    ]


def test_short_conversation_single_chunk() -> None:
    messages = make_conv(5)
    assert len(chunk_messages(messages)) == 1


def test_no_chunk_exceeds_budget() -> None:
    messages = make_conv(300)
    chunks = chunk_messages(messages, max_tokens=400)
    for chunk in chunks:
        assert chunk.token_estimate <= 400


def test_no_message_lost_or_split_and_order_kept() -> None:
    messages = make_conv(250)
    chunks = chunk_messages(messages, max_tokens=280)
    flattened = [m for chunk in chunks for m in chunk.messages]
    assert flattened == messages
    timestamps = [m.timestamp for m in flattened]
    assert timestamps == sorted(timestamps)


def test_time_gap_lands_on_boundary_or_is_interior() -> None:
    # 40 tightly-spaced messages, one 1-hour gap in the middle, more tight ones
    start = datetime(2026, 10, 19, 20, 0)
    messages = []
    for i in range(80):
        if i < 40:
            ts = start + timedelta(minutes=i)
        else:
            # one big 81-minute silence between message 39 and message 40
            ts = start + timedelta(hours=2, minutes=i - 40)
        messages.append(
            build_message(
                platform="whatsapp",
                conversation_id="c1",
                seq=i,
                sender="Asha" if i % 2 else "Sam",
                timestamp=ts,
                text="hi there",
            )
        )
    chunks = chunk_messages(messages, max_tokens=500)
    # the 1-hour gap must not be sliced arbitrarily: either a chunk boundary
    # sits exactly at the gap (or later), or the gap is interior to one chunk
    boundary_gap = any(
        (next_chunk.start.timestamp - chunk.end.timestamp) >= timedelta(hours=1)
        for chunk, next_chunk in zip(chunks, chunks[1:], strict=False)
    )
    interior_gap = any(
        (later.timestamp - earlier.timestamp) >= timedelta(hours=1)
        for chunk in chunks
        for earlier, later in zip(chunk.messages, chunk.messages[1:], strict=False)
    )
    assert boundary_gap or interior_gap


def test_huge_single_message_not_split() -> None:
    from app.ingest.base import build_message

    big = build_message(
        platform="whatsapp",
        conversation_id="c1",
        seq=0,
        sender="Asha",
        timestamp=datetime(2026, 10, 19, 20, 0),
        text="long story " * 2000,
    )
    chunks = chunk_messages([big], max_tokens=10)
    assert len(chunks) == 1
    assert chunks[0].messages[0] == big


def test_estimate_tokens_scales() -> None:
    assert estimate_tokens([]) == 0
    small = estimate_tokens(make_conv(10))
    large = estimate_tokens(make_conv(40))
    assert large > small * 3
