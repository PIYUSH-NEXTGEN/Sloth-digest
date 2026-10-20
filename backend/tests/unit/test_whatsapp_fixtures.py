"""Fixture-driven tests: parse Agent B's synthetic WhatsApp exports and check
against the expected.json ground truth (Phase 1 exit criteria).

Fixtures live in B's lane (fixtures/); we only read them. If B hasn't landed
them yet the tests skip instead of failing.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

import pytest

from app.ingest.whatsapp import WhatsAppParser

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "whatsapp"


FixtureCase = tuple[str, Path, dict[str, object]]


def _fixture_cases() -> list[FixtureCase]:
    cases: list[FixtureCase] = []
    if not FIXTURE_DIR.exists():
        return cases
    for expected_path in FIXTURE_DIR.rglob("expected.json"):
        chat_path = expected_path.parent / "chat.txt"
        if chat_path.exists():
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            cases.append((expected_path.parent.name, chat_path, expected))
    return cases


CASES = _fixture_cases()


@pytest.mark.skipif(not CASES, reason="agent B fixtures not landed yet")
@pytest.mark.parametrize("name", [c[0] for c in CASES], ids=[c[0] for c in CASES])
def test_fixture_parses_to_expected(name: str) -> None:
    _, chat_path, expected = next(case for case in CASES if case[0] == name)
    expected_participants = cast(list[str], expected["participants"])
    result = WhatsAppParser(conversation_id=str(expected["conversation_name"])).parse(
        chat_path.read_text(encoding="utf-8")
    )
    assert result.messages, "parser produced zero messages"
    assert result.message_count == expected["message_count"]
    assert result.participants == set(expected_participants)
    assert result.unparsed == []
    start = datetime.fromisoformat(str(expected["start"])).replace(second=0, microsecond=0)
    end = datetime.fromisoformat(str(expected["end"])).replace(second=0, microsecond=0)
    for msg in result.messages:
        # the .txt export has no seconds; compare at minute granularity
        msg_minute = msg.timestamp.replace(tzinfo=None, second=0, microsecond=0)
        assert start <= msg_minute <= end
        if not msg.is_system:
            assert msg.sender in expected_participants
