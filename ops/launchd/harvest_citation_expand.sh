#!/usr/bin/env bash
# Weekly citation chain processing (Sundays 02:30 local).

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_citation_expand -- \
    "$UV_BIN" run harvester expand-citations --max-batch 100 --threshold 0.4
