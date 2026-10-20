"""Unit + fixture tests for the Discord and Telegram parsers (A1.2, A1.3)."""

import json
from pathlib import Path
from typing import cast

import pytest

from app.ingest.discord import DiscordParser, parse_json
from app.ingest.telegram import TelegramParser, extract_text

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("root", "count"),
    [
        (
            {
                "messages": [
                    {
                        "id": "1",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "author": {"name": "A"},
                        "content": "hi",
                    }
                ]
            },
            1,
        ),
        ({"channel": {"name": "x"}, "messages": []}, 0),
        ([], 0),
    ],
)
def test_discord_root_shapes(root: object, count: int) -> None:
    text = json.dumps(root)
    assert len(parse_json(text)) == count


def test_discord_replies_bots_deleted_author() -> None:
    t10, t11, t12, t13 = (
        "2026-01-01T10:00:00Z",
        "2026-01-01T10:01:00Z",
        "2026-01-01T10:02:00Z",
        "2026-01-01T10:03:00Z",
    )
    t14, t15 = "2026-01-01T10:04:00Z", "2026-01-01T10:05:00Z"
    chat = {
        "messages": [
            {"id": "10", "timestamp": t10, "author": {"name": "Priya"}, "content": "match at 6?"},
            {
                "id": "11",
                "timestamp": t11,
                "type": 6,
                "author": {"name": "Bot"},
                "content": "Priya pinned a message",
            },
            {
                "id": "12",
                "timestamp": t12,
                "author": {"name": "Sam"},
                "content": "yes",
                "messageReference": {"messageId": "10"},
            },
            {"id": "13", "timestamp": t13, "author": None, "content": ""},
            {
                "id": "14",
                "timestamp": t14,
                "author": {"name": "Asha"},
                "content": "",
                "attachments": [{"filename": "score.png"}],
            },
            {
                "id": "15",
                "timestamp": t15,
                "author": {"name": "Asha", "bot": True},
                "content": "deploy finished",
            },
        ]
    }
    result = DiscordParser("d1").parse(json.dumps(chat))
    msgs = result.messages
    assert msgs[0].text == "match at 6?"
    assert msgs[1].is_system is True
    assert msgs[2].reply_to == "discord:d1:000001"
    assert msgs[3].is_system is True  # deleted author
    assert "[attachment: score.png]" in msgs[4].text
    assert result.participants == {"Priya", "Sam", "Asha"}


def test_discord_bad_entries_collected() -> None:
    chat = {
        "messages": [
            "not-an-object",
            {"id": "2", "timestamp": "bad-date", "author": {"name": "A"}},
            {
                "id": "3",
                "timestamp": "2026-01-01T10:00:00Z",
                "author": {"name": "A"},
                "content": "ok",
            },
        ]
    }
    result = DiscordParser("d1").parse(json.dumps(chat))
    assert len(result.messages) == 1
    assert len(result.unparsed) == 2


def test_telegram_text_entities() -> None:
    assert extract_text(["hello ", {"type": "bold", "text": "world"}, "!"]) == "hello world!"
    assert extract_text("plain") == "plain"
    assert extract_text(None) == ""


def test_telegram_service_and_replies() -> None:
    chat = {
        "name": "trip",
        "messages": [
            {
                "id": 1,
                "date": "2026-01-01T10:00:00",
                "type": "service",
                "actor": "Ishita",
                "text": "",
            },
            {"id": 2, "date": "2026-01-01T10:05:00", "from": "Priya", "text": "leaving at 6"},
            {
                "id": 3,
                "date": "2026-01-01T10:06:00",
                "from": "Sam",
                "text": ["same ", {"type": "mention", "text": "@priya"}],
                "reply_to_message_id": 2,
            },
            {
                "id": 4,
                "date": "2026-01-01T10:07:00",
                "from": "Kabir",
                "text": "",
                "photo": "img.jpg",
                "sticker_emoji": "🔥",
            },
        ],
    }
    result = TelegramParser("t1").parse(json.dumps(chat))
    msgs = result.messages
    assert msgs[0].is_system is True
    assert msgs[1].sender == "Priya"
    assert msgs[2].text == "same @priya"
    assert msgs[2].reply_to == "telegram:t1:000002"
    assert "[photo]" in msgs[3].text and "[sticker 🔥]" in msgs[3].text
    assert result.participants == {"Priya", "Sam", "Kabir"}


def _load_case(platform: str) -> tuple[Path, dict[str, object]] | None:
    expected_path = REPO_ROOT / "fixtures" / platform / "expected.json"
    chat_path = REPO_ROOT / "fixtures" / platform / "chat.json"
    if not (expected_path.exists() and chat_path.exists()):
        return None
    return chat_path, json.loads(expected_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", ["discord", "telegram"])
def test_fixture_parses_to_expected(fixture: str) -> None:
    loaded = _load_case(fixture)
    assert loaded is not None, f"fixture {fixture} expected.json missing"
    chat_path, expected = loaded
    parser_class = DiscordParser if fixture == "discord" else TelegramParser
    conversation_name = str(expected.get("conversation_name", fixture))
    result = parser_class(conversation_id=conversation_name).parse(
        chat_path.read_text(encoding="utf-8")
    )
    assert result.message_count == expected["message_count"]
    participants = cast(list[str], expected["participants"])
    assert result.participants == set(participants)
    assert result.unparsed == []
