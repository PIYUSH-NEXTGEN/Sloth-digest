"""Ingest + sources endpoints (A1.5) per contracts/openapi.yaml.

The SQLite store lives on ``app.state.store`` (created in app.main.create_app).
"""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.api.dto import ConversationInfo, IngestResult, SourcesResponse
from app.ingest.service import decode_export, ingest_export
from app.store.db import Store

router = APIRouter()

_FILE = File(...)  # B008-safe module-level default


def store_from(request: Request) -> Store:
    store: object = getattr(request.app.state, "store", None)
    if not isinstance(store, Store):
        raise HTTPException(status_code=500, detail="store not initialised")
    return store


@router.post("/ingest/file", response_model=IngestResult)
async def ingest_file(
    request: Request,
    file: UploadFile = _FILE,
    conversation_name: str | None = None,
) -> IngestResult:
    store = store_from(request)
    data = await file.read()

    try:
        text = decode_export(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        conversation_id, imported, duplicates = ingest_export(
            store, file.filename or "export", text, conversation_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngestResult(conversation_id=conversation_id, imported=imported, duplicates=duplicates)


@router.get("/sources", response_model=SourcesResponse)
async def list_sources(request: Request) -> SourcesResponse:
    store = store_from(request)
    rows = store.list_conversations()
    return SourcesResponse(
        conversations=[
            ConversationInfo(
                id=row["id"],
                platform=row["platform"],
                name=row["name"],
                message_count=row["message_count"],
                last_message_at=row["last_message_at"],
            )
            for row in rows
        ]
    )
