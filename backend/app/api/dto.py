"""API DTOs mirroring contracts/openapi.yaml (Agent B relies on these shapes)."""

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
