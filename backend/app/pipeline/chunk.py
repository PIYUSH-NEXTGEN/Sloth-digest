"""Chunk a conversation window to fit the model's context budget (A2.1).

Rules (AGENTS.md 9.1):
- no chunk exceeds the token budget,
- no message is ever split in half,
- original ordering is preserved,
- when closing a chunk, prefer cutting at a natural time gap within the
  buffered window instead of at an arbitrary boundary (with a floor to avoid
  microscopic chunks).

Token estimation is a cheap heuristic (chars/3.5 plus a fixed per-message
overhead) - good enough for budgeting, and model-agnostic.
"""

from dataclasses import dataclass

from app.models import Message

CHARS_PER_TOKEN = 3.5
PER_MESSAGE_OVERHEAD_TOKENS = 16
DEFAULT_MAX_TOKENS = 3000
MAX_GAP_LOOKBACK = 40  # messages to inspect when choosing a nicer cut point
MIN_FLOOR_AFTER_GAP_CUT = 0.6  # keep at least this fraction of the budget filled


def estimate_tokens(messages: list[Message]) -> int:
    if not messages:
        return 0
    chars = sum(len(m.text) + len(m.sender) for m in messages)
    return int(chars / CHARS_PER_TOKEN) + len(messages) * PER_MESSAGE_OVERHEAD_TOKENS


@dataclass
class Chunk:
    messages: list[Message]

    @property
    def token_estimate(self) -> int:
        return estimate_tokens(self.messages)

    @property
    def start(self) -> Message:
        return self.messages[0]

    @property
    def end(self) -> Message:
        return self.messages[-1]


def chunk_messages(
    messages: list[Message], *, max_tokens: int = DEFAULT_MAX_TOKENS
) -> list["Chunk"]:
    """Split into ordered chunks under ``max_tokens`` each."""
    if not messages:
        return []
    if estimate_tokens(messages) <= max_tokens:
        return [Chunk(messages)]

    chunks: list[Chunk] = []
    buffer: list[Message] = []

    for message in messages:
        buffer.append(message)
        if estimate_tokens(buffer) <= max_tokens:
            continue
        cut_at = _choose_cut(buffer)
        first, remainder = buffer[:cut_at], buffer[cut_at:]
        if first:
            chunks.append(Chunk(first))
        buffer = remainder
        # remainder may still overflow; the loop keeps trimming as needed

    if buffer:
        # an oversized single message may end a chunk alone (no legal split)
        chunks.append(Chunk(buffer))
    return chunks


def _choose_cut(buffer: list[Message]) -> int:
    """Pick an index in ``1..len-1`` cutting at the biggest time gap of the
    recent window, unless each piece would be too small, then fall back to
    "fill up to budget" (single oversized message stays whole)."""
    lookback_start = max(1, len(buffer) - MAX_GAP_LOOKBACK)
    best_index = None
    best_gap = None
    budget_of_buffer = estimate_tokens(buffer)

    for index in range(lookback_start, len(buffer)):
        gap = (buffer[index].timestamp - buffer[index - 1].timestamp).total_seconds()
        first_tokens = estimate_tokens(buffer[:index])
        if first_tokens < budget_of_buffer * MIN_FLOOR_AFTER_GAP_CUT:
            continue
        if best_gap is None or gap > best_gap:
            best_gap = gap
            best_index = index

    if best_index is not None:
        return best_index

    # fall back: cut right before the last message that made it overflow
    return max(1, len(buffer) - 1)
