"""SQLite store (A1.4): messages, conversations, digests; FTS5 search index.

Dedupe is exact and idempotent: the natural key is
(platform, conversation_id, timestamp, sender, text_hash) enforced by a UNIQUE
constraint, so re-importing the same export (or overlapping exports) adds zero
duplicate messages (AGENTS.md 9.1).

Message ids are content-derived (sha1 of the natural key) so ids are stable
across overlapping exports - required for safe attribution references (7.4).
"""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import Digest, Message, Platform

_SCHEMA_VERSION = 1

_MIGRATIONS: list[str] = [
    # v1
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        sender TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        text TEXT NOT NULL,
        reply_to TEXT,
        is_system INTEGER NOT NULL DEFAULT 0,
        text_hash TEXT NOT NULL,
        UNIQUE (platform, conversation_id, timestamp, sender, text_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_messages_conv_ts
        ON messages (conversation_id, timestamp);
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        text, content='messages', content_rowid='rowid', tokenize='unicode61'
    );
    CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts (rowid, text) VALUES (new.rowid, new.text);
    END;
    CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts (messages_fts, rowid, text)
        VALUES ('delete', old.rowid, old.text);
    END;
    CREATE TABLE IF NOT EXISTS digests (
        id TEXT PRIMARY KEY,
        generated_at TEXT NOT NULL,
        window_start TEXT NOT NULL,
        window_end TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        json TEXT NOT NULL
    );
    """,
]


def message_natural_key_hash(text: str, sender: str, timestamp: datetime) -> str:
    raw = f"{sender}|{timestamp.isoformat()}|{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def content_message_id(
    platform: str, conversation_id: str, text: str, sender: str, timestamp: datetime
) -> str:
    uid = message_natural_key_hash(text, sender, timestamp)[:10]
    return f"{platform}:{conversation_id}:{uid}"


class Store:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        current = self._conn.execute("PRAGMA user_version").fetchone()["user_version"]
        for version in range(current, _SCHEMA_VERSION):
            self._conn.executescript(_MIGRATIONS[version])
            self._conn.execute(
                f"PRAGMA user_version = {version + 1}"  # noqa: S608 - constant
            )
        self._conn.commit()

    # -- conversations ------------------------------------------------

    def upsert_conversation(self, conversation_id: str, platform: str, name: str) -> None:
        self._conn.execute(
            """
            INSERT INTO conversations (id, platform, name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name
            """,
            (conversation_id, platform, name, datetime.now().isoformat()),
        )
        self._conn.commit()

    def list_conversations(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT c.id AS id, c.platform AS platform, c.name AS name,
                   COUNT(m.id) AS message_count,
                   MAX(m.timestamp) AS last_message_at
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY last_message_at DESC NULLS LAST, c.name
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def participants_of(self, conversation_id: str) -> list[str]:
        rows = self._conn.execute(
            """SELECT DISTINCT sender FROM messages
               WHERE conversation_id = ? AND is_system = 0 AND sender != ''
               ORDER BY sender""",
            (conversation_id,),
        ).fetchall()
        return [row["sender"] for row in rows]

    # -- messages -------------------------------------------------------

    def import_messages(
        self, conversation_id: str, platform: str, messages: list[Message]
    ) -> tuple[int, int]:
        """Insert messages idempotently; returns (imported, duplicates)."""
        imported = 0
        duplicates = 0
        for msg in messages:
            text_hash = message_natural_key_hash(msg.text, msg.sender, msg.timestamp)
            stable_id = content_message_id(
                platform, conversation_id, msg.text, msg.sender, msg.timestamp
            )
            cursor = self._conn.execute(
                """
                INSERT INTO messages
                    (id, platform, conversation_id, sender, timestamp,
                     text, reply_to, is_system, text_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, conversation_id, timestamp, sender, text_hash)
                DO NOTHING
                """,
                (
                    stable_id,
                    platform,
                    conversation_id,
                    msg.sender,
                    msg.timestamp.isoformat(),
                    msg.text,
                    msg.reply_to,
                    int(msg.is_system),
                    text_hash,
                ),
            )
            if cursor.rowcount == 0:
                duplicates += 1
            else:
                imported += 1
        self._conn.commit()
        return imported, duplicates

    def messages_in_window(
        self,
        conversation_id: str,
        start: datetime,
        end: datetime,
        include_system: bool = False,
    ) -> list[Message]:
        rows = self._conn.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ? AND timestamp >= ? AND timestamp <= ?
              AND (? OR is_system = 0)
            ORDER BY timestamp
            """,
            (conversation_id, start.isoformat(), end.isoformat(), int(include_system)),
        ).fetchall()
        return [
            Message(
                id=row["id"],
                platform=Platform(row["platform"]),
                conversation_id=row["conversation_id"],
                sender=row["sender"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                text=row["text"],
                reply_to=row["reply_to"],
                is_system=bool(row["is_system"]),
            )
            for row in rows
        ]

    # -- digests --------------------------------------------------------

    def save_digest(self, digest: Digest) -> None:
        self._conn.execute(
            """
            INSERT INTO digests (id, generated_at, window_start, window_end,
                                 model, prompt_version, json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET json = excluded.json
            """,
            (
                digest.id,
                digest.generated_at.isoformat(),
                digest.window.start.isoformat(),
                digest.window.end.isoformat(),
                digest.model,
                digest.prompt_version,
                digest.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_digest(self, digest_id: str) -> Digest | None:
        row = self._conn.execute("SELECT json FROM digests WHERE id = ?", (digest_id,)).fetchone()
        if row is None:
            return None
        return Digest.model_validate_json(row["json"])

    def get_latest_digest(self) -> Digest | None:
        row = self._conn.execute(
            "SELECT json FROM digests ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Digest.model_validate_json(row["json"])

    # -- search (FTS5; Phase 5 'ask' will build on this) -----------------

    def search(self, query: str, limit: int = 20) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT m.id FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [row["id"] for row in rows]

    def close(self) -> None:
        self._conn.close()
