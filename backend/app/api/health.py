"""Health and basic info endpoint (contract: contracts/openapi.yaml /health)."""

from fastapi import APIRouter

from app.config import APP_VERSION, get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def get_health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "version": APP_VERSION, "model": settings.model}
