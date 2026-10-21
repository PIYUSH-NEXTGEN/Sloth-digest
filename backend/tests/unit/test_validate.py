"""Validate tests: bad ids dropped, from_ rebuilt from store, ids deduped."""

from datetime import datetime

from app.models import Deadline, Decision, GroupDigest, Message, NeedsYouItem, Platform
from app.pipeline.validate import (
    validate_deadlines,
    validate_decisions,
    validate_group_digest,
    validate_needs_you,
)

ALL_IDS = {"m1", "m2", "m3"}


def store_messages() -> list[Message]:
    return [
        Message(
            id="m1",
            platform=Platform.WHATSAPP,
            conversation_id="g1",
            sender="Real Sender",
            timestamp=datetime(2026, 3, 13, 21, 0),
            text="hi",
            is_system=False,
        )
    ]


def test_bad_ids_dropped_and_empty_items_removed() -> None:
    kept = validate_decisions(
        [
            Decision(text="park", message_ids=["m1", "zz-invented", "m1"]),
            Decision(text="ghost", message_ids=["zz-invented"]),
        ],
        ALL_IDS,
    )
    assert kept[0][1] == ["m1"]  # deduped, unknown dropped
    assert len(kept) == 1


def test_deadlines_validated_same_way() -> None:
    kept = validate_deadlines(
        [Deadline(text="ship", when=None, message_ids=["m2", "nope"])], ALL_IDS
    )
    assert kept == [(kept[0][0], ["m2"])]


def test_needs_you_from_rebuilt_from_store() -> None:
    items = validate_needs_you(
        [
            NeedsYouItem.model_validate(
                {
                    "message_id": "m1",
                    "from": "LLM Invented Name",
                    "summary": "hi",
                    "reason": "test",
                }
            ),
            NeedsYouItem.model_validate(
                {"message_id": "ghost", "from": "x", "summary": "y", "reason": "z"}
            ),
        ],
        store_messages(),
    )
    assert len(items) == 1
    assert items[0].from_ == "Real Sender"


def test_group_digest_end_to_end() -> None:
    digest = GroupDigest.model_validate(
        {
            "conversation_id": "g1",
            "platform": Platform.WHATSAPP,
            "name": "Trip",
            "message_count": 2,
            "skipped_count": 0,
            "tldr": "t",
            "needs_you": [
                {
                    "message_id": "m1",
                    "from": "Sam",
                    "summary": "s",
                    "reason": "r",
                }
            ],
            "decisions": [
                {"text": "go", "message_ids": ["m1", "nope", "m2"]},
                {"text": "gone", "message_ids": ["nope"]},
            ],
            "by_person": [],
            "deadlines": [{"text": "fri", "when": None, "message_ids": ["m3", "nope"]}],
        }
    )
    out = validate_group_digest(digest, store_messages())
    assert [d.text for d in out.decisions] == ["go"]
    assert out.decisions[0].message_ids == ["m1"]
    assert out.deadlines == []
    assert len(out.needs_you) == 1
    assert out.needs_you[0].from_ == "Real Sender"
