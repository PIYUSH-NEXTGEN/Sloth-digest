# Privacy statement

SlothDigest is local-first by design. Plainly: your group chats already sit on
your devices; this project never adds a new reason for anyone else to see
them.

## What leaves your machine

- Chat content: **nothing**. Every step — parsing, storing, summarizing,
  surfacing — runs in processes on your machine.
- The only network call that carries chat content goes to `http://localhost`
  (Ollama, or `curl --max-time` in tests). With Wi-Fi off, the full pipeline
  still runs; the scheduled run and "run digest now" keep working, and the
  recorded demo is captured exactly that way (Wi-Fi disabled on camera).
- Nothing is auto-sent to anyone. Draft replies shown in "Needs you" are
  drafts; nothing is delivered or queued anywhere.

## Where your data lives

| Data | Location |
|---|---|
| Parsed messages, conversations, digests | SQLite at `SLOTH_DB_PATH` (default `./data/sloth.db`) |
| Exports dropped in for watching | `SLOTH_DROP_FOLDER` (default `./data/drop`) |
| Settings overrides | JSON next to the DB file |
| Rendered demo digest | `data/demo/digest.md` |

Deleting the folder or the database file deletes everything. There is no
cloud copy and no sync.

## Redaction before the model

Messages are redacted deterministically before any prompt is built: phone
numbers, email addresses, URLs, and long national-ID runs are replaced with
stable, reversible tokens. The system prompt never sees raw identifiers, and
the digest store keeps the redacted text so rendered output cannot leak them.
Timestamps and participants are kept locally so "who said what" can be
rebuilt from the message store rather than guessed.

## Official exports only

Supported inputs are official chat exports: WhatsApp `.txt` (Android/iOS
formats both honored), Discord via DiscordChatExporter JSON, Telegram Desktop
JSON. No self-bots, no scraping, no unofficial APIs, no credentials for
chat networks at any point in the codebase.

## Optional features are opt-in and off

- `SLOTH_SENTRY_DSN`: empty by default. When set, emits **metadata only**
  (crash traces, never messages or digests).
- `SLOTH_ELEVENLABS_API_KEY`: empty by default. When set, only the digest text
  you explicitly send for narration leaves localhost, over its official API.
- `SLOTH_TEMPORAL_ENABLED`: off by default; durable workflow mode for the
  scheduling demo is purely local orchestration.

## Quotas and rate limits

Because there is no remote API in the default path, there are none to exceed.
The model runs on your own hardware through local Ollama.

## What "local-first" does not mean

It does not mean the code is bug-free or that your OS is. The threat model is
SlothDigest not *adding* exfiltration paths, not protecting you from a
compromised machine. Keep the machine safe; the app has no secrets to steal.
