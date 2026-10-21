"""Scoring tests (AGENTS.md 9.1): mentions, VIP, keywords, deadlines, banter."""

from datetime import datetime

from app.ingest.base import build_message
from app.models import Message
from app.pipeline.extract import QuestionForUser
from app.pipeline.score import (
    ScoringConfig,
    detect_deadline,
    mentions_user,
    score_messages,
    suggested_reply_draft,
)

START = datetime(2026, 3, 13, 20, 0)  # a Friday


def msg(seq: int, sender: str, text: str) -> Message:
    return build_message(
        platform="whatsapp",
        conversation_id="c1",
        seq=seq,
        sender=sender,
        timestamp=START + seq * __import__("datetime").timedelta(minutes=1),
        text=text,
    )


def test_user_mention_beats_banter() -> None:
    config = ScoringConfig(user_names=["Priya"])
    banter = msg(1, "Sam", "kkrh bhai")
    pinged = msg(2, "Ishita", "Priya are you coming tonight?")
    scored = score_messages([banter, pinged], [], config)
    ids = [item.message_id for _score, item in scored]
    assert ids[0] == pinged.id
    assert ids[1] == banter.id
    assert scored[0][0] > scored[1][0]


def test_at_handle_and_hinglish_address() -> None:
    config = ScoringConfig()
    assert mentions_user("@nickname check DM", config)
    assert mentions_user("bhai reply karna please", config)
    assert not mentions_user("anyone need snacks?", config)


def test_rank_above_banter_and_limits() -> None:
    config = ScoringConfig()
    items = score_messages(
        [msg(1, "A", "urgent deadline talk"), msg(2, "B", "lol mood")], [], config
    )
    assert items[0][0] >= 20


def test_vip_people_add_weight() -> None:
    config = ScoringConfig(vip_people=["Aman"])
    base = score_messages([msg(1, "Riya", "urgent: leave now")], [], config)[0][0]
    vip = score_messages([msg(2, "Aman", "urgent: leave now")], [], config)[0][0]
    assert vip > base


def test_question_flagged_by_extract_ranks_top() -> None:
    config = ScoringConfig()
    mine = msg(1, "X", "Priya kkrh")
    dont_care = msg(2, "Y", "urgent urgent urgent")
    questions = [QuestionForUser(message_id=mine.id, question="what are you doing?")]
    scored = score_messages([mine, dont_care], questions, config)
    assert scored[0][1].message_id == mine.id
    assert scored[0][0] == 100.0


def test_deadlines_detected() -> None:
    assert detect_deadline("kal tak batch hai", START) == "2026-03-14"
    assert detect_deadline("submit by tomorrow", START) == "2026-03-14"
    assert detect_deadline("review by Friday", START) == "2026-03-20"
    assert detect_deadline("6bh B: call at 18:30", START) == "18:30"
    assert detect_deadline("just chatting", START) is None


def test_suggested_reply_is_draft_only() -> None:
    config = ScoringConfig(user_names=["Priya"])
    scored = score_messages([msg(1, "Sam", "Priya kal tak report?")], [], config)
    _, item = scored[0]
    reply = suggested_reply_draft(item)
    assert reply
    assert item.suggested_reply is None  # not attached automatically
