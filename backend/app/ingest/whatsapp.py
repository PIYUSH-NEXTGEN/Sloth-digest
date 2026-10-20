"""WhatsApp .txt export parser (Agent A1.1).

Handles:
- Android format: ``12/03/2026, 21:45 - Sender: text`` (24h, seconds optional,
  some exports use ``12/03/26 21:45 - ...`` without a comma after the date)
- iOS format: ``[12/03/26, 9:45:12 PM] Sender: text`` (12h, optional seconds)
- Multiline messages (continuation lines are appended)
- System lines (no ``Sender:`` prefix, or known system keywords)
- ``<Media omitted>`` and similar placeholders kept verbatim as body text
- DD/MM vs MM/DD detection: both orders are tried across all lines; the one
  that never produces a month > 12 wins; ties go to DD/MM (the common default)

Timestamps stay naive in the export's local time; UTC normalization is the
store layer's job (the user's machine clock is the source of truth).
Unparseable timestamp lines are collected in ``ParseResult.unparsed``;
nothing is silently dropped.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.ingest.base import FIRST_MESSAGE_ID, ParseResult, build_message
from app.models import Message

PLATFORM = "whatsapp"

TimestampKind = Literal["android", "ios"]


@dataclass
class _DraftMessage:
    """Accumulates a message through multiline continuation lines."""

    sender: str
    text: str
    timestamp: datetime
    is_system: bool


# Android:    12/03/2026, 21:45 - Sender: text   (or) 12/03/2026 21:45 - ...
_ANDROID_TIMESTAMP = re.compile(
    r"^(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4})"
    r",?\s+"
    r"(?P<h>\d{1,2}):(?P<minute>\d{2})(?::(?P<s>\d{2}))?"
    r"\s*(?P<ampm>[APap]\.?\s?[Mm]\.?)?"
    r"\s+-\s+"
    r"(?P<rest>.*)$"
)

# iOS:        [12/03/26, 9:45:12 PM] Sender: text
_IOS_TIMESTAMP = re.compile(
    r"^\[(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4})"
    r",\s*"
    r"(?P<h>\d{1,2}):(?P<minute>\d{2})(?::(?P<s>\d{2}))?"
    r"\s*(?P<ampm>[APap]\.?\s?[Mm]\.?)?"
    r"\]\s*"
    r"(?P<rest>.*)$"
)

# Android system lines use "- " separator (no sender)
_NAME_SPLIT = re.compile(r"^(?P<sender>.{1,120}?):\s(?P<text>.*\S.*)?$")

# Known system phrases (checked case-insensitively anywhere in the body)
SYSTEM_PHRASES = (
    "messages and calls are end-to-end encrypted",
    "this chat is a place for",
    "joined using this group's invite link",
    "created group",
    "changed the group subject",
    "changed the group description",
    "changed the group's icon",
    "changed the group's description",
    "changed the timer",
    "security code changed",
    "security code is now unavailable",
    "missed voice call",
    "missed video call",
    "disappearing messages",
)

SYSTEM_PREFIXES = (
    "this chat is with a business account",
    "this communication is now end-to-end encrypted",
    "you joined using this group's invite link",
    "you left",
)


def read_export(path: str) -> str:
    """Read an export file trying common WhatsApp encodings (UTF-8/UTF-16)."""
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            with open(path, encoding=encoding) as handle:
                return handle.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"could not decode export file: {path}")


class WhatsAppParser:
    """Parses a WhatsApp .txt export (Android or iOS) into messages."""

    platform = PLATFORM

    def __init__(
        self,
        conversation_id: str,
        date_order: Literal["auto", "dmy", "mdy"] = "auto",
    ) -> None:
        self.conversation_id = conversation_id
        self.date_order = date_order

    def parse(
        self,
        text: str,
        conversation_name: str | None = None,
    ) -> ParseResult:
        lines = text.splitlines()
        if self.date_order == "auto":
            order = self._detect_order(lines)
        else:
            order = self.date_order
        return self._parse_lines(lines, order)

    def _detect_order(self, lines: list[str]) -> Literal["dmy", "mdy"]:
        dmy_only = 0
        mdy_only = 0
        for line in lines:
            match = _ANDROID_TIMESTAMP.match(line) or _IOS_TIMESTAMP.match(line)
            if match is None:
                continue
            first, second = int(match.group("d")), int(match.group("m"))
            if second > 12:
                # second can't be a month -> first is the month (MM/DD)
                mdy_only += 1
            elif first > 12:
                # first can't be a month -> second is the month (DD/MM)
                dmy_only += 1
        return "mdy" if mdy_only > dmy_only else "dmy"

    def _parse_lines(self, lines: list[str], order: Literal["dmy", "mdy"]) -> ParseResult:
        result = ParseResult()
        participants: set[str] = set()
        unparsed: list[str] = []
        messages: list[Message] = []
        draft: list[_DraftMessage] = []
        seq = FIRST_MESSAGE_ID

        for line in lines:
            if not line.strip():
                continue
            match = _match_line(line, order)
            if match is None:
                if _looks_like_timestamp(line):
                    unparsed.append(line)
                elif draft:
                    draft[-1].text = f"{draft[-1].text}\n{line.rstrip()}"
                else:
                    unparsed.append(line)
                continue
            kind, body, timestamp = match
            sender_content = _split_sender_and_text(body)
            if sender_content is None:
                sender, content, is_system = "", body.strip(), True
                _capture_system_participant(body, participants)
            else:
                sender, content = sender_content
                is_system = _is_system_body(content)
                participants.add(sender)

            draft.append(
                _DraftMessage(
                    sender=sender,
                    text=content.rstrip(),
                    timestamp=timestamp,
                    is_system=is_system,
                )
            )

        for item in draft:
            messages.append(
                build_message(
                    platform=self.platform,
                    conversation_id=self.conversation_id,
                    seq=seq,
                    sender=item.sender,
                    timestamp=item.timestamp,
                    text=item.text,
                    is_system=item.is_system,
                )
            )
            seq += 1

        result.messages = messages
        result.participants = participants
        result.unparsed = unparsed
        return result


def _match_line(
    line: str, order: Literal["dmy", "mdy"]
) -> tuple[TimestampKind, str, datetime] | None:
    iso = _IOS_TIMESTAMP.match(line)
    if iso is not None and _valid_order(iso, order):
        return "ios", iso.group("rest"), _extract_time(iso, order)
    android = _ANDROID_TIMESTAMP.match(line)
    if android is not None and _valid_order(android, order):
        return "android", android.group("rest"), _extract_time(android, order)
    return None


def _valid_order(match: re.Match[str], order: Literal["dmy", "mdy"]) -> bool:
    first, second = int(match.group("d")), int(match.group("m"))
    if order == "dmy":
        return second <= 12 and first <= 31
    return first <= 12 and second <= 31


def _extract_time(match: re.Match[str], order: Literal["dmy", "mdy"]) -> datetime:
    first, second = int(match.group("d")), int(match.group("m"))
    day, month = (first, second) if order == "dmy" else (second, first)
    year = _two_digit_year(int(match.group("y")))
    hour = _apply_ampm(int(match.group("h")), match.group("ampm"))
    return datetime(
        year,
        month,
        day,
        hour,
        int(match.group("minute")),
        int(match.group("s") or 0),
    )


def _two_digit_year(year: int) -> int:
    if year >= 100:
        return year
    return 1900 + year if year > 68 else 2000 + year


def _apply_ampm(hour: int, ampm: str | None) -> int:
    if not ampm:
        return hour
    cleaned = ampm.strip().replace(".", "").replace(" ", "").upper()
    if cleaned not in ("AM", "PM"):
        return hour
    if cleaned == "PM":
        return hour if hour == 12 else hour + 12
    return 0 if hour == 12 else hour


def _split_sender_and_text(body: str) -> tuple[str, str] | None:
    """Split at the first ': '. Sender is 1..120 chars. WhatsApp exports always
    prefix member messages with 'Sender: ', so a miss means system line."""
    match = _NAME_SPLIT.match(body)
    if match is not None:
        return match.group("sender").strip(), (match.group("text") or "").strip()
    if body.endswith(":"):
        return body[:-1].strip(), ""
    return None


_TIMESTAMP_ATTEMPT = re.compile(r"^(\[\d{1,4}/\d{1,4}/\d{1,5}\b|\d{1,4}/\d{1,4}/\d{1,5}\b)")

_JOINED_PHRASE = "joined using this group's invite link"
_CREATED_PHRASE = "created group"


def _looks_like_timestamp(line: str) -> bool:
    return _TIMESTAMP_ATTEMPT.match(line) is not None


def _capture_system_participant(body: str, participants: set[str]) -> None:
    """System lines like 'Asha joined using this group's invite link' name a
    real participant; keep them in the attribution allowlist."""
    lowered = body.strip().lower()
    if _JOINED_PHRASE in lowered or _CREATED_PHRASE in lowered:
        name = body.strip()
        for phrase in (_JOINED_PHRASE, _CREATED_PHRASE):
            idx = lowered.find(phrase)
            if idx > 0:
                name = body.strip()[:idx].strip()
                break
        if name and name.lower() != "you":
            participants.add(name)


def _is_system_body(content: str) -> bool:
    lowered = content.lower()
    stripped = content.strip().lower()
    if any(stripped.startswith(prefix) for prefix in SYSTEM_PREFIXES):
        return True
    if any(phrase in lowered for phrase in SYSTEM_PHRASES):
        return True
    return "<media omitted>" == stripped or "<attached:" in lowered
