#!/usr/bin/env bash
# Daily Federal Register harvest at 22:00 local.
# Invokes the harvester CLI in measuring-ai-economy/harvester.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_federal_register -- \
    "$UV_BIN" run harvester run federal_register --tier=tier_1
