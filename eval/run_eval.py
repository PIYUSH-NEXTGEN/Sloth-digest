#!/usr/bin/env python3
"""SlothDigest quality harness (eval/run_eval.py, Agent B).

Runs the REAL pipeline (in-process FastAPI + SQLite + FakeLLMClient) over the
synthetic datasets in fixtures/ and eval/datasets/, then scores the digests
against each dataset's expected.json ground truth. Deterministic: --fake mode
is CI-safe (no model; the empty LLM script drives the heuristic fallback).

Modes:
    python eval/run_eval.py --fake          # heuristic baseline, no network
    python eval/run_eval.py --live          # local Gemma via Ollama (manual)
    python eval/run_eval.py --json out.json # machine-readable metrics

Exit code is 0 when every run is schema-valid, 1 otherwise (CI gate).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.llm.client import FakeLLMClient  # noqa: E402
from app.main import create_app  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402


@dataclass
class DatasetCase:
    directory: str
    chat_path: Path
    expected: dict


def discover_datasets() -> list[DatasetCase]:
    """fixtures/ and eval/datasets/: any dir holding chat.txt/chat.json."""
    cases: list[DatasetCase] = []
    for search in ("fixtures", "eval/datasets"):
        for chat in sorted((REPO_ROOT / search).glob("**/chat.*")):
            expected_path = chat.parent / "expected.json"
            if not expected_path.exists():
                continue
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            cases.append(
                DatasetCase(
                    directory=str(chat.parent.relative_to(REPO_ROOT)),
                    chat_path=chat,
                    expected=expected,
                )
            )
    return cases


REQUIRED_DIGEST_KEYS = (
    "id",
    "generated_at",
    "window",
    "model",
    "prompt_version",
    "groups",
)
REQUIRED_GROUP_KEYS = (
    "conversation_id",
    "platform",
    "name",
    "message_count",
    "skipped_count",
    "tldr",
    "needs_you",
    "decisions",
    "by_person",
    "deadlines",
)


def digest_is_valid(digest: dict) -> bool:
    """Structural check against the canonical Digest shape (7.1/contracts)."""
    if any(key not in digest for key in REQUIRED_DIGEST_KEYS):
        return False
    for group in digest.get("groups", []):
        if any(key not in group for key in REQUIRED_GROUP_KEYS):
            return False
        for item in group["needs_you"]:
            if not all(item.get(key) for key in ("message_id", "from", "summary", "reason")):
                return False
        for decision in group["decisions"]:
            if not decision.get("text") or not decision.get("message_ids"):
                return False
        for deadline in group["deadlines"]:
            if not deadline.get("text") or not deadline.get("message_ids"):
                return False
        for person in group["by_person"]:
            if not person.get("name") or not person.get("points"):
                return False
    return True


def ingest(client: TestClient, case: DatasetCase) -> dict:
    payload = case.chat_path.read_bytes()
    fields: dict = {}
    if "conversation_name" in case.expected:
        fields["conversation_name"] = case.expected["conversation_name"]
    response = client.post(
        "/ingest/file",
        files={"file": (case.chat_path.name, payload)},
        data=fields,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    # re-import safety: uploading the same export again adds nothing
    repeat = client.post(
        "/ingest/file",
        files={"file": (case.chat_path.name, payload)},
        data=fields,
    )
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["imported"] == 0, "re-import created duplicate messages"
    return result


def run_and_fetch(client: TestClient, conversation_ids: list[str]) -> tuple[dict, float]:
    started = time.perf_counter()
    response = client.post(
        "/digest/run",
        json={
            "since": "2026-10-19T00:00:00Z",
            "conversation_ids": conversation_ids,
        },
    )
    assert response.status_code == 202, response.text
    digest_id = response.json()["digest_id"]
    fetched = client.get(f"/digest/{digest_id}")
    assert fetched.status_code == 200, fetched.text
    return fetched.json(), time.perf_counter() - started


def score(case: DatasetCase, digest: dict) -> dict:
    """Compare the produced digest against the planted-fact ground truth."""
    groups = digest["groups"]
    facts = [
        f
        for f in case.expected.get("planted_facts", [])
        if f["kind"] != "banter"
    ]
    needs_you_ids = {
        item["message_id"] for group in groups for item in group["needs_you"]
    }
    from_by_id = {
        item["message_id"]: item["from"] for group in groups for item in group["needs_you"]
    }
    decision_texts = " \n ".join(
        decision["text"] for group in groups for decision in group["decisions"]
    )
    decision_norm = _norm(decision_texts)

    question_facts = [f for f in facts if f["kind"] in ("question_for_user", "mention_user")]
    decision_facts = [f for f in facts if f["kind"] in ("decision", "correction")]
    deadline_facts = [f for f in facts if f["kind"] == "deadline"]

    needs_recall = (
        sum(1 for f in question_facts if f["message_id"] in needs_you_ids)
        / max(len(question_facts), 1)
    )
    decision_recall = (
        sum(1 for f in decision_facts if _contains_norm(decision_norm, f["text"]))
        / max(len(decision_facts), 1)
    )
    deadline_recall = (
        sum(1 for f in deadline_facts if _contains_norm(decision_norm, f["text"]))
        / max(len(deadline_facts), 1)
    )

    # attribution: every needs_you `from` must equal the planted fact's sender
    # when the item points at a planted message; real messages count via store.
    mentioned_ids = [f["message_id"] for f in question_facts if f["message_id"] in needs_you_ids]
    attribution_hits = sum(
        1
        for message_id in mentioned_ids
        if from_by_id[message_id]
        == next(f["sender"] for f in question_facts if f["message_id"] == message_id)
    )
    total_in_window = sum(group["message_count"] for group in groups)
    surfaced = sum(
        len(group["needs_you"]) + len(group["decisions"]) + len(group["by_person"])
        for group in groups
    )
    return {
        "dataset": case.directory,
        "schema_valid": digest_is_valid(digest),
        "needs_you_recall": needs_recall,
        "decision_recall": decision_recall,
        "deadline_recall": deadline_recall,
        "attribution_accuracy": attribution_hits / max(len(mentioned_ids), 1),
        "groups": len(groups),
        "messages_in_window": total_in_window,
        "surfaced_items": surfaced,
    }


def _norm(text: str) -> str:
    return "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()


def _contains_norm(haystack_tokens: list[str], needle: str) -> bool:
    needle_tokens = _norm(needle)
    if not needle_tokens:
        return False
    needle_joined = " ".join(needle_tokens)
    haystack_joined = " ".join(haystack_tokens)
    return needle_joined in haystack_joined


def run_dataset_livetest(case: DatasetCase, app) -> tuple[dict, float]:
    with TestClient(app) as client:
        ingest_result = ingest(client, case)
        digest, latency = run_and_fetch(client, [ingest_result["conversation_id"]])
        return score(case, digest), latency


EMPTY_EXTRACT = json.dumps(
    {
        "topics": [],
        "decisions": [],
        "questions_for_user": [],
        "deadlines": [],
        "per_person": [],
    },
    ensure_ascii=False,
)

EMPTY_REDUCE = json.dumps(
    {
        "tldr": "Nothing needs attention; the window was mostly banter.",
        "topics": [],
        "decisions": [],
        "deadlines": [],
        "per_person": [],
    },
    ensure_ascii=False,
)


def run_case(case: DatasetCase, live: bool) -> tuple[dict, float]:
    with tempfile.TemporaryDirectory(prefix="sloth-eval-") as tmp:
        db_path = str(Path(tmp) / "sloth.db")
        Path(tmp, "drop").mkdir()
        set_env_for_settings(db_path)
        get_settings.cache_clear()
        if live:
            app = create_app()
        else:
            app = create_app(
                llm=FakeLLMClient([EMPTY_EXTRACT] * 50 + [EMPTY_REDUCE] * 50),
            )
        try:
            return run_dataset_livetest(case, app)
        finally:
            get_settings.cache_clear()


def set_env_for_settings(db_path: str) -> None:
    import os

    os.environ["SLOTH_DB_PATH"] = db_path
    os.environ["SLOTH_DROP_FOLDER"] = str(Path(db_path).parent / "drop")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", action="store_true", help="heuristic baseline, no LLM")
    parser.add_argument("--live", action="store_true", help="use Ollama-backed client")
    parser.add_argument("--json", dest="json_out", type=Path, help="also write JSON metrics")
    args = parser.parse_args()
    if args.live and args.fake:
        parser.error("--fake and --live are mutually exclusive")

    cases = discover_datasets()
    if not cases:
        print("no datasets with expected.json found", file=sys.stderr)
        return 1
    print(f"eval: {len(cases)} datasets, mode={'live' if args.live else 'fake'}")
    rows = []
    for case in cases:
        scored, latency = run_case(case, args.live)
        scored["latency_s"] = round(latency, 3)
        rows.append(scored)
        state = "ok" if scored["schema_valid"] else "INVALID"
        print(
            f"  {scored['dataset']:<38} {state}  needs_you={scored['needs_you_recall']:.0%}"
            f"  decisions={scored['decision_recall'] + scored['deadline_recall']:.0%}"
            f"  attribution={scored['attribution_accuracy']:.0%}"
        )
    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_report(rows)
    invalid = [row for row in rows if not row["schema_valid"]]
    if invalid:
        print(f"FAIL: schema-invalid digests: {[row['dataset'] for row in invalid]}")
        return 1
    return 0


def write_report(rows: list[dict]) -> None:
    lines = [
        "# SlothDigest eval report",
        "",
        "Deterministic runs over the synthetic datasets (no real chats).",
        "`--fake` mode exercises the full pipeline with the heuristic fallback digest.",
        "",
        "| dataset | schema | needs-you recall | decision+deadline recall | attribution | groups | messages | surfaced | latency s |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['dataset']} | {'ok' if row['schema_valid'] else 'INVALID'}"
            f" | {row['needs_you_recall']:.0%} | {(row['decision_recall'] + row['deadline_recall']):.0%}"
            f" | {row['attribution_accuracy']:.0%} | {row['groups']} | {row['messages_in_window']}"
            f" | {row['surfaced_items']} | {row['latency_s']} |"
        )
    out = REPO_ROOT / "eval" / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    raise SystemExit(main())
