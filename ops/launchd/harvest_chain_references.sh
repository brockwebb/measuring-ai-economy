#!/usr/bin/env bash
# Weekly citation-chain reference expansion (Sundays 02:45 local).

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_chain_references -- \
    "$UV_BIN" run harvester chain-references --max-parents 50 --ref-limit 100
