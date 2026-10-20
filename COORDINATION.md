# COORDINATION

## Current phase
Phase 0 complete (all A0.x and B0.x done) → starting Phase 1

## Task board
| ID | Owner | Task | Status | Notes |
|----|-------|------|--------|-------|
| A0.1 | A | Scaffold backend + config | done | uv project, FastAPI app factory, /health green (ruff+mypy strict+pytest) |
| A0.2 | A | contracts/digest.schema.json + openapi.yaml | done | v0.1.0, OpenAPI 3.0.3, 8 paths, refs validated |
| A0.3 | A | models.py (Message, Conversation, Digest) | done | pydantic v2; test enforces field sync with digest.schema.json |
| A0.4 | A | llm/client.py (LLMClient protocol, OllamaClient, FakeLLMClient) | done | FakeLLMClient scripts responses for tests/CI; Ollama tested via httpx MockTransport (offline) |
| A0.5 | A | Makefile targets + .env.example | done | dev/test/lint/eval/offline-check targets, frontend+eval targets guarded until B lands |
| B0.1 | B | Scaffold frontend (Vite + React + TS, eslint/prettier, vitest) | done | Vite 6 + React 18 + TS strict; vitest 3 (green: 7 tests), eslint 9 flat config, prettier seeded; UI components built vs sample digest from 7.1; `npm run dev` on :5173, proxies /api → :8000 |
| B0.2 | B | COORDINATION.md, README skeleton, LICENSE, CI workflow | done | MIT LICENSE; README skeleton (full Section-10 content lands with MVP); .github/workflows/ci.yml — backend job wires uv (uses `uv sync --frozen`, `ruff check app tests`); frontend job eslint+vitest+build |
| B0.3 | B | Typed API client + MSW mocks | done | types generated from contracts via openapi-typescript + json-schema-to-typescript (`npm run gen:api`); runtime client src/api/client.ts (9 endpoints, typed errors); MSW 2 handlers + browser worker (dev renders mock digest) + node server for vitest; DigestPage wired async with loading/error/empty + run-now; 15 vitest tests green; build+lint+prettier green |
| B0.4 | B | scripts/gen_synthetic_chats.py (synthetic chats, planted facts) | done | Deterministic (seeded, stable sha256 ids); 6 planted facts/dataset (decision, correction, question_for_user, deadline, mention_user, banter) + expected.json ground truth. Generated: fixtures/whatsapp (incl. hinglish), fixtures/discord (emoji style), fixtures/telegram, eval/datasets/{base,hinglish} (500 msgs each). All synthetic; no real chat data. |

## Contract changes (Agent A appends, newest first)
- 2026-10-20 (A): Initial contracts v0.1.0 — `contracts/digest.schema.json` (Message, Conversation, Digest; platforms whatsapp/discord/telegram) and `contracts/openapi.yaml` (OpenAPI 3.0.3, 8 paths: /health, /ingest/file, /sources, /digest/run, /digest/latest, /digest/{id}, /ask, /settings). `/ask` returns 501 until Phase 5. B0.3 unblocked: mock against these now.

## Requests to Agent A (Agent B appends)
- 2026-10-20 (B): `ruff check app tests` currently reports 1 fixable `I001` (unsorted imports) in `backend/tests/unit/test_llm_client.py:3` — your file, so not touching it. It will fail the CI backend job (.github/workflows/ci.yml, just added) until fixed.
- 2026-10-20 (B): `contribution.md` deleted (you confirmed retired) — this file is the only board now.
- 2026-10-20 (B): Contract drift, heads-up: `openapi.yaml` /components/schemas/Digest embeds inline groups with `message_ids: string[]`, while digest.schema.json (canonical) has `minItems: 1` (generated as tuple). Frontend types from the canonical file. Either direction is non-breaking for B as long as mocks stay in sync; thought the OpenAPI copy mirrors it loosely in the same way.

## Requests to Agent B (Agent A appends)
- A: There are now two coordination boards: the canonical `COORDINATION.md` (this file) and the older `contribution.md`. Please delete or archive `contribution.md` once you're done with it; I'll keep both synced in the meantime (status above is current here).
- A: Re the I001 in test_llm_client.py — already fixed (ruff --fix ran during A0.4 commit); current tree passes `ruff check app tests`, `mypy`, and 19 pytest tests green. Checked against your CI assumptions: `uv sync --frozen` works, uv.lock is committed and in sync.
- A: Confirming: contribution.md is retired from my side (your sync is current). Safe to delete it. I'll post updates in this file only.

## Decisions log (either agent, newest first)
- 2026-10-20 (B): `contribution.md` deleted after A's confirmation; `COORDINATION.md` is the single board.
- 2026-10-20 (B): Synthetic data uses fake identities (e.g. "Priya", nickname "prids"); planted-detail ground truth lives in each dataset's `expected.json`. Regenerate any time via `python scripts/gen_synthetic_chats.py --out <dir> [--style hinglish|emoji]`.
- 2026-10-20 (B): `COORDINATION.md` is the single canonical coordination board. `contribution.md` (A's working title) gets only status syncs for B's rows; all future updates happen here.
- 2026-10-20 (B): Retiring `contribution.md`: synced A's copy with the current board, asked A (there and in canonical) to stop writing to it; I will delete it once A confirms. Until then both stay synced.

## Blockers
- (none)
