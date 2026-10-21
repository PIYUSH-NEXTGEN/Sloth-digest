"""Digest endpoints (A2.6) per contracts/openapi.yaml.

POST /digest/run  -> 202 {digest_id} (synchronous MVP run)
GET  /digest/latest -> 200 Digest | 404
GET  /digest/{id}   -> 200 Digest | 404

The LLM client lives on ``app.state.llm``; tests inject FakeLLMClient there.
"""

from fastapi import APIRouter, HTTPException, Request

from app.api.dto import DigestRunRequest, DigestRunResult
from app.api.ingest import store_from
from app.config import Settings
from app.llm.client import LLMClient
from app.models import Digest
from app.pipeline.run import run_digest
from app.pipeline.score import ScoringConfig
from app.store.db import Store

router = APIRouter()


def llm_from(request: Request) -> LLMClient:
    client: LLMClient | None = getattr(request.app.state, "llm", None)
    if client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialised")
    return client


@router.post("/digest/run", status_code=202, response_model=DigestRunResult)
async def run_digest_endpoint(
    request: Request, body: DigestRunRequest | None = None
) -> DigestRunResult:
    store = store_from(request)
    llm = llm_from(request)
    settings: Settings = request.app.state.settings
    payload = body or DigestRunRequest()
    try:
        digest = await run_digest(
            store,
            llm,
            ScoringConfig(
                user_names=settings.user_names,
                vip_people=settings.vip_people,
                keywords=settings.keywords,
            ),
            since=payload.since,
            conversation_ids=payload.conversation_ids,
            model_name=settings.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if digest is None:
        raise HTTPException(
            status_code=400,
            detail="nothing to digest: no messages in window for selected conversations",
        )
    return DigestRunResult(digest_id=digest.id)


@router.get("/digest/latest", response_model=Digest)
async def get_latest_digest(request: Request) -> Digest:
    store: Store = store_from(request)
    digest = store.get_latest_digest()
    if digest is None:
        raise HTTPException(status_code=404, detail="no digest generated yet")
    return digest


@router.get("/digest/{digest_id}", response_model=Digest)
async def get_digest(request: Request, digest_id: str) -> Digest:
    store: Store = store_from(request)
    digest = store.get_digest(digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="unknown digest id")
    return digest
