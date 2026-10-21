#!/usr/bin/env bash
# SlothDigest demo (agent.md B3.2): 500-message overnight chat -> ~10 lines.
#
# Fully offline and deterministic: the chat is synthetic, the model step is
# the scripted stand-in (ScriptedPipelineClient), and nothing ever leaves the
# machine. For the recorded 90-second flow: generate a fresh chat, run the
# pipeline, show the digest on the frontend while Wi-Fi is off on camera.
#
# Usage: bash scripts/demo.sh [--seed N] [--out DIR]
set -euo pipefail
cd "$(dirname "$0")/.."

SEED=7
DEMO_DIR="data/demo"
EXTRA_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --seed) SEED="$2"; shift 2 ;;
    --out) DEMO_DIR="$2"; shift 2 ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

echo "[1/3] generating a fresh 500-message synthetic chat -> $DEMO_DIR"
python scripts/gen_synthetic_chats.py --out "$DEMO_DIR" \
  --messages 500 --seed "$SEED" --style english \
  --conversation-name "saturday-plan-making"

echo "[2/3] running the real pipeline over it (offline, scripted model)"
uv run --project backend python scripts/demo_digest.py \
  --chat "$DEMO_DIR/chat.txt" --expected "$DEMO_DIR/expected.json" \
  --out "$DEMO_DIR/digest.md" "${EXTRA_ARGS[@]+${EXTRA_ARGS[@]}}"

echo "[3/3] digest written to $DEMO_DIR/digest.md"
echo " UI flow:  make backend-dev &  && make frontend-dev, then open"
echo " http://localhost:5173/#/sources and upload $DEMO_DIR/chat.txt"
