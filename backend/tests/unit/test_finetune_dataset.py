"""A6.1 finetune dataset builder: synthetic-only guard + pair shape tests.

The builder must never accept dataset paths outside eval/datasets/ (agent.md
6: real chats may not feed finetuning) and must produce reduce-schema-valid
completions with message ids that resolve in the ingested store.
"""

import json
import sys
from pathlib import Path

import pytest

# tests/unit/case.py -> parents[3] is the repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "finetune"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

import make_dataset  # noqa: E402

from app.ingest.service import ingest_export  # noqa: E402
from app.pipeline.reduce import parse_reduce_json  # noqa: E402
from app.store.db import Store  # noqa: E402

EVAL_BASE = REPO_ROOT / "eval" / "datasets" / "base"


def test_guard_rejects_non_synthetic_paths(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="refusing non-synthetic"):
        make_dataset._assert_synthetic(tmp_path)
    make_dataset._assert_synthetic(make_dataset.EVAL_ROOT)
    make_dataset._assert_synthetic(EVAL_BASE)


@pytest.mark.skipif(not EVAL_BASE.exists(), reason="Agent B dataset missing")
def test_base_pair_is_reduce_schema_valid() -> None:
    pair = make_dataset._pair(EVAL_BASE)
    assert pair["dataset"] == "base"
    completion = json.loads(pair["completion"])
    parsed = parse_reduce_json(json.dumps(completion))
    assert parsed["tldr"]
    for decision in parsed["decisions"]:
        assert set(decision["message_ids"])
    expected = json.loads((EVAL_BASE / "expected.json").read_text(encoding="utf-8"))
    # expected counts raw export lines; the builder imports post-dedupe
    assert 0 < pair["message_count"] <= expected["message_count"]


@pytest.mark.skipif(not EVAL_BASE.exists(), reason="Agent B dataset missing")
def test_planted_ids_resolve_in_store() -> None:
    chat = (EVAL_BASE / "chat.txt").read_text(encoding="utf-8")
    expected = json.loads((EVAL_BASE / "expected.json").read_text(encoding="utf-8"))
    store = Store(":memory:")
    try:
        _cid, _imported, _dupes = ingest_export(
            store, "base.txt", chat, expected.get("conversation_name")
        )
        messages = store.all_messages(2000)
        store_ids = {m.id for m in messages}
    finally:
        store.close()
    pair = make_dataset._pair(EVAL_BASE)
    completion = json.loads(pair["completion"])
    evidence = set(store_ids)
    for decision in completion["decisions"]:
        for message_id in decision["message_ids"]:
            assert message_id in evidence
    for deadline in completion["deadlines"]:
        for message_id in deadline["message_ids"]:
            assert message_id in evidence
