"""Ask endpoint (A5.1) per contracts/openapi.yaml /ask.

Question -> hybrid retrieval (FTS5 + local embeddings) -> LLM answer with
cited message ids -> Answer {answer, sources}. Returns 501 behaviour only
when no embedder/LLM is wired; in the normal app state it answers.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.ingest import store_from
from app.llm.client import LLMClient
from app.pipeline.ask import Answer, answer_question
from app.retrieval.embeddings import Embedder, FakeEmbedder

router = APIRouter()


class AskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=1)


class AnswerResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    answer: str
    sources: list[str]


def llm_from(request: Request) -> LLMClient:
    client: LLMClient | None = getattr(request.app.state, "llm", None)
    if client is None:
        raise HTTPException(status_code=501, detail="ask not available without an LLM")
    return client


def embedder_from(request: Request) -> Embedder:
    embedder: Embedder | None = getattr(request.app.state, "embedder", None)
    if embedder is None:
        embedder = FakeEmbedder()
    return embedder


@router.post("/ask", response_model=AnswerResponse)
async def ask(request: Request, body: AskRequest) -> AnswerResponse:
    store = store_from(request)
    llm = llm_from(request)
    answer: Answer = await answer_question(
        store, embedder_from(request), llm, body.question.strip()
    )
    return AnswerResponse(answer=answer.text, sources=answer.sources)
