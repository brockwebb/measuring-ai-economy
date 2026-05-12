#!/usr/bin/env bash
# Nightly count validation at 03:30 local.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_count_validation -- \
    "$UV_BIN" run python -m harvester.scripts.validate_count
