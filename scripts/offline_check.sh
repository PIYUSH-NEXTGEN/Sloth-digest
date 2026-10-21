#!/usr/bin/env bash
# Offline / privacy proof (A3.3, agent.md 9.5): runs the full pipeline
# (ingest -> chunk -> extract -> reduce -> score -> validate -> persist)
# with every non-localhost socket patched to raise. Fails on ANY network
# attempt; localhost:11434 (local Ollama) is still allowed.
set -euo pipefail
cd "$(dirname "$0")/../backend"

echo "[offline_check] running full pipeline with non-localhost sockets refused..."
uv run pytest tests/offline -q
echo "[offline_check] OK: pipeline completed offline, no network attempted."
