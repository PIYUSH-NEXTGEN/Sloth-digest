"""Local hybrid retrieval (A5.1): FTS5 keyword match + in-device embeddings.

Everything stays on the machine: embeddings are computed locally (Ollama
``/api/embeddings`` in prod, a deterministic hash embedder in tests) and
persisted in the SQLite db. Cosine similarity ranks semantic candidates;
FTS5 ranks lexical ones; the union feeds the answer prompt. No external
embedding APIs, ever.
"""

import hashlib
import math
import re
from typing import Protocol

import httpx

from app.store.db import Store

EMBED_DIM = 256  # FakeEmbedder hash space; highs dims keep word collisions rare
_MIN_SEMANTIC_SIM = 0.12  # below this a semantic candidate is noise
_EMBED_URL_PATH = "/api/embeddings"
_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Deterministic hashed bag-of-words vectors (offline tests only)."""

    def __init__(self, dim: int = EMBED_DIM) -> None:
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in _WORD_RE.findall(text.lower()):
            idx = int.from_bytes(hashlib.sha1(word.encode()).digest()[:4], "big") % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OllamaEmbedder:
    """Local Ollama embeddings (e.g. nomic-embed-text)."""

    def __init__(
        self,
        ollama_url: str,
        model: str,
        *,
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.ollama_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            response = await self._client.post(
                _EMBED_URL_PATH, json={"model": self.model, "prompt": text}
            )
            response.raise_for_status()
            vectors.append(list(response.json()["embedding"]))
        return vectors


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


async def ensure_embeddings(store: Store, embedder: Embedder, *, batch_limit: int = 500) -> int:
    """Backfill embeddings for messages missing one; returns count embedded."""
    messages = store.embeddable_messages(limit=batch_limit)
    if not messages:
        return 0
    vectors = await embedder.embed([m.text for m in messages])
    for message, vector in zip(messages, vectors, strict=False):
        store.save_embedding(message.id, vector)
    store.flush_embeddings()
    return len(messages)


def hybrid_candidates(
    store: Store,
    question_text: str,
    question_vec: list[float],
    *,
    fts_limit: int = 24,
    semantic_limit: int = 24,
) -> list[tuple[str, float]]:
    """Union of lexical + semantic candidates as (message_id, score)."""
    staged: dict[str, float] = {}
    for message_id in store.search(question_norm(question_text), limit=fts_limit):
        staged[message_id] = max(staged.get(message_id, 0.0), 1.0)
    vectors = store.existing_embeddings()
    sims: list[tuple[float, str]] = []
    for message_id, vector in vectors.items():
        sims.append((cosine_similarity(question_vec, vector), message_id))
    sims.sort(key=lambda pair: pair[0], reverse=True)
    for score, message_id in sims[:semantic_limit]:
        if score < _MIN_SEMANTIC_SIM:
            continue
        staged[message_id] = max(staged.get(message_id, 0.0), score)
    return sorted(staged.items(), key=lambda pair: pair[1], reverse=True)


def question_norm(text: str) -> str:
    """FTS5-safe query: strip operator punct, keep terms."""
    words = _WORD_RE.findall(text)
    return " OR ".join(f'"{w}"' for w in words) if words else '""'
