"""LLM abstraction (AGENTS.md A0.4).

``LLMClient`` is the swappable interface the pipeline will call in Phase 2.
``OllamaClient`` talks to local Ollama at SLOTH_OLLAMA_URL (the only permitted
network destination for chat content). ``FakeLLMClient`` scripts responses for
tests and offline CI runs - it never touches the network.
"""

from collections.abc import Sequence
from typing import Protocol

import httpx


class LLMClient(Protocol):
    """Interface for the model runtime used by the digest pipeline."""

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        """Run one generation and return the raw text output."""
        ...


class OllamaClient:
    """Local Ollama via REST (/api/generate, non-streaming)."""

    def __init__(
        self,
        ollama_url: str,
        model: str,
        *,
        timeout_seconds: float = 120.0,
        context_tokens: int = 16384,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.context_tokens = context_tokens
        self._client = httpx.AsyncClient(
            base_url=self.ollama_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        # Connection: close — pooled keep-alive sockets to local Ollama go
        # half-dead on Windows and the next request stalls interminably.
        headers = {"Connection": "close"}
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # keep the model resident across long sequential pipeline calls
            "keep_alive": "30m",
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                # Ollama silently truncates long prompts without this
                # (digest chunk prompts run ~6K tokens; gemma3 caps at 128K)
                "num_ctx": self.context_tokens,
            },
        }
        resp = await self._client.post("/api/generate", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        response = data.get("response")
        if not isinstance(response, str):
            msg = f"unexpected Ollama response shape: keys={sorted(data)}"
            raise RuntimeError(msg)
        return response


class FakeLLMClient:
    """Returns scripted responses in order; raises when the script runs dry.

    Compose with the pipeline's retry/fallback logic in tests: an empty script
    simulates the LLM failing so the fallback path is exercised. Pass
    ``default=...`` to instead answer all further calls with a canned reply.
    """

    def __init__(
        self, responses: Sequence[str], model: str = "fake", default: str | None = None
    ) -> None:
        self.model = model
        self.calls: list[dict[str, str]] = []
        self._responses = list(responses)
        self._default = default

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        self.calls.append({"prompt": prompt, "max_tokens": str(max_tokens)})
        if self._responses:
            return self._responses.pop(0)
        if self._default is None:
            raise RuntimeError("FakeLLMClient script is empty")
        return self._default
