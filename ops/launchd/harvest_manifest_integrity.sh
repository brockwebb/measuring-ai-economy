#!/usr/bin/env bash
# Weekly manifest integrity check (Mondays 04:15 local).

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_manifest_integrity -- \
    "$UV_BIN" run python -m harvester.scripts.verify_manifest
