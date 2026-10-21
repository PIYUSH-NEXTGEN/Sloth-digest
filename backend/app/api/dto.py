"""API DTOs mirroring contracts/openapi.yaml (Agent B relies on these shapes)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IngestResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str
    imported: int
    duplicates: int


class ConversationInfo(BaseModel):
    id: str
    platform: str = Field(pattern="^(whatsapp|discord|telegram)$")
    name: str
    message_count: int
    last_message_at: str | None = Field(default=None)


class SourcesResponse(BaseModel):
    conversations: list[ConversationInfo]


class DigestRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    since: datetime | None = Field(
        default=None,
        description="Only include messages after this time (UTC). Defaults to last 24h.",
    )
    conversation_ids: list[str] | None = Field(
        default=None, description="Restrict to these conversations. Default all."
    )


class DigestRunResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    digest_id: str
