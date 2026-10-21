#!/usr/bin/env python3
"""Generate realistic SYNTHETIC group chats with planted facts.

SlothDigest test data. Every message here is invented; no real chat
exports ever enter this repository (AGENTS.md rule 13 / 8).

Screenplay style: the generator writes a banter timeline overnight, then
injects "planted facts" at known indices with known senders so the
evaluation harness (eval/run_eval.py) can measure recall and attribution
against ground truth. Seeded RNG => every run is reproducible.

Output for one dataset:
    chat.<format>            the chat export itself
    expected.json            planted facts + true senders + counts

Usage:
    python scripts/gen_synthetic_chats.py --out eval/datasets/base
    python scripts/gen_synthetic_chats.py --out eval/datasets/hinglish --style hinglish
    python scripts/gen_synthetic_chats.py --out fixtures --variants android,hinglish,edge_cases,discord,telegram
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

START = datetime(2026, 10, 19, 20, 0, 0)
END = datetime(2026, 10, 20, 6, 0, 0)

# The "user" whose perspective the digest is built for. Planted facts are
# aimed at this person (or use one of the aliases the backend settings
# would know). This is fake identity data, same as every other name here.
USER = "Priya"
USER_ALIASES = ["prids", "pris"]

NICHE_PLACES = ["Kheerganga", "Tirthan Valley", "Gokarna", "Lonavla creek"]

ENGLISH_BANTER = [
    "who else is awake lol",
    "this match is going to kill me",
    "send me that playlist na",
    "anyone up for biryani tomorrow",
    "ren danced so badly at farewell, wish I had the video",
    "I fixed the wifi password finally, write it down",
    "brb cat walked on the keyboard asdfgj",
    "schrödinger's parcel says out for delivery since Tuesday",
]

HINGLISH_BANTER = [
    "yaar ye match toh nikal gaya",
    "koi hai? bore ho raha hoon",
    "chal na, ab kya kar rahe ho tum log",
    "mugal se dar nahi lagta sahab, khatarnaak toh humidity hai",
    "aaj toh thand kam hai, phir bhi kambal le aao",
    "bhai reply karna please, urgent hai",
]

EMOJI_BANTER = ["🚀🚀🚀", "🔥🔥🔥", "😂😂", "🫡", "💀💀💀"]

CONFLICT_POOL = [
    "let's meet Saturday 6pm",
    "meeting is at Saturday 7pm",
]

DEADLINES = [
    "send booking amount by Friday",
    "vote on venue by tonight",
    "upload the report by Wednesday night",
]


@dataclass
class PlantedFact:
    kind: str
    text: str
    sender: str
    at: datetime
    message_id: str = field(init=False)
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        digest = hashlib.sha256(f"{self.kind}|{self.text}|{self.sender}".encode()).hexdigest()
        self.message_id = f"m-{digest[:10]}"


def gen_participants(rng: random.Random) -> tuple[list[str], str]:
    """3-8 fake participants; USER is always present (plus one alias user)."""
    pool = ["Riya", "Aman", "Kabir", "Dev", "Sam", "Nikhil", "Ishita"]
    rng.shuffle(pool)
    count = rng.randint(2, min(6, len(pool)))
    participants = pool[:count]
    participants.append(USER)
    return participants, USER


def banter_timeline(
    rng: random.Random,
    participants: list[str],
    style: str,
    target_n: int,
) -> tuple[list[tuple[datetime, str, str]], int]:
    """Return (timeline, messages_before_plants); also count noise messages.

    A banter message is (timestamp, sender, text). ~15 percent of banter is
    pure emoji noise, which the "skipped" counter should eventually absorb.
    """
    if style == "hinglish":
        pools = (ENGLISH_BANTER, HINGLISH_BANTER)
    elif style == "emoji":
        pools = (EMOJI_BANTER,)
    else:
        pools = (ENGLISH_BANTER,)

    speakers = participants.copy()
    out: list[tuple[datetime, str, str]] = []
    span = int((END - START).total_seconds()) - 1
    for _ in range(target_n):
        at = START + timedelta(seconds=rng.randint(0, span))
        speaker = rng.choice(speakers)
        pool = rng.choice(pools)
        text = rng.choice(pool)
        out.append((at, speaker, text))
    out.sort(key=lambda t: t[0])
    emojiish = sum(1 for _at, _spk, txt in out if any(e in txt for e in ("🚀", "🔥", "😂", "🫡", "💀")))
    return out, emojiish


def plant_facts(
    rng: random.Random,
    participants: list[str],
    timeline: list[tuple[datetime, str, str]],
) -> list[PlantedFact]:
    """Inject the 9.3 planted facts into the timeline at random slots."""
    others = [p for p in participants if p != USER]
    facts: list[PlantedFact] = []

    def message_from(sender: str, kind: str, text: str) -> PlantedFact:
        return PlantedFact(kind=kind, text=text, sender=sender,
                           at=timeline[rng.randrange(len(timeline))][0])

    alias = rng.choice(USER_ALIASES)
    # 1. decision ... 2. correction which supersedes it (9.3 reduce rule)
    base = message_from(rng.choice(others), "decision", CONFLICT_POOL[0])
    facts.append(base)
    correction = message_from(rng.choice(others), "correction", CONFLICT_POOL[1])
    facts.append(correction)
    base.superseded_by = correction.message_id
    # 3. question directed at USER
    facts.append(message_from(rng.choice(others), "question_for_user",
                              f"@{USER} can you drive on Saturday or take the bus?"))
    # 4. deadline
    facts.append(message_from(rng.choice(others), "deadline", rng.choice(DEADLINES)))
    # 5. mention of USER by nickname
    facts.append(message_from(rng.choice(others), "mention_user",
                              f"{alias} you owe the group zoodles"))
    # 6. banter planted to test the noise filter
    facts.append(message_from(rng.choice(others), "banter", rng.choice(EMOJI_BANTER)))
    return facts


def whatsapp_android_line(ts: datetime, sender: str, text: str) -> str:
    """Android WhatsApp export line: 12/03/2026, 21:45 - Sender: text."""
    return f"{ts.strftime('%d/%m/%Y, %H:%M')} - {sender}: {text}"


def discord_json(
    timeline: list[tuple[datetime, str, str]],
    conv_name: str,
) -> str:
    """DiscordChatExporter-shaped JSON export (simplified)."""
    return json.dumps(
        {
            "channel": {"name": conv_name},
            "messages": [
                {
                    "id": f"{int(ts.timestamp())}",
                    "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "author": {"name": sender},
                    "content": text,
                }
                for (ts, sender, text) in timeline
            ],
        },
        indent=1,
        ensure_ascii=False,
    )


def telegram_json(timeline: list[tuple[datetime, str, str]]) -> str:
    """Telegram Desktop-style export (simplified text form)."""
    return json.dumps(
        {
            "name": "Sloth Test Group",
            "messages": [
                {
                    "id": idx + 1,
                    "date": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                    "from": sender,
                    "text": text,
                }
                for idx, (ts, sender, text) in enumerate(timeline)
            ],
        },
        indent=1,
        ensure_ascii=False,
    )


def write_dataset(
    out_dir: Path,
    platform: str,
    style: str,
    participants: list[str],
    timeline: list[tuple[datetime, str, str]],
    facts: list[PlantedFact],
    conv_name: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if platform == "whatsapp":
        body = "\n".join(
            whatsapp_android_line(ts, sender, text) for (ts, sender, text) in timeline
        )
    elif platform == "discord":
        body = discord_json(timeline, conv_name)
    elif platform == "telegram":
        body = telegram_json(timeline)
    else:
        raise ValueError(f"unsupported platform {platform}")

    fmt = "txt" if platform == "whatsapp" else "json"
    (out_dir / f"chat.{fmt}").write_text(body + "\n", encoding="utf-8")

    skipped_lower_bound = sum(
        1 for _ts, _sender, text in timeline
        if any(e in text for e in ("🚀", "🔥", "😂", "🫡", "💀"))
    )
    expected = {
        "platform": platform,
        "conversation_name": conv_name,
        "participants": participants,
        "user_identifiers": [USER] + USER_ALIASES,
        "start": timeline[0][0].isoformat(),
        "end": timeline[-1][0].isoformat(),
        "message_count": len(timeline),
        "planted_facts": [
            {**asdict(f), "at": f.at.isoformat()} for f in facts
        ],
        "skipped_lower_bound": skipped_lower_bound,
    }
    (out_dir / "expected.json").write_text(
        json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("eval/datasets/base"),
        help="directory to write chat.<fmt> and expected.json into",
    )
    parser.add_argument(
        "--platform",
        choices=("whatsapp", "discord", "telegram"),
        default="whatsapp",
    )
    parser.add_argument(
        "--style",
        choices=("english", "hinglish", "emoji"),
        default="english",
    )
    parser.add_argument("--messages", type=int, default=None,
                        help="override banter message count (200-800)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--conversation-name", default="sloth test group")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    participants, _user = gen_participants(rng)
    n = args.messages or rng.randint(200, 800)
    timeline, _emoji = banter_timeline(rng, participants, args.style, n)
    facts = plant_facts(rng, participants, timeline)
    timeline = sorted(
        timeline
        + [(f.at, f.sender, f.text) for f in facts]
    )
    write_dataset(args.out, args.platform, args.style, participants, timeline,
                  facts, args.conversation_name)
    print(f"wrote {args.out} ({len(timeline)} messages, {len(facts)} planted facts)")


if __name__ == "__main__":
    main()
