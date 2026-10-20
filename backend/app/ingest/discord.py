"""Discord parser (A1.2) for DiscordChatExporter JSON exports.

Accepts a root object (``{"channel": {...}, "messages": [...]}``), just
``{"messages": [...]}`` or a bare array. Handles real DiscordChatExporter
fields (author ids/bots, ``messageReference`` replies mapped to our ids,
attachments, embeds, edited timestamps - ignored) plus the minimal shape
Agent B's generator emits. Non-default message types (pins, joins, boosts)
are flagged ``is_system``; system lines never influence attribution.
"""

import json
from datetime import datetime
from typing import Any, cast

from app.ingest.base import FIRST_MESSAGE_ID, ParseResult, build_message
from app.models import Message

PLATFORM = "discord"

# Discord message type ids (0 = default member message)
_DEFAULT_TYPE = 0
_SYSTEM_TYPES = {1, 2, 3, 6, 7, 8, 9, 10, 20, 21, 22}


def parse_json(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    if isinstance(data, list) and all(isinstance(entry, dict) for entry in data):
        return cast(list[dict[str, Any]], data)
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return cast(list[dict[str, Any]], data["messages"])
    raise ValueError("unsupported Discord export shape")


class DiscordParser:
    platform = PLATFORM

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

    def parse(self, text: str, conversation_name: str | None = None) -> ParseResult:
        raw = parse_json(text)
        result = ParseResult()
        participants: set[str] = set()
        unparsed: list[str] = []
        drafts: list[tuple[str, str, bool, datetime, Any, Any]] = []

        for position, item in enumerate(raw):
            if not isinstance(item, dict):
                unparsed.append(f"entry {position} is not an object")
                continue
            author = item.get("author") or {}
            sender = str(author.get("name") or "").strip()
            content = str(item.get("content") or "").strip()
            attachments = item.get("attachments") or []
            embeds = item.get("embeds") or []
            reference = item.get("messageReference") or {}
            reply_ref = reference.get("messageId")
            mtype = item.get("type", _DEFAULT_TYPE)
            raw_ts = item.get("timestamp")
            if not isinstance(raw_ts, str):
                unparsed.append(f"entry {position} has no timestamp")
                continue
            try:
                timestamp = datetime.fromisoformat(raw_ts)
            except ValueError:
                unparsed.append(f"entry {position} bad timestamp {raw_ts!r}")
                continue

            is_system = mtype in _SYSTEM_TYPES or sender == ""
            extras: list[str] = []
            if attachments:
                if isinstance(attachments, list):
                    extras.extend(f"[attachment: {a['filename']}]" for a in attachments)
            if embeds:
                extras.append(f"[{len(embeds)} embed(s)]")
            body = content
            if not body and extras:
                body = " ".join(extras)
            elif extras:
                body = "\n".join([content, *extras])
            drafts.append((sender, body, is_system, timestamp, reply_ref, item.get("id")))
            if not is_system:
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
