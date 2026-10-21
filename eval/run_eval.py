#!/usr/bin/env python3
"""SlothDigest quality harness (eval/run_eval.py, Agent B).

Runs the REAL pipeline (in-process FastAPI + SQLite) over the synthetic
datasets in fixtures/ and eval/datasets/, then scores the digests against each
dataset's expected.json ground truth.

Modes:
    --fake   CI-safe baseline: ScriptedPipelineClient answers chunk prompts or
             reduce prompts with perfect-content JSON built from expected.json,
             so the full pipeline (chunk, validate, reduce, score, attribution
             check) is measured while the "model" is deterministic.
    --live   Real Gemma via Ollama, manual run (may degrade gracefully through
             the heuristic fallback when the model misbehaves).
    --json   Also dump raw row metrics.

Exit code is 0 when every run is schema-valid, 1 otherwise (CI gate). Digest
attribution is expected to be 100% by construction (AGENTS.md 7.4).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import get_settings
from app.llm.client import LLMClient
from app.main import create_app
from fastapi.testclient import TestClient

_MESSAGE_LINE = re.compile(
    r"^(?P<id>\S+) \[\d{2}:\d{2}\] (?:\[system\] )?(?P<sender>[^:\[]+): (?P<text>.*)$"
)


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower(), flags=re.UNICODE) if t]


class ScriptedPipelineClient(LLMClient):
    """Deterministic ground-truth LLM stand-in for --fake eval runs.

    Reads the message lines embedded in each prompt (same format the pipeline
    gives real models) and answers from the planted-fact ground truth only:
    it can find exactly what expected.json says exists, nothing more. This
    exercises chunking, strict-JSON validation, reduce merging, scoring and
    the attribution check with perfect semantics - so any failure is due to
    the workflow, not model judgement.
    """

    model = "scripted"

    def __init__(self, facts: list[dict]) -> None:
        self._facts = facts
        self.calls = 0

    async def complete(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        self.calls += 1
        if '"chunk_summaries"' in prompt:
            return self._reduce(prompt)
        return self._extract(prompt)

    def _extract(self, prompt: str) -> str:
        decisions: list[dict] = []
        questions: list[dict] = []
        per_person: list[dict] = []
        seen: set[str] = set()
        for raw_line in prompt.splitlines():
            match = _MESSAGE_LINE.match(raw_line.strip())
            if match is None:
                continue
            message_id = match.group("id")
            if message_id in seen:
                continue
            seen.add(message_id)
            line_tokens = _tokens(match.group("text"))
            sender = match.group("sender").strip()
            for fact in self._facts:
                fact_tokens = _tokens(fact["text"])
                if fact_tokens and set(fact_tokens) <= set(line_tokens):
                    if fact["kind"] in ("decision", "correction", "deadline"):
                        decisions.append(
                            {"text": fact["text"], "message_ids": [message_id]}
                        )
                    else:
                        questions.append(
                            {"message_id": message_id, "question": fact["text"]}
                        )
                    if not any(p["name"] == sender for p in per_person):
                        per_person.append(
                            {"name": sender, "points": ["surfaced planted facts"]}
                        )
        return json.dumps(
            {
                "topics": [],
                "decisions": decisions,
                "questions_for_user": questions,
                "deadlines": [],
                "per_person": per_person,
            },
            ensure_ascii=False,
        )

    def _reduce(self, prompt: str) -> str:
        summaries = self._summaries_from_reduce_prompt(prompt)
        decisions: list[dict] = []
        deadlines: list[dict] = []
        per_person: list[dict] = []
        for summary in summaries:
            for decision in summary.get("decisions", []):
                _merge_uniq(decisions, decision["text"], decision["message_ids"])
            for deadline in summary.get("deadlines", []):
                _merge_uniq(deadlines, deadline["text"], deadline["message_ids"])
            for person in summary.get("per_person", []):
                existing = next((p for p in per_person if p["name"] == person["name"]), None)
                if existing is None:
                    per_person.append({"name": person["name"], "points": list(person["points"])})
                else:
                    existing["points"] = list(
                        dict.fromkeys(existing["points"] + person["points"])
                    )
        # Ground-truth correction rule (AGENTS 9.3): the correction supersedes
        # the original decision in the final group digest.
        corrections = {
            self._norm_key(f["text"])
            for f in self._facts
            if f["kind"] == "correction"
        }
        originals = {
            self._norm_key(f["text"])
            for f in self._facts
            if f["kind"] == "decision"
        }
        if corrections:
            decisions = [d for d in decisions if self._norm_key(d["text"]) not in originals]
        decision_texts = [d["text"] for d in decisions]
        deadline_texts = [d["text"] for d in deadlines]
        parts = []
        if decision_texts:
            parts.append("Final plan: " + "; ".join(decision_texts))
        if deadline_texts:
            parts.append("Open deadlines: " + "; ".join(deadline_texts))
        tldr = ". ".join(parts) if parts else "Pure banter; nothing to act on."
        return json.dumps(
            {
                "tldr": tldr[:400],
                "topics": [],
                "decisions": decisions,
                "deadlines": deadlines,
                "per_person": per_person,
            },
            ensure_ascii=False,
        )

    def _summaries_from_reduce_prompt(self, prompt: str) -> list[dict]:
        # The prompt template itself contains a ```json example fence, so only
        # trust fences after the "## Input" marker (build_reduce_prompt format).
        _, _, section = prompt.rpartition("## Input")
        payload_match = re.search(r"```json\s*(\{.*?\})\s*```", section, re.DOTALL)
        if payload_match is None:
            return []
        try:
            return json.loads(payload_match.group(1))["chunk_summaries"]
        except (json.JSONDecodeError, KeyError):
            return []

    def _norm_key(self, text: str) -> str:
        return " ".join(_tokens(text))


def _merge_uniq(bucket: list[dict], text: str, message_ids: list) -> None:
    for item in bucket:
        if item["text"] == text:
            merged = list(dict.fromkeys(item["message_ids"] + list(message_ids)))
            item["message_ids"] = merged
            return
    bucket.append({"text": text, "message_ids": list(message_ids)})


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


def push_settings(client: TestClient, case: DatasetCase) -> None:
    settings = {
        "user_names": case.expected.get(
            "user_identifiers", case.expected.get("participants", [])[:1]
        ),
        "vip_people": [],
        "keywords": [],
        "digest_time": "06:00",
        "model": "scripted",
    }
    put = client.put("/settings", json=settings)
    assert put.status_code == 200, put.text
    got = client.get("/settings")
    assert got.status_code == 200, got.text


def score(case: DatasetCase, digest: dict) -> dict:
    """Compare the produced digest against the planted-fact ground truth.

    Matching is by content, not message id: ingest re-derives stable ids from
    content+sender+timestamp, so planted ids and post-ingest ids always differ
    by design. A needs-you item matches a planted fact when the item's summary
    (the surfaced text) carries all of the fact's tokens.
    """
    groups = digest["groups"]
    facts = [f for f in case.expected.get("planted_facts", []) if f["kind"] != "banter"]
    needs_items = [
        {"summary": item["summary"], "from": item["from"], "message_id": item["message_id"]}
        for group in groups
        for item in group["needs_you"]
    ]
    surfaced_norm_tokens = [
        token
        for group in groups
        for decision in group["decisions"] + group["deadlines"]
        for token in _tokens(decision["text"])
    ]

    question_facts = [f for f in facts if f["kind"] in ("question_for_user", "mention_user")]
    decision_facts = [
        f
        for f in facts
        if f["kind"] in ("decision", "correction", "deadline") and not f.get("superseded_by")
    ]

    matched_needs: list[tuple[dict, dict]] = []
    for fact in question_facts:
        fact_tokens = _tokens(fact["text"])
        for item in needs_items:
            if fact_tokens and set(fact_tokens) <= set(_tokens(item["summary"])):
                matched_needs.append((fact, item))
                break
    needs_recall = len(matched_needs) / max(len(question_facts), 1)

    decision_recall = (
        sum(1 for f in decision_facts if _contains_norm(surfaced_norm_tokens, f["text"]))
        / max(len(decision_facts), 1)
    )

    # attribution: matching needs-you items must name the planted fact sender.
    attribution_hits = sum(1 for fact, item in matched_needs if item["from"] == fact["sender"])
    attribution = attribution_hits / max(len(matched_needs), 1)

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
        "attribution_accuracy": attribution,
        "groups": len(groups),
        "messages_in_window": total_in_window,
        "surfaced_items": surfaced,
    }


def _contains_norm(haystack_tokens: list[str], needle: str) -> bool:
    needle_tokens = _tokens(needle)
    return bool(needle_tokens) and set(needle_tokens) <= set(haystack_tokens)


def run_dataset(case: DatasetCase, app) -> tuple[dict, float]:
    with TestClient(app) as client:
        ingest_result = ingest(client, case)
        push_settings(client, case)
        digest, latency = run_and_fetch(client, [ingest_result["conversation_id"]])
        return score(case, digest), latency


def run_case(case: DatasetCase, live: bool) -> tuple[dict, float]:
    with tempfile.TemporaryDirectory(prefix="sloth-eval-") as tmp:
        db_path = str(Path(tmp) / "sloth.db")
        Path(tmp, "drop").mkdir()
        os.environ["SLOTH_DB_PATH"] = db_path
        os.environ["SLOTH_DROP_FOLDER"] = str(Path(tmp) / "drop")
        get_settings.cache_clear()
        try:
            if live:
                app = create_app()
            else:
                app = create_app(
                    llm=ScriptedPipelineClient(case.expected.get("planted_facts", []))
                )
            return run_dataset(case, app)
        finally:
            get_settings.cache_clear()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake", action="store_true", help="deterministic simulated model (default)"
    )
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
            f"  decisions={scored['decision_recall']:.0%}"
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
        "`--fake` exercises the full pipeline with `ScriptedPipelineClient`:",
        "a deterministic stand-in that answers chunk/reduce prompts with",
        "perfect-content JSON built from each dataset's ground truth. It",
        "measures the workflow (chunking, validation, reduce, scoring,",
        "attribution), not a model; `--live` results with real Gemma land",
        "here as well once the demo machine has Ollama pulled up.",
        "",
        "| dataset | schema | needs-you recall | decision recall | attribution | groups | messages | surfaced | latency s |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['dataset']} | {'ok' if row['schema_valid'] else 'INVALID'}"
            f" | {row['needs_you_recall']:.0%} | {row['decision_recall']:.0%}"
            f" | {row['attribution_accuracy']:.0%} | {row['groups']} | {row['messages_in_window']}"
            f" | {row['surfaced_items']} | {row['latency_s']} |"
        )
    out = REPO_ROOT / "eval" / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    raise SystemExit(main())
