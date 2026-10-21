"""FastAPI application factory for SlothDigest (AGENTS.md 3)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.ask import router as ask_router
from app.api.digest import router as digest_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.settings import router as settings_router
from app.config import APP_VERSION, Settings, get_settings
from app.ingest.watcher import DropFolderWatcher
from app.llm.client import LLMClient, OllamaClient
from app.observability.sentry import init_sentry
from app.retrieval.embeddings import OllamaEmbedder
from app.scheduler import DigestScheduler
from app.store.db import Store
from app.store.user_settings import UserSettings


def create_watcher(settings: Settings, store: Store) -> DropFolderWatcher:
    return DropFolderWatcher(store, settings.drop_folder)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    store: Store = app.state.store
    watcher: DropFolderWatcher = app.state.watcher
    watcher.start()
    scheduler: DigestScheduler | None = app.state.digest_scheduler
    if scheduler is not None:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.stop()
        await watcher.stop()
        store.close()


def create_app(
    store: Store | None = None,
    llm: LLMClient | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    init_sentry(settings)  # no-op unless SLOTH_SENTRY_DSN is set (A4.1)
    instance = store if store is not None else Store(settings.db_path)
    app = FastAPI(
        title="SlothDigest API",
        version=APP_VERSION,
        description="Local-first digest for group chats. See contracts/openapi.yaml.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = instance
    app.state.llm = llm if llm is not None else OllamaClient(settings.ollama_url, settings.model)
    user_settings = UserSettings(settings)
    app.state.user_settings = user_settings
    watcher = create_watcher(settings, instance)
    app.state.watcher = watcher
    app.state.digest_scheduler = DigestScheduler(
        instance, app.state.llm, user_settings, watcher, env_settings=settings
    )
    app.state.embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model)
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(digest_router)
    app.include_router(settings_router)
    app.include_router(ask_router)
    return app


app = create_app()
