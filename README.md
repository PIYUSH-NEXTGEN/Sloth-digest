# SlothDigest

> **Sleep through the chat. Wake up caught up.**

SlothDigest is a local-first, open-source tool that reads your group chats
(WhatsApp, Discord, Telegram) and every morning hands you a short, structured
digest: what happened, what needs *you*, what was decided, and who said what.
It runs entirely on your own machine with an open-weight model (Gemma via
Ollama). No chat content ever leaves your computer.

_TODO: 10-second demo GIF (added in Phase 7 with the submission)._

## Why local + open matters

- **Privacy by architecture, not by policy.** Your chats are processed on your
  machine. The only network call allowed with chat content is to `localhost`
  (Ollama).
- **Works offline.** With Wi-Fi off, the full pipeline — ingest, summarize,
  view digest — still works.
- **Free forever, swappable model.** No API bills, no rate limits. Swap the
  model (`SLOTH_MODEL`) or fine-tune it later for your language.

## Features

- Morning digest per group chat: TL;DR, **Needs you**, **Decisions**,
  **By person**, deadlines, and a collapsed "skipped N messages of banter".
- Official exports only: WhatsApp `.txt`, Discord (DiscordChatExporter),
  Telegram Desktop JSON. No self-bots, no scraping.
- "Who said what" is never guessed by the model — it is rebuilt from the
  parsed message store for 100% attribution accuracy by construction.
- Scheduled daily run, or "run digest now".
- Optional models/features are strictly opt-in and off by default.

_Quickstart, export guides, digest example, architecture, privacy statement,
configuration table, and credits are being filled in as the MVP (Phases 0–3)
lands._

## Quickstart (planned — first cut in Phase 3)

```bash
# 1. Install Ollama and pull the model
ollama pull gemma3:4b

# 2. Clone and run
make dev

# 3. Drop a chat export into the app, or wait for the morning schedule
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `SLOTH_MODEL` | `gemma3:4b` | Ollama model used for summarization |
| `SLOTH_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `SLOTH_DB_PATH` | `./data/sloth.db` | SQLite database path |
| `SLOTH_DROP_FOLDER` | `./data/drop` | Folder watched for new exports |
| `SLOTH_DIGEST_TIME` | `06:00` | Local time of the morning digest run |
| `SLOTH_USER_NAMES` | your name | Names/nickmarks the digest uses to detect "needs you" |
| `SLOTH_SENTRY_DSN` | empty (off) | Optional metadata-only tracing |
| `SLOTH_ELEVENLABS_API_KEY` | empty (off) | Optional spoken briefing |
| `SLOTH_TEMPORAL_ENABLED` | `false` | Optional durable workflow mode |

## Project status

Phase 3 of the two-phase MVP — backend pipeline and frontend surface are
landed; settings UI and demo/docs polish are in flight.

- [AGENTS.md](agent.md) — how the two-agent repo is organized
- [COORDINATION.md](COORDINATION.md) — live task board
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to help (even "good first issues")
- [LICENSE](LICENSE) — MIT

## Evaluation

The pipeline is measured against synthetic datasets only (seeded generator,
planted facts, no real chats): 8 datasets across WhatsApp (Android/iOS,
Hinglish, edge cases), Discord, and Telegram, 240–500 messages each. Each run
ingests the export through the real HTTP API and scores the produced digest
against the planted ground truth. See [eval/report.md](eval/report.md) and
[eval/run_eval.py](eval/run_eval.py) for details.

The table below is the `--fake` baseline: the LLM step is replaced by
`ScriptedPipelineClient`, a deterministic stand-in that answers prompts with
perfect-content JSON built from the ground truth — so these numbers measure
the *workflow* (chunking, strict JSON validation, reduce merging, deterministic
scoring, attribution), not a model. Real Ollama numbers land with `--live`.

- **needs-you recall: 100%** (every planted question/mention surfaces)
- **decision recall: 100%** (corrections supersede their original decision)
- **attribution accuracy: 100%** — "who said what" is rebuilt from the parsed
  message store, never from model output, so this is 100% by construction
- schema validity: 8/8 digests (canonical JSON Schema)

## License

MIT — see [LICENSE](LICENSE).
