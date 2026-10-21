"""Importance scoring (A2.4): what in the chat needs *you* (AGENTS.md 9.1).

Deterministic rules on top of the redacted store text - no LLM here:
- direct questions flagged for the user (by the extract step) rank highest,
- messages mentioning the user's names/aliases (incl. @handle and Hinglish
  direct address like "bhai"/"yaar") rank high,
- default keywords (urgent, asap, deadline, tomorrow, kal tak, tonight, ...)
  and user-added keywords add weight,
- messages from VIP people add weight.

Attribution note: every produced ``NeedsYouItem.from_`` is copied from the
stored message's sender - the LLM never decides it (7.4). Suggested replies
(A2.7) are drafts only; SlothDigest never sends anything.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models import Message, NeedsYouItem
from app.pipeline.extract import QuestionForUser

_DEFAULT_KEYWORDS: tuple[str, ...] = (
    "urgent",
    "asap",
    "deadline",
    "tomorrow",
    "tonight",
    "as soon as possible",
    "kal tak",
    "kal",
)

_HINGLISH_ADDRESS: tuple[str, ...] = ("bhai", "yaar", "boss")

_WEEKDAY_NUMS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thur": 3,
    "thurs": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\s*(?:am|pm)?\b")


@dataclass
class ScoringConfig:
    user_names: list[str] = field(default_factory=lambda: ["Your Name", "nickname"])
    vip_people: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    def all_keywords(self) -> tuple[str, ...]:
        return tuple({*_DEFAULT_KEYWORDS, *self.keywords})


def mentions_user(text: str, config: ScoringConfig) -> bool:
    lowered = text.lower()
    names = [n.lower() for n in config.user_names if n]
    if any(f"@{name}" in lowered or name in lowered for name in names):
        return True
    # Hinglish direct address also counts as addressing the user
    return any(word in lowered for word in _HINGLISH_ADDRESS)


def detect_deadline(text: str, message_ts: datetime) -> str | None:
    """Best-effort normalization: next weekday/date or a clock time.

    Returns an ISO date ('2026-03-15') or an 'HH:MM' time, else None.
    """
    lowered = text.lower()
    if "kal tak" in lowered:
        return (message_ts + timedelta(days=1)).strftime("%Y-%m-%d")
    if "tomorrow" in lowered or " kal " in f" {lowered} ":
        return (message_ts + timedelta(days=1)).strftime("%Y-%m-%d")
    for word, weekday in _WEEKDAY_NUMS.items():
        if re.search(rf"\b{word}\b", lowered):
            days_ahead = (weekday - message_ts.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (message_ts + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    time_match = _TIME_RE.search(lowered)
    if "deadline" in lowered:
        return time_match.group(1) if time_match else "unspecified"
    if "tonight" in lowered or "asap" in lowered:
        return message_ts.strftime("%H:%M")
    has_time = time_match is not None
    has_schedule_word = any(
        word in lowered
        for word in ("call", "meet", "meetup", "due", "submit", "till", "by ", "shift")
    )
    if has_time and has_schedule_word and time_match is not None:
        return time_match.group(1)
    return None


def keyword_hits(text: str, config: ScoringConfig) -> list[str]:
    lowered = text.lower()
    return [k for k in config.all_keywords() if k in lowered]


def score_messages(
    messages: list[Message],
    questions: list[QuestionForUser],
    config: ScoringConfig,
) -> list[tuple[float, NeedsYouItem]]:
    """Produce ranked (score, NeedsYouItem) candidates; highest first."""
    by_id = {m.id: m for m in messages}
    items: list[tuple[float, NeedsYouItem]] = []
    handled: set[str] = set()

    for question in questions:
        message = by_id.get(question.message_id)
        if message is None or message.is_system:
            continue
        items.append(_build_item(message, question.question, "asked you a question", 100.0))
        handled.add(message.id)

    candidates: list[tuple[float, NeedsYouItem]] = []
    for message in messages:
        if message.is_system or message.id in handled:
            continue
        score = 0.0
        reasons: list[str] = []
        if mentions_user(message.text, config):
            score += 40.0
            reasons.append("mentions you")
        hits = keyword_hits(message.text, config)
        if hits:
            score += 20.0 * min(len(hits), 3)
            reasons.append("keyword: " + "/".join(hits[:2]))
        vip_hit = next((v for v in config.vip_people if v.lower() == message.sender.lower()), None)
        if vip_hit is not None:
            score += 30.0
            reasons.append("VIP person")
        if score > 0:
            candidates.append(_build_item(message, message.text[:240], "; ".join(reasons), score))

    items.extend(candidates)
    items.sort(key=lambda pair: pair[0], reverse=True)
    return items


def _build_item(
    message: Message, summary: str, reason: str, score: float, suggested_reply: str | None = None
) -> tuple[float, NeedsYouItem]:
    item = NeedsYouItem.model_validate(
        {
            "message_id": message.id,
            "from": message.sender,
            "summary": summary[:240],
            "reason": reason[:240],
            "suggested_reply": suggested_reply,
        }
    )
    return score, item


def suggested_reply_draft(item: NeedsYouItem) -> str:
    """A short draft reply (A2.7); never sent automatically."""
    if "deadline" in item.reason:
        return f"On it - {item.summary[:80]}"
    return f"Got it ({item.message_id}) - will reply soon."[:120]
