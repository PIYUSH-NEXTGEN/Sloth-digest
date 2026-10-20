"""WhatsApp parser unit tests (AGENTS.md 9.1). All inputs are synthetic."""

from datetime import datetime

from app.ingest.whatsapp import WhatsAppParser

CONV = "conv1"


def make(device: str, conv: str = CONV, order: str = "auto") -> WhatsAppParser:
    return WhatsAppParser(conversation_id=conv, date_order=order)  # type: ignore[arg-type]


def test_android_basic_message() -> None:
    parser = make("android")
    result = parser.parse("12/03/2026, 21:45 - Asha: cafe at 6?")
    msg = result.messages[0]
    assert msg.sender == "Asha"
    assert msg.text == "cafe at 6?"
    assert not msg.is_system
    assert msg.timestamp == datetime(2026, 3, 12, 21, 45)
    assert msg.id == f"whatsapp:{CONV}:000001"
    assert result.unparsed == []


def test_ios_basic_message() -> None:
    parser = make("ios")
    result = parser.parse("[12/03/26, 9:45:12 PM] Asha: cafe at 6?")
    msg = result.messages[0]
    assert msg.sender == "Asha"
    assert msg.timestamp == datetime(2026, 3, 12, 21, 45, 12)


def test_multiline_continuation() -> None:
    parser = make("android")
    text = "12/03/2026, 21:45 - Asha: long thought\ncontinues here\nand here"
    msgs = parser.parse(text).messages
    assert msgs[0].text == "long thought\ncontinues here\nand here"
    assert len(msgs) == 1


def test_system_lines_flagged() -> None:
    parser = make("android")
    text = "\n".join(
        [
            "12/03/2026, 21:40 - Messages and calls are end-to-end encrypted.",
            "12/03/2026, 21:41 - Asha joined using this group's invite link",
            "12/03/2026, 21:42 - Sam: hi",
            "12/03/2026, 21:43 - Sam left",
            "12/03/2026, 21:44 - You changed the group subject",
        ]
    )
    result = parser.parse(text)
    flags = [msg.is_system for msg in result.messages]
    assert flags == [True, True, False, True, True]
    assert result.participants == {"Asha", "Sam"}


def test_media_omitted_not_content() -> None:
    parser = make("android")
    text = "12/03/2026, 21:45 - Asha: <Media omitted>"
    msg = parser.parse(text).messages[0]
    assert msg.is_system
    assert msg.text == "<Media omitted>"


def test_names_with_emoji_and_phone_number() -> None:
    parser = make("android")
    text = "\n".join(
        [
            "12/03/2026, 21:45 - 🎉 Party Planner: friday works",
            "12/03/2026, 21:46 - +91 98765 43210: yes confirmed",
            "12/03/2026, 21:47 - Priya S: nice",
        ]
    )
    msgs = parser.parse(text).messages
    assert [m.sender for m in msgs] == ["🎉 Party Planner", "+91 98765 43210", "Priya S"]


def test_twelve_hour_and_twentyfour_hour() -> None:
    parser = make("android")
    text = "\n".join(
        [
            "[12/03/26, 12:05 AM] Asha: midnight snack",
            "[12/03/26, 12:05 PM] Asha: noon snack",
            "[12/03/26, 11:59 PM] Sam: late",
        ]
    )
    times = [m.timestamp for m in parser.parse(text).messages]
    assert times == [
        datetime(2026, 3, 12, 0, 5),
        datetime(2026, 3, 12, 12, 5),
        datetime(2026, 3, 12, 23, 59),
    ]


def test_date_order_mdy_detected() -> None:
    parser = make("android")
    text = "03/14/2026, 21:45 - Asha: MM/DD export"
    msg = parser.parse(text).messages[0]
    assert msg.timestamp == datetime(2026, 3, 14, 21, 45)


def test_date_order_ambiguous_defaults_to_dmy() -> None:
    parser = make("android")
    msg = parser.parse("03/04/2026, 09:00 - Asha: ambiguous date").messages[0]
    assert msg.timestamp == datetime(2026, 4, 3, 9, 0)


def test_empty_file_and_blank_lines() -> None:
    parser = make("android")
    result = parser.parse("")
    assert result.messages == []

    result = parser.parse("\n\n   \n")
    assert result.messages == []


def test_malformed_lines_collected_not_dropped() -> None:
    parser = make("android")
    text = "12/03/2026, 21:45 - Asha: ok\nnot-a-timestamp-orphan\n999/99/9999, xx - bogus"
    result = parser.parse(text)
    assert result.messages[0].text == "ok\nnot-a-timestamp-orphan"
    assert any("999" in line for line in result.unparsed)


def test_sender_with_colon_early_split() -> None:
    parser = make("android")
    msg = parser.parse("12/03/2026, 21:45 - Sam: reply: sure thing").messages[0]
    assert msg.sender == "Sam"
    assert msg.text == "reply: sure thing"


def test_huge_file_under_time_limit() -> None:
    import time

    parser = make("android")
    lines = []
    for i in range(1, 10001):
        sender = "Asha" if i % 2 else "Sam"
        lines.append(f"12/03/2026, 21:45 - {sender}: message number {i}")
    start = time.perf_counter()
    result = parser.parse("\n".join(lines))
    elapsed = time.perf_counter() - start
    assert len(result.messages) == 10000
    assert elapsed < 8.0, f"10k messages took {elapsed:.2f}s"


def test_continuation_before_first_line_is_unparsed() -> None:
    parser = make("android")
    result = parser.parse("orphan first line\n12/03/2026, 21:45 - Asha: hi")
    assert [m.text for m in result.messages] == ["hi"]
    assert result.unparsed == ["orphan first line"]


def test_explicit_mdy_order() -> None:
    parser = WhatsAppParser(conversation_id=CONV, date_order="mdy")
    msg = parser.parse("03/04/2026, 09:00 - Asha: ambiguous date").messages[0]
    assert msg.timestamp == datetime(2026, 3, 4, 9, 0)
