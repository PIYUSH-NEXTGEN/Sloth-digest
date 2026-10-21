"""A6.2 finetune wrappers: dry-run payload validation + offline compare.

train_tinker.py real (non-dry-run) mode never runs here: it needs the tinker
SDK and TINKER_API_KEY. compare.py is offline by design.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for entry in (REPO_ROOT / "finetune", REPO_ROOT / "backend"):
    sys.path.insert(0, str(entry))

import compare  # noqa: E402
import train_tinker  # noqa: E402

PAIRS = REPO_ROOT / "finetune" / "data" / "pairs.jsonl"
EXPECTED = REPO_ROOT / "eval" / "datasets" / "base" / "expected.json"

BASE_PAIR = json.loads(PAIRS.read_text(encoding="utf-8").strip().splitlines()[0])
GOLD = json.loads(BASE_PAIR["completion"])


@pytest.mark.skipif(not PAIRS.exists(), reason="run finetune/make_dataset.py first")
def test_dry_run_payload_validates_and_matches_pairs(tmp_path: Path) -> None:
    out = train_tinker.run(PAIRS, tmp_path, dry_run=True)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        pair = json.loads(line)
        assert pair["prompt"].startswith("# Reduce")
        assert set(pair["completion"]) >= {"tldr", "decisions", "deadlines"}


def test_dry_run_rejects_empty_pairs(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="no pairs"):
        train_tinker.run(empty, tmp_path, dry_run=True)


def test_fact_recall_full_and_miss() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert compare.fact_recall(GOLD, expected) > 0.5
    assert compare.fact_recall({"tldr": "", "topics": []}, expected) == 0.0


def test_attribution_bad_catches_invented_ids(tmp_path: Path) -> None:
    pool = {"whatsapp:conv:abc"}
    bad = compare.attribution_bad({"decisions": [{"message_ids": ["fake-id"]}]}, pool)
    assert bad == ["fake-id"]
    assert (
        compare.attribution_bad({"decisions": [{"message_ids": ["whatsapp:conv:abc"]}]}, pool) == []
    )


def test_score_digest_reports_recall(tmp_path: Path) -> None:
    digest_path = tmp_path / "g.json"
    digest_path.write_text(json.dumps(GOLD), encoding="utf-8")
    ids_path = tmp_path / "ids.json"
    id_pool = []
    for bucket in ("decisions", "deadlines"):
        id_pool += [mid for item in GOLD.get(bucket, []) for mid in item["message_ids"]]
    ids_path.write_text(json.dumps(sorted(set(id_pool))), encoding="utf-8")
    score = compare.score_digest(digest_path, EXPECTED, set(id_pool))
    assert score["json_valid"] is True
    assert score["fact_recall"] > 0.5
    assert score["bad_attribution_ids"] == []
