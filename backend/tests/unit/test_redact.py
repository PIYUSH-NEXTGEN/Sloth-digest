"""Redaction tests (AGENTS.md 9.1): deterministic, reversible, no false hits."""

import pytest

from app.redact import RedactionMap, Redactor


@pytest.fixture()
def redactor() -> Redactor:
    return Redactor(RedactionMap())


def test_email_redacted_and_reversible(redactor: Redactor) -> None:
    out = redactor.redact("mail me at priya.trip@example.com please")
    assert "priya.trip@example.com" not in out
    assert "[EMAIL_1]" in out
    assert redactor.restore(out) == "mail me at priya.trip@example.com please"


def test_phone_formats(redactor: Redactor) -> None:
    samples = [
        "+91 98765 43210",
        "(987) 654-3210",
        "0091-987654321",
        "98765 43210",
        "9876543210",
    ]
    for sample in samples:
        out = redactor.redact(f"call {sample} tonight")
        assert sample not in out, sample
        assert "[PHONE_" in out, sample


def test_long_digit_strings(redactor: Redactor) -> None:
    out = redactor.redact("aadhaar 1234 5678 9012 and card 4111 1111 1111 1111")
    assert "1234 5678 9012" not in out
    assert "4111 1111 1111 1111" not in out


def test_url_tokens_stripped(redactor: Redactor) -> None:
    text = "preview: https://docs.example.com/share/files?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9&id=42"
    out = redactor.redact(text)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in out
    assert "docs.example.com/share/files" in out
    assert "id=42" in out  # short innocuous param kept


def test_no_false_redaction(redactor: Redactor) -> None:
    text = "meet 6 PM in room 204, score 3-1, bus 42 at 21:45, order ORD-987654 ok"
    out = redactor.redact(text)
    assert "6 PM" in out
    assert "room 204" in out
    assert "score 3-1" in out
    assert "21:45" in out
    assert "ORD-987654" in out
    assert "bus 42" in out


def test_deterministic(redactor: Redactor) -> None:
    text = "call +91 98765 43210"
    first = redactor.redact(text)
    second = redactor.redact(text)
    assert first == second


def test_same_value_reuses_placeholder(redactor: Redactor) -> None:
    out = redactor.redact("+91 98765 43210 then +91 98765 43210")
    assert out.count("[PHONE_1]") == 2
    assert out.count("[PHONE_2]") == 0


def test_restore_long_numbers(redactor: Redactor) -> None:
    out = redactor.redact("aadhaar 1234 5678 9012 emailed to priya@example.com")
    restored = redactor.restore(out)
    assert restored == "aadhaar 1234 5678 9012 emailed to priya@example.com"


def test_map_stays_local(redactor: Redactor) -> None:
    out = redactor.redact("secret +1 (555) 010-9999 email a@b.co digits 1234567890123")
    assert "secret" in out
    assert redactor.mapping.counter >= 3
