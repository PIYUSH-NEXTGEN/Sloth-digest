"""FINETUNING DATASET BUILDER (A6.1) - synthetic chats ONLY.

Builds chat-to-digest training pairs from Agent B's generated synthetic
datasets (eval/datasets/<name>: chat.txt + expected.json).

Hard safety rule (agent.md 6): this script refuses any dataset whose
directory is not the repo's `eval/datasets/` tree. Real chat exports must
NEVER feed finetuning.

Pair shape per dataset:
  prompt:     the reduce-task input JSON exactly as the reduce prompt
              consumes it (conversation + window + chunk_summaries)
  completion: golden reduce-output JSON built ONLY from planted facts
              (no invented content), keyed as the reduce output schema
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ingest.service import ingest_export  # noqa: E402
from app.pipeline.reduce import build_reduce_prompt  # noqa: E402
from app.store.db import Store  # noqa: E402

EVAL_ROOT = REPO_ROOT / "eval" / "datasets"

DECISION_KINDS = {"decision", "correction"}


def _assert_synthetic(path: Path) -> None:
    resolved = path.resolve()
    root = EVAL_ROOT.resolve()
    if root != resolved and root not in resolved.parents:
        raise SystemExit(f"refusing non-synthetic input {resolved}: only {root}/* is allowed")


def _pair(dataset_dir: Path) -> dict:
    chat = (dataset_dir / "chat.txt").read_text(encoding="utf-8")
    expected = json.loads((dataset_dir / "expected.json").read_text(encoding="utf-8"))

    store = Store(":memory:")
    try:
        _conversation_id, imported, _dupes = ingest_export(
            store,
            f"{dataset_dir.name}.txt",
            chat,
            expected.get("conversation_name"),
        )
        messages = store.all_messages(2000)
    finally:
        store.close()
    {m.id.rsplit(":", 1)[-1]: m.id for m in messages}
    _tokens = lambda t: {x for x in re.split(r"\W+", t.lower(), flags=re.UNICODE) if x}  # noqa: E731
    source_tokens = [(m, _tokens(m.text)) for m in messages]

    def _key(fact: dict) -> str | None:
        fact_tokens = _tokens(fact.get("text", ""))
        if not fact_tokens:
            return None
        for message, m_tokens in source_tokens:
            if fact_tokens <= m_tokens:
                return message.id
        return None

    facts = expected.get("planted_facts", [])
    superseded = {f.get("message_id") for f in facts if f.get("superseded_by")}

    topics: list[str] = []
    decisions: list[dict] = []
    deadlines: list[dict] = []
    questions: list[dict] = []
    points_by_sender: dict[str, list[str]] = {}
    for fact in facts:
        kind = fact.get("kind")
        text = fact.get("text", "")
        sender = fact.get("sender", "")
        mid = _key(fact)
        if kind == "banter":
            continue
        if mid is None:
            raise SystemExit(f"{dataset_dir.name}: planted fact id not in store: {fact}")
        topics.append(text[:60])
        if kind in DECISION_KINDS:
            if fact.get("message_id") in superseded:
                continue
            decisions.append({"text": text, "message_ids": [mid]})
        elif kind == "deadline":
            deadlines.append({"text": text, "when": None, "message_ids": [mid]})
        elif kind in {"question_for_user", "mention_user"}:
            questions.append({"message_id": mid, "question": text[:200]})
        if sender:
            points_by_sender.setdefault(sender, []).append(text[:120])

    per_person = [{"name": s, "points": p} for s, p in sorted(points_by_sender.items())]
    tldr_bits = []
    if decisions:
        tldr_bits.append("Decided: " + " / ".join(d["text"] for d in decisions))
    if deadlines:
        tldr_bits.append("Deadlines: " + " / ".join(d["text"] for d in deadlines))
    if questions:
        tldr_bits.append(f"{len(questions)} thing(s) waiting on the user")
    completion = {
        "tldr": " | ".join(tldr_bits)[:390] or "Chat was mostly banter.",
        "topics": list(dict.fromkeys(topics))[:6],
        "decisions": decisions,
        "deadlines": deadlines,
        "per_person": per_person,
    }

    start = expected.get("start") or (messages[0].timestamp if messages else datetime.now())
    end = expected.get("end") or (messages[-1].timestamp if messages else start)
    sys.path.insert(0, str(BACKEND))
    from app.models import Window  # noqa: E402

    window = Window(
        start=start if isinstance(start, datetime) else datetime.fromisoformat(start),
        end=end if isinstance(end, datetime) else datetime.fromisoformat(end),
    )
    from app.pipeline.extract import ChunkExtract  # noqa: E402

    extract_view = ChunkExtract.model_validate(
        {
            "topics": completion["topics"],
            "decisions": completion["decisions"],
            "questions_for_user": questions,
            "deadlines": completion["deadlines"],
        }
    )
    prompt = build_reduce_prompt(
        conversation_name=expected.get("conversation_name") or dataset_dir.name,
        window=window,
        extracts=[extract_view],
    )
    return {
        "dataset": dataset_dir.name,
        "message_count": imported,
        "prompt": prompt,
        "completion": json.dumps(completion, ensure_ascii=False, indent=2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A6.1 finetune dataset builder")
    parser.add_argument("--datasets", type=Path, default=EVAL_ROOT)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "finetune" / "data" / "pairs.jsonl")
    args = parser.parse_args()
    _assert_synthetic(args.datasets)
    pairs = []
    for dataset_dir in sorted(p for p in args.datasets.iterdir() if p.is_dir()):
        if not (dataset_dir / "chat.txt").exists():
            continue
        pair = _pair(dataset_dir)
        pairs.append(pair)
        print(f"{dataset_dir.name}: {pair['message_count']} messages -> 1 pair")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"wrote {len(pairs)} pairs -> {args.out}")


if __name__ == "__main__":
    main()
