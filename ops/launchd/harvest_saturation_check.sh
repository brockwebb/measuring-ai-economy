#!/usr/bin/env bash
# Nightly saturation check at 04:00 local.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_saturation_check -- \
    "$UV_BIN" run harvester check-saturation
