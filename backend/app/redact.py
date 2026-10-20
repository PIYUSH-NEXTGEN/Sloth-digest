"""Redaction before LLM (A1.6, AGENTS.md 7.3 / 9.1).

Replaces phones, emails, long digit strings (Aadhaar/card-like), and token-ish
URL query values with stable placeholders (``[PHONE_1]``). The mapping is kept
locally (never leaves the machine) so text can be restored for display via
``restore``. Redaction must be deterministic and must NOT flag everyday
numbers ("6 PM", "room 204", times, short ids).
"""

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# URL query values that look secret-ish (>=8 chars of token alphabet) or the
# parameter name itself smells like a credential (token/key/secret/auth/sig).
_URL_TOKEN_RE = re.compile(
    r"(?i)([?&](?:api[_-]?key|access[_-]?token|token|key|secret|auth|sig|sig|"
    r"pass(?:word)?)=)([^&\s]{8,})"
)

_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?"  # optional country prefix
    r"(?:\(?\d{3,5}\)?[\s.-]?){1,4}\d{3,5}"  # digit groups summing to >= 8 digits
    r"(?!\S*\d)"  # not inside a longer digit run / word
)


def _phone_match(match: re.Match[str]) -> bool:
    return len(re.sub(r"\D", "", match.group(0))) >= 8


_LONG_DIGITS_RE = re.compile(r"\b\d{8,16}\b")


class RedactionMap:
    """Local, reversible placeholder mapping."""

    def __init__(self) -> None:
        self.counter = 0
        self.forward: dict[str, str] = {}  # original -> placeholder
        self.reverse: dict[str, str] = {}  # placeholder -> original

    def _placeholder(self, kind: str, original: str) -> str:
        existing = self.forward.get(original)
        if existing:
            return existing
        self.counter += 1
        placeholder = f"[{kind}_{self.counter}]"
        self.forward[original] = placeholder
        self.reverse[placeholder] = original
        return placeholder


class Redactor:
    """Redacts text against a map and can restore it."""

    def __init__(self, mapping: RedactionMap | None = None) -> None:
        self.mapping = mapping or RedactionMap()

    def redact(self, text: str) -> str:
        result = EMAIL_RE.sub(lambda m: self.mapping._placeholder("EMAIL", m.group(0)), text)
        result = _URL_TOKEN_RE.sub(
            lambda m: m.group(1) + self.mapping._placeholder("TOKEN", m.group(2)),
            result,
        )
        result = _PHONE_RE.sub(
            lambda m: (
                self.mapping._placeholder("PHONE", m.group(0)) if _phone_match(m) else m.group(0)
            ),
            result,
        )
        result = _LONG_DIGITS_RE.sub(
            lambda m: self.mapping._placeholder("NUMBER", m.group(0)), result
        )
        return result

    def restore(self, text: str) -> str:
        result = text
        for placeholder, original in self.mapping.reverse.items():
            result = result.replace(placeholder, original)
        return result
