#!/usr/bin/env bash
# Daily arxiv harvest at 23:00 local. Parallel to legacy search_papers.sh
# until Phase 2 cutover.

. "$(dirname "$0")/_lib.sh"

HARVESTER_DIR="/Users/brock/Documents/GitHub/measuring-ai-economy/harvester"
UV_BIN="/Users/brock/.local/bin/uv"

cd "$HARVESTER_DIR" || exit 1

run_job harvest_arxiv -- \
    "$UV_BIN" run harvester run arxiv --tier=tier_1
