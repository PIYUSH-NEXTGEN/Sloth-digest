"""A6.2 comparison harness: baseline vs tuned digests against planted facts.

Offline by design: reads two candidate digest JSON files plus one expected.json
from Agent B's eval datasets and reports JSON validity, fact recall, and
attribution sanity (no invented message ids). Latency values are passed in by
the caller (a real harness); nothing is measured here.
"""

import argparse
import json
import re
from collections.abc import Iterator
from pathlib import Path


def token_set(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower(), flags=re.UNICODE) if t}


def _text_blob(digest: dict) -> set[str]:
    blobs: list[str] = [digest.get("tldr", "")]
    blobs += digest.get("topics", [])
    for bucket in ("decisions", "deadlines"):
        blobs += [str(item.get("text", "")) for item in digest.get(bucket, [])]
    for person in digest.get("per_person", []):
        blobs += person.get("points", [])
    for llm_question in digest.get("llm_questions", []):
        blobs.append(llm_question.get("summary", ""))
    blob_text: set[str] = set()
    for blob in blobs:
        blob_text |= token_set(blob)
    return blob_text


def fact_recall(digest: dict, expected: dict) -> float:
    """Planted-fact texts recoverable from tldr/topics/decisions/deadlines."""
    available = _text_blob(digest)
    facts = [f for f in expected.get("planted_facts", []) if f.get("kind") != "banter"]
    hits = sum(1 for f in facts if token_set(f["text"]) <= available)
    return hits / max(1, len(facts))


def attribution_bad(digest: dict, id_pool: set[str]) -> list[str]:
    """Decision/deadline message ids that do not exist in the provided pool."""
    bad: list[str] = []
    for bucket in ("decisions", "deadlines"):
        for item in digest.get(bucket, []):
            for message_id in item.get("message_ids", []):
                if message_id not in id_pool:
                    bad.append(message_id)
    return sorted(set(bad))


def score_digest(digest_path: Path, expected_path: Path, id_pool: set[str]) -> dict:
    digest = json.loads(digest_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    return {
        "json_valid": True,
        "fact_recall": round(fact_recall(digest, expected), 3),
        "bad_attribution_ids": attribution_bad(digest, id_pool),
    }


def _candidate_paths(args: argparse.Namespace) -> Iterator[tuple[str, Path]]:
    yield "baseline", args.baseline
    yield "tuned", args.tuned


def main() -> None:
    parser = argparse.ArgumentParser(description="A6.2 baseline vs tuned digest scores")
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--tuned", type=Path, required=True)
    parser.add_argument("--ids", type=Path, required=True, help="JSON list of source message ids")
    args = parser.parse_args()
    id_pool = set(json.loads(args.ids.read_text(encoding="utf-8")))
    scores = {
        variant: score_digest(path, args.expected, id_pool)
        for variant, path in _candidate_paths(args)
    }
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
