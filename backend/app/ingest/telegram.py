"""Telegram parser (A1.3) for Telegram Desktop JSON exports.

Root shape: ``{"name": "...", "messages": [...]}``. Message fields handled:
``id``, ``date`` (ISO-8601, naive local), ``from``/``from_id`` (``None`` for
service messages), ``type: "message" | "service"``, ``text`` (string or the
entity-shard list format), ``reply_to_message_id`` (mapped to our ids),
attachments/photos/files kept as text notes. Service messages are
``is_system``.
"""

import json
from datetime import datetime
from typing import Any

from app.ingest.base import FIRST_MESSAGE_ID, ParseResult, build_message
from app.models import Message

PLATFORM = "telegram"


def extract_text(value: Any) -> str:
    """``text`` is either a string or a list of string/entity shards."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for shard in value:
            if isinstance(shard, str):
                parts.append(shard)
            elif isinstance(shard, dict) and isinstance(shard.get("text"), str):
                parts.append(shard["text"])
        return "".join(parts)
    return ""


class TelegramParser:
    platform = PLATFORM

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

    def parse(self, text: str, conversation_name: str | None = None) -> ParseResult:
        data = json.loads(text)
        raw: list[dict[str, Any]]
        if isinstance(data, dict) and isinstance(data.get("messages"), list):
            raw = data["messages"]
        elif isinstance(data, list):
            raw = data
        else:
            raise ValueError("unsupported Telegram export shape")

        result = ParseResult()
        participants: set[str] = set()
        unparsed: list[str] = []
        drafts: list[tuple[str, str, bool, datetime, Any, Any]] = []

        for position, item in enumerate(raw):
            if not isinstance(item, dict):
                unparsed.append(f"entry {position} is not an object")
                continue
            raw_ts = item.get("date")
            if not isinstance(raw_ts, str):
                unparsed.append(f"entry {position} has no date")
                continue
            try:
                timestamp = datetime.fromisoformat(raw_ts)
            except ValueError:
                unparsed.append(f"entry {position} bad date {raw_ts!r}")
                continue

            msg_type = str(item.get("type") or "message")
            sender = str(item.get("from") or "").strip()
            body = extract_text(item.get("text"))
            is_service = msg_type == "service" or sender == ""
            if not body:
                extras: list[str] = []
                if item.get("photo"):
                    extras.append("[photo]")
                if item.get("file"):
                    extras.append(f"[file: {item['file']}]")
                if item.get("sticker_emoji"):
                    extras.append(f"[sticker {item['sticker_emoji']}]")
                body = " ".join(extras) if extras else body
            sender_for_msg = "" if is_service else sender
            desc = ""
            if is_service and not body:
                desc = str(item.get("actor") or "system")
            drafts.append(
                (
                    sender_for_msg,
                    body or desc,
                    is_service,
                    timestamp,
                    item.get("reply_to_message_id"),
                    item.get("id"),
                )
            )
            if not is_service:
                participants.add(sender)

        id_by_raw: dict[Any, str] = {}
        for seq, draft in enumerate(drafts, start=FIRST_MESSAGE_ID):
            id_by_raw[draft[5]] = f"{PLATFORM}:{self.conversation_id}:{seq:06d}"

        messages: list[Message] = []
        for seq, (sender, body, is_system, timestamp, reply_ref, _raw_id) in enumerate(
            drafts, start=FIRST_MESSAGE_ID
        ):
            messages.append(
                build_message(
                    platform=self.platform,
                    conversation_id=self.conversation_id,
                    seq=seq,
                    sender=sender,
                    timestamp=timestamp,
                    text=body,
                    reply_to=id_by_raw.get(reply_ref),
                    is_system=is_system,
                )
            )

        result.messages = messages
        result.participants = participants
        result.unparsed = unparsed
        return result
