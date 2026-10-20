# COORDINATION

## Current phase
Phase 0

## Task board
| ID | Owner | Task | Status | Notes |
|----|-------|------|--------|-------|
| A0.1 | A | Scaffold backend + config | done | uv project, FastAPI app factory, /health green (ruff+mypy strict+pytest) |
| A0.2 | A | contracts/digest.schema.json + openapi.yaml | done | v0.1.0, OpenAPI 3.0.3, 8 paths, refs validated |
| A0.3 | A | models.py (Message, Conversation, Digest) | done | pydantic v2; test enforces field sync with digest.schema.json |
| A0.4 | A | llm/client.py (LLMClient protocol, OllamaClient, FakeLLMClient) | todo | |
| A0.5 | A | Makefile targets + .env.example | todo | |
| B0.1 | B | Scaffold frontend (Vite + React + TS, eslint/prettier, vitest) | done | Vite 6 + React 18 + TS strict; vitest 3 (green: 7 tests), eslint 9 flat config, prettier seeded; UI components built vs sample digest from 7.1; `npm run dev` on :5173, proxies /api → :8000 |
| B0.2 | B | COORDINATION.md, README skeleton, LICENSE, CI workflow | done | MIT LICENSE; README skeleton (full Section-10 content lands with MVP); .github/workflows/ci.yml — backend job wires uv (uses `uv sync --frozen`, `ruff check app tests`); frontend job eslint+vitest+build |
| B0.3 | B | Typed API client + MSW mocks | unblocked | A0.2 contracts landed (types.ts drafted vs 7.1 — will reconcile against contracts/digest.schema.json); MSW mocks next |
| B0.4 | B | scripts/gen_synthetic_chats.py (synthetic chats, planted facts) | todo | |

## Contract changes (Agent A appends, newest first)
- 2026-10-20 (A): Initial contracts v0.1.0 — `contracts/digest.schema.json` (Message, Conversation, Digest; platforms whatsapp/discord/telegram) and `contracts/openapi.yaml` (OpenAPI 3.0.3, 8 paths: /health, /ingest/file, /sources, /digest/run, /digest/latest, /digest/{id}, /ask, /settings). `/ask` returns 501 until Phase 5. B0.3 unblocked: mock against these now.

## Requests to Agent A (Agent B appends)
- (none)
- 2026-10-20 (B): `ruff check app tests` currently reports 1 fixable `I001` (unsorted imports) in `backend/tests/unit/test_llm_client.py:3` — your file, so not touching it. It will fail the CI backend job (.github/workflows/ci.yml, just added) until fixed.

## Requests to Agent B (Agent A appends)
- A: There are now two coordination boards: the canonical `COORDINATION.md` (this file) and the older `contribution.md`. Please delete or archive `contribution.md` once you're done with it; I'll keep both synced in the meantime (status above is current here).

## Decisions log (either agent, newest first)
- 2026-10-20 (B): `COORDINATION.md` is the single canonical coordination board. `contribution.md` (A's working title) gets only status syncs for B's rows; all future updates happen here.
- 2026-10-20 (B): Retiring `contribution.md`: synced A's copy with the current board, asked A (there and in canonical) to stop writing to it; I will delete it once A confirms. Until then both stay synced.

## Blockers
- (none)
