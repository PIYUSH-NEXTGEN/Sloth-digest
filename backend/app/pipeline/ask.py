"""Ask-your-chats pipeline (A5.1): hybrid retrieval -> cited LLM answer.

The LLM answers only from retrieved context and must cite message ids from
it (see llm/prompts/v1_ask.md). Sources are the ids we actually presented
to the model, intersected with ids it cited - no invented "sources".
"""

import logging
import re
from dataclasses import dataclass
from importlib import resources

from app.llm.client import LLMClient
from app.llm.prompts import PROMPT_VERSION
from app.models import Message
from app.pipeline.retry import run_with_retry
from app.retrieval.embeddings import Embedder, ensure_embeddings, hybrid_candidates
from app.store.db import Store

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[([a-z]+:[^:\s]+):([0-9a-f]+|\d+)\]")
_TIMESTAMP_FMT = "%H:%M"


def get_ask_template(version: str = PROMPT_VERSION) -> str:
    path = resources.files("app") / "llm" / "prompts" / f"{version}_ask.md"
    return path.read_text(encoding="utf-8")


@dataclass
class Answer:
    text: str
    sources: list[str]


def format_context(messages: list[Message]) -> str:
    lines: list[str] = []
    for message in messages:
        hhmm = message.timestamp.strftime(_TIMESTAMP_FMT)
        prefix = "[system] " if message.is_system else ""
        lines.append(f"{message.id} [{hhmm}] {prefix}{message.sender}: {message.text}")
    return "\n".join(lines)


def extract_citations(text: str, available: set[str]) -> list[str]:
    """[id] citations appearing in the answer text, limited to context ids."""
    found: list[str] = []
    for match in _CITATION_RE.finditer(text):
        candidate = f"{match.group(1)}:{match.group(2)}"
        if candidate in available and candidate not in found:
            found.append(candidate)
    return found


async def answer_question(
    store: Store,
    embedder: Embedder,
    client: LLMClient,
    question: str,
    *,
    context_limit: int = 10,
    max_tokens: int = 500,
) -> Answer:
    await ensure_embeddings(store, embedder)
    ranked = hybrid_candidates(store, question, (await embedder.embed([question]))[0])
    picked: list[Message] = []
    seen: set[str] = set()
    for message_id, _score in ranked[:context_limit]:
        message = store.get_message(message_id)
        if message is not None and message.id not in seen:
            picked.append(message)
            seen.add(message.id)
    if not picked:
        return Answer(text="No messages in your chats cover this.", sources=[])
    prompt = (
        get_ask_template(PROMPT_VERSION)
        + f"\n\n## Context\n{format_context(picked)}\n\n## Question\n{question}"
    )
    raw = await run_with_retry(
        lambda: client.complete(prompt, max_tokens=max_tokens, temperature=0.0),
        attempts=2,
        retry_on=(ValueError,),
    )
    text = raw.strip()
    sources = extract_citations(text, seen)
    return Answer(text=text, sources=sources)
