"""Settings endpoints (A3.4) per contracts/openapi.yaml /settings.

GET  -> merged view (env defaults + persisted overrides)
PUT  -> partial update; omitted fields keep their value; echoes the view
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.store.user_settings import UserSettings

router = APIRouter()


class SettingsView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_names: list[str]
    vip_people: list[str]
    keywords: list[str]
    digest_time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    model: str


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_names: list[str] | None = None
    vip_people: list[str] | None = None
    keywords: list[str] | None = None
    digest_time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    model: str | None = None


def user_settings_from(request: Request) -> UserSettings:
    settings = getattr(request.app.state, "user_settings", None)
    if not isinstance(settings, UserSettings):
        raise HTTPException(status_code=500, detail="user settings not initialised")
    return settings


@router.get("/settings", response_model=SettingsView)
async def get_settings_endpoint(request: Request) -> SettingsView:
    return SettingsView.model_validate(user_settings_from(request).view())


@router.put("/settings", response_model=SettingsView)
async def update_settings(request: Request, body: SettingsUpdate) -> SettingsView:
    view = user_settings_from(request).update(body.model_dump(mode="json", exclude_none=True))
    return SettingsView.model_validate(view)
