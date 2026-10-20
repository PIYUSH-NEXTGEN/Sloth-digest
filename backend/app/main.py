"""FastAPI application factory for SlothDigest (AGENTS.md 3)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.config import APP_VERSION, Settings, get_settings
from app.ingest.watcher import DropFolderWatcher
from app.store.db import Store


def create_watcher(settings: Settings, store: Store) -> DropFolderWatcher:
    return DropFolderWatcher(store, settings.drop_folder)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    store: Store = app.state.store
    watcher: DropFolderWatcher | None = None
    watcher = create_watcher(settings, store)
    watcher.start()
    try:
        yield
    finally:
        await watcher.stop()
        store.close()


def create_app(store: Store | None = None) -> FastAPI:
    settings = get_settings()
    instance = store if store is not None else Store(settings.db_path)
    app = FastAPI(
        title="SlothDigest API",
        version=APP_VERSION,
        description="Local-first digest for group chats. See contracts/openapi.yaml.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = instance
    app.include_router(health_router)
    app.include_router(ingest_router)
    return app


app = create_app()
