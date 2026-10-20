"""Ingest service: parse any supported export and import into the store (A1.5).

Platform detection from file content:
- ``.txt`` -> WhatsApp
- ``.json`` -> Discord (``messages`` with ``author``) or Telegram (``from``/``date`` entries)
"""

import hashlib
import json
from pathlib import Path
from typing import Protocol

from app.ingest.base import Parser
from app.ingest.discord import DiscordParser
from app.ingest.telegram import TelegramParser
from app.ingest.whatsapp import WhatsAppParser, read_export
from app.models import Message
from app.redact import RedactionMap, Redactor
from app.store.db import Store

SUPPORTED_SUFFIXES = {".txt", ".json"}


def decode_export(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("could not decode export file")


def detect_platform(filename: str, text: str) -> str:
    if filename.lower().endswith(".txt"):
        return "whatsapp"
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        entries = data["messages"]
    elif isinstance(data, list):
        entries = data
    else:
        raise ValueError("unsupported JSON export")
    for entry in entries:
        if isinstance(entry, dict):
            if "author" in entry:
                return "discord"
            if "from" in entry or "date" in entry:
                return "telegram"
    raise ValueError("unsupported JSON export")


def build_parser(platform: str, conversation_id: str) -> Parser:
    parser: Parser | None = None
    if platform == "whatsapp":
        parser = WhatsAppParser(conversation_id=conversation_id)
    elif platform == "discord":
        parser = DiscordParser(conversation_id=conversation_id)
    elif platform == "telegram":
        parser = TelegramParser(conversation_id=conversation_id)
    if parser is None:
        raise ValueError(f"unsupported platform: {platform}")
    return parser


class _ParserLike(Protocol):
    def parse(self, text: str, conversation_name: str | None = None) -> object: ...


def ingest_export(
    store: Store,
    filename: str,
    text: str,
    conversation_name: str | None = None,
    *,
    redact: bool = True,
) -> tuple[str, int, int]:
    """Parse and import one export file. Returns (conversation_id, imported, duplicates)."""
    platform = detect_platform(filename, text)
    stem = Path(filename).stem or "chat"
    content_key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    conversation_id = f"{platform}-{stem}:{content_key}"
    name = conversation_name or stem
    store.upsert_conversation(conversation_id, platform, name)

    mapping = RedactionMap()
    redactor = Redactor(mapping)
    parser = build_parser(platform, conversation_id)
    result = parser.parse(text, name)
    messages = _ensure_messages(result)
    if redact:
        messages = [_redact_message(redactor, msg) for msg in messages]
    imported, duplicates = store.import_messages(conversation_id, platform, messages)
    return conversation_id, imported, duplicates


def _ensure_messages(result: object) -> list[Message]:
    from app.ingest.base import ParseResult

    if isinstance(result, ParseResult):
        return result.messages
    raise TypeError("parser returned unexpected result")


def _redact_message(redactor: Redactor, msg: Message) -> Message:
    from app.ingest.base import build_message

    if not msg.text or msg.is_system:
        return msg
    redacted = redactor.redact(msg.text)
    if redacted == msg.text:
        return msg
    return build_message(
        platform=str(msg.platform.value),
        conversation_id=msg.conversation_id,
        seq=0,
        sender=msg.sender,
        timestamp=msg.timestamp,
        text=redacted,
        reply_to=msg.reply_to,
        is_system=msg.is_system,
    )


def ingest_file_path(
    store: Store, path: Path, conversation_name: str | None = None
) -> tuple[str, int, int]:
    text = (
        read_export(str(path))
        if path.suffix.lower() == ".txt"
        else path.read_text(encoding="utf-8")
    )
    return ingest_export(store, path.name, text, conversation_name)
