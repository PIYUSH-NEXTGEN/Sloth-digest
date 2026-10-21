"""A6.2 Tinker training job wrapper.

Builds the training payload from the A6.1 pairs file and (when the tinker
SDK is importable AND TINKER_API_KEY is set) submits a supervised-fine-tune
job over the base Gemma. `--dry-run` fully validates the payload without the
SDK, key, or any network, which is what CI exercises.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def _gold_completion(raw: str) -> dict:
    return json.loads(raw)


def load_pairs(path: Path, limit: int | None = None) -> list[dict]:
    pairs = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        pair = json.loads(line)
        pairs.append({"prompt": pair["prompt"], "completion": _gold_completion(pair["completion"])})
    if limit is not None:
        pairs = pairs[:limit]
    if not pairs:
        raise SystemExit(f"no pairs found in {path}")
    return pairs


def validate_payload(pairs: list[dict]) -> None:
    for pair in pairs:
        completion = pair["completion"]
        for key in ("tldr", "topics", "decisions", "deadlines", "per_person"):
            assert key in completion, f"completion missing key: {key}"
        assert completion["tldr"], "completion tldr must be non-empty"


def payload_path_for(run_dir: Path) -> Path:
    return run_dir / "tinker_payload.jsonl"


def run(
    pairs_path: Path,
    out_dir: Path,
    *,
    base_model: str = "gemma3-4b",
    limit: int | None = None,
    dry_run: bool = False,
) -> Path:
    pairs = load_pairs(pairs_path, limit=limit)
    validate_payload(pairs)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = payload_path_for(out_dir)
    with payload.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    if dry_run:
        return payload
    import tinker  # optional SDK, never installed in offline environments

    api_key = os.environ.get("TINKER_API_KEY")
    if not api_key:
        raise SystemExit("TINKER_API_KEY is required for non-dry-run training")
    job = tinker.submit_finetune_job(
        base_model=base_model,
        training_file=str(payload),
        api_key=api_key,
    )
    meta = {
        "base_model": base_model,
        "pairs": len(pairs),
        "job_id": getattr(job, "id", None),
        "submitted": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (out_dir / "job.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="A6.2 tinker SFT wrapper")
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base", default="gemma3-4b")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payload_path = run(
        args.pairs, args.out, base_model=args.base, limit=args.limit, dry_run=args.dry_run
    )
    print(f"payload ready: {payload_path}")


if __name__ == "__main__":
    main()
