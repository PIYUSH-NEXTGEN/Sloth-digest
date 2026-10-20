"""Parser protocol (AGENTS.md app/ingest/base.py).

Every platform parser turns an official export into ``Message`` models sharing
one conversation id. Parsers must never guess senders or timestamps: that data
is the attribution ground truth (AGENTS.md 7.4). Unknown lines are collected in
``ParseResult.unparsed`` instead of being dropped silently.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.models import Message, Platform


@dataclass
class ParseResult:
    messages: list[Message] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    participants: set[str] = field(default_factory=set)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def warnings(self) -> list[str]:
        return (
            [f"{len(self.unparsed)} line(s) could not be parsed: " + "; ".join(self.unparsed[:3])]
            if self.unparsed
            else []
        )


@runtime_checkable
class Parser(Protocol):
    def parse(self, text: str, conversation_name: str | None = None) -> ParseResult:
        """Parse a full export into messages of one conversation."""
        ...


FIRST_MESSAGE_ID = 1


def next_message_id(platform: str, conversation_id: str, seq: int) -> str:
    """Stable message id: 'wa:conv1:000123'."""
    return f"{platform}:{conversation_id}:{seq:06d}"


def build_message(
    *,
    platform: str,
    conversation_id: str,
    seq: int,
    sender: str,
    timestamp: datetime | str,
    text: str,
    reply_to: str | None = None,
    is_system: bool = False,
) -> Message:
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    return Message(
        id=next_message_id(platform, conversation_id, seq),
        platform=Platform(platform),
        conversation_id=conversation_id,
        sender=sender,
        timestamp=timestamp,
        text=text,
        reply_to=reply_to,
        is_system=is_system,
    )


def participants_of(result: ParseResult) -> Sequence[str]:
    return sorted(result.participants)
