# Architecture

SlothDigest turns chat exports into a structured morning digest with one
in-process pipeline and zero remote calls in the default path.

```mermaid
flowchart TD
    subgraph inputs
        WA["WhatsApp .txt (Android/iOS)"]
        DC["Discord (DiscordChatExporter JSON)"]
        TG["Telegram Desktop JSON"]
        DROP["SLOTH_DROP_FOLDER watcher"]
    end
    subgraph backend "FastAPI app (backend/app)"
        ING["/ingest/file<br/>decode -> detect -> redact -> parse"]
        STORE[("SQLite store<br/>messages, digests, embeddings")]
        RUN["/digest/run<br/>chunk -> extract (map) -> reduce -> score -> validate"]
        LLM["LLMClient<br/>(OllamaClient | Fake | Scripted)"]
        API["/digest/latest, /digest/{id},<br/>/sources, /settings, /ask"]
    end
    subgraph frontend "React SPA (frontend/)"
        UI["Digest | Sources | Settings"]
    end
    WA --> ING
    DC --> ING
    TG --> ING
    DROP --> ING
    ING --> STORE
    STORE --> RUN
    RUN --> LLM
    LLM -->|chunk prompts<br/>strict JSON| RUN
    RUN --> STORE
    STORE --> API
    API --> UI
```

(If your renderer does not do mermaid, the same flow in text: exports or the
drop folder land in `/ingest/file`, which decodes, detects the platform,
redacts identifiers, parses, and stores messages. `/digest/run` chunks the
window, calls the model per chunk for structured extracts, merges with the
reduce step, ranks "needs you" deterministically, validates ids against the
store, and persists the group digest. The SPA reads it back through the
contracted endpoints.)

## Layer by layer

| Stage | Where | Guarantees |
|---|---|---|
| Decode + platform detect | `app/ingest/service.py` | Encoding detection (incl. UTF-16 WhatsApp exports) + exactly one of 3 platforms per file shape |
| Redaction | `app/ingest/redact.py` | phones/emails/URLs/national-ID runs -> stable reversible tokens, offline, deterministic |
| Parsers | `app/ingest/{whatsapp,discord,telegram}.py` | system messages kept but marked, `<Media omitted>` absorbed, participants exact |
| Store | `app/store/db.py` | SQLite; stable ids derived from content+sender+timestamp so overlapping re-imports add zero duplicates; FTS5 ready |
| Chunking | `app/pipeline/chunk.py` | budget-driven, never splits a message, cuts at natural gaps |
| Extract (map) | `app/pipeline/extract.py` + `app/llm/prompts/v1_extract.md` | versioned prompt, strict JSON shape check (extra keys rejected), fenced-JSON tolerant |
| Reduce | `app/pipeline/reduce.py` + `v1_reduce.md` | merges chunk extracts; correction supersedes the superseded decision; tldr fallback when empty |
| Score | `app/pipeline/score.py` | deterministic ranking only: direct questions asked to you > mentions/aliases > keywords > VIP sender > deadlines; no LLM ranking |
| Validate | `app/pipeline/validate.py` | message ids referenced by the model are checked against the store; invented ids dropped; `NeedsYouItem.from` always re-asserted from the store |
| Persist | `app/pipeline/run.py` | digest rows saved, `GET /digest/{id}` 404-clean |

## The LLM is replaceable, not trusted

One `LLMClient` protocol (`app/llm/client.py`) behind three installations:

- `OllamaClient` — real Gemma on localhost, `SLOTH_MODEL` swappable.
- `FakeLLMClient` — scripts responses for unit tests and CI.
- `ScriptedPipelineClient` (`eval/run_eval.py`) — eval-only stand-in that
  answers prompts with ground-truth JSON so the pipeline's recall/precision
  numbers isolate workflow bugs from model judgement.

Everything structural — attribution, needs-you ranking, eligibility of
message ids, correction precedence — is decided by deterministic code, never
by the model. Attribution accuracy is therefore 100% by construction (see the
[Evaluation section of the README](../README.md#evaluation)).

## Frontend

Vite + React SPA, hash routing, typed API client generated from
`contracts/`, MSW for the mock-recorded demo path and Vitest; a Playwright
smoke (`frontend/tests-smoke`) that uploads a real fixture and reads a digest
card. `/api` proxies to the backend during dev.

## Testing surface

- `backend/tests` — parser fixtures (the same synthetic datasets drive the
  parsers and the eval), store dedupe, pipeline unit tests.
- `eval/run_eval.py` — the real HTTP API end-to-end over 8 datasets; also
  generates `eval/report.md`.
- `scripts/offline_check.sh` — runs the pipeline with network blocked.
- `frontend` — Vitest + Playwright smoke.
