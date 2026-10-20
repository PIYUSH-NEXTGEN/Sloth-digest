"""Core data models (AGENTS.md 7.1; canonical contract: contracts/digest.schema.json).

Keep these in sync with the contract — tests/unit/test_models.py enforces it by
reading the required fields straight out of contracts/digest.schema.json.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Platform(StrEnum):
    """Chat platform (official export/API ingestion only)."""

    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    TELEGRAM = "telegram"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Message(_Frozen):
    """A single parsed chat message. Attribution ground truth lives here."""

    id: str = Field(description="Stable digest-assigned ID (e.g. 'wa:conv1:000123').")
    platform: Platform
    conversation_id: str
    sender: str = Field(description="As parsed from the export; never decided by the LLM.")
    timestamp: datetime
    text: str
    reply_to: str | None = None
    is_system: bool


class Conversation(_Frozen):
    """A chat thread. Participants are the attribution allowlist."""

    id: str
    platform: Platform
    name: str
    participants: list[str]


class Window(_Frozen):
    start: datetime
    end: datetime


class NeedsYouItem(_Frozen):
    message_id: str
    from_: str = Field(alias="from", description="Rebuilt from source message by validate.py.")
    summary: str = Field(max_length=240)
    reason: str = Field(max_length=240)
    suggested_reply: str | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Decision(_Frozen):
    text: str = Field(max_length=400)
    message_ids: list[str] = Field(min_length=1)


class PersonPoints(_Frozen):
    name: str
    points: list[str] = Field(min_length=1, description="At most 240 chars each.")


class Deadline(_Frozen):
    text: str = Field(max_length=240)
    when: str | None = None
    message_ids: list[str] = Field(min_length=1)


class GroupDigest(_Frozen):
    """Digest of one group conversation over the window."""

    conversation_id: str
    platform: Platform
    name: str
    message_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    tldr: str = Field(max_length=400, description="At most 2 sentences.")
    needs_you: list[NeedsYouItem]
    decisions: list[Decision]
    by_person: list[PersonPoints]
    deadlines: list[Deadline]


class Digest(_Frozen):
    """Top-level digest produced by a pipeline run."""

    id: str
    generated_at: datetime
    window: Window
    model: str
    prompt_version: str
    groups: list[GroupDigest]
