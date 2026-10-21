"""Unit tests for the LLM client layer (all offline: httpx MockTransport)."""

import json

import httpx
import pytest

from app.llm.client import FakeLLMClient, LLMClient, OllamaClient


@pytest.mark.asyncio
async def test_fake_llm_scripted_responses() -> None:
    client = FakeLLMClient(["first", "second"])
    assert await client.complete("p1", max_tokens=100, temperature=0.0) == "first"
    assert await client.complete("p2", max_tokens=100, temperature=0.0) == "second"
    assert [c["prompt"] for c in client.calls] == ["p1", "p2"]


@pytest.mark.asyncio
async def test_fake_llm_raises_when_script_empty() -> None:
    client = FakeLLMClient([])
    with pytest.raises(RuntimeError, match="empty"):
        await client.complete("p", max_tokens=10, temperature=0.0)


@pytest.mark.asyncio
async def test_ollama_client_returns_text() -> None:
    body = {"response": "hello digest", "model": "gemma3:4b", "done": True}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        payload = json.loads(request.content)
        assert payload["model"] == "gemma3:4b"
        assert payload["stream"] is False
        assert payload["options"]["num_predict"] == 256
        assert payload["options"]["temperature"] == 0.2
        assert payload["options"]["num_ctx"] == 4096
        return httpx.Response(200, json=body)

    client = OllamaClient(
        ollama_url="http://localhost:11434",
        model="gemma3:4b",
        context_tokens=4096,
        transport=httpx.MockTransport(handler),
    )
    out = await client.complete("summarize", max_tokens=256, temperature=0.2)
    assert out == "hello digest"


@pytest.mark.asyncio
async def test_ollama_client_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = OllamaClient(
        ollama_url="http://localhost:11434",
        model="gemma3:4b",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.complete("p", max_tokens=8, temperature=0.0)


@pytest.mark.asyncio
async def test_ollama_client_raises_on_bad_shape() -> None:
    body: dict[str, object] = {"model": "gemma3:4b", "done": True}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    client = OllamaClient(
        ollama_url="http://localhost:11434",
        model="gemma3:4b",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RuntimeError, match="response shape"):
        await client.complete("p", max_tokens=8, temperature=0.0)


def test_both_clients_declare_complete() -> None:
    assert all(hasattr(cls, "complete") for cls in [OllamaClient, FakeLLMClient])
    assert LLMClient is not None  # protocol exists and is importable
