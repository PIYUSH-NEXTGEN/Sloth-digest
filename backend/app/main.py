"""FastAPI application factory for SlothDigest (AGENTS.md 3)."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.config import APP_VERSION


def create_app() -> FastAPI:
    app = FastAPI(
        title="SlothDigest API",
        version=APP_VERSION,
        description="Local-first digest for group chats. See contracts/openapi.yaml.",
    )
    app.include_router(health_router)
    return app


app = create_app()
