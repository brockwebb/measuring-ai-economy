# PubMed Migration — 3-Day Soak Window

**Started:** 2026-05-14T00:48:39Z

**Source:** `pubmed` via `mcp__claude_ai_PubMed__search_articles` + `mcp__claude_ai_PubMed__get_article_metadata` (Claude MCP transport via `claude -p` subprocess).

**Cron:** `com.wintermute.harvest-pubmed` fires daily at 22:00 local; wraps `harvester run pubmed --tier=tier_1` (10 terms; 10 MCP invocations/night, each making 2 tool calls — search then get_metadata).

**Cost model:** Each tier_1 term = 1 `claude -p` subprocess invocation (orchestrates search + get_metadata internally) + triage on every deposited paper. Max-results capped at 5 per term in PubMedFetcher; 5 × 10 = 50 papers/night ceiling. Daily cost ceiling soft-capped at $2.00 in sources.yaml.

## Deviation from initial plan

The plan assumed `mcp__claude_ai_PubMed__search_articles` returned full article records. It only returns PMIDs. Live smoke (Task 5) surfaced this and PubMedFetcher's `_build_mcp_prompt` was overridden to orchestrate a two-tool call in one subprocess (search → get_metadata). McpFetcher base class also gained `allowed_tools` and `subprocess_timeout` class attributes (backward-compatible, defaults preserve original behavior). `_MAX_RESULTS_CAP` was reduced from 10 to 5 to compensate for the 2x inference per term.

## Daily check (run each morning during the soak)

```bash
# 1. Did the nightly cron fire and complete?
tail -30 /Users/brock/.wintermute/logs/cron/harvest_pubmed.log

# 2. Run-log: every run for the last 24h
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed, started_at
FROM harvest.run_log
WHERE source_id='pubmed' AND started_at > now() - interval '24 hours'
ORDER BY id DESC
"

# 3. Per-term deposit rate
psql wintermute -c "
SELECT (request_params->>'mcp_tool') AS tool,
       count(*) AS runs,
       sum(items_fetched) AS fetched,
       sum(items_deposited) AS deposited
FROM harvest.run_log
WHERE source_id='pubmed' AND started_at > now() - interval '24 hours'
GROUP BY tool
"

# 4. Triage scoring
psql wintermute -c "
SELECT count(*) AS scored, avg(score)::numeric(4,2) AS avg_score
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='pubmed' AND created_at > now() - interval '24 hours'
)
"

# 5. Failure patterns
psql wintermute -c "
SELECT error_signature, occurrence_count, last_seen_at, mitigation_status
FROM harvest.failure_patterns
WHERE source_id='pubmed' AND last_seen_at > now() - interval '24 hours'
"
```

## Green criteria (all four for 3 consecutive days)

1. >=1 status='completed' run per day with sum(items_deposited) > 0.
2. >=30% of deposited docs have a triage score recorded.
3. No failure_patterns row crosses occurrence_count >= 5 with mitigation_status='unaddressed'.
4. Daily LLM call count stays bounded (approx 10 tier MCP calls + ~50 triage calls per night).

## Notes on edge cases

- **MCP response shape changes:** Claude's `--output-format json` envelope may differ over time. If `items_from_response` starts returning 0 items unexpectedly, capture the raw stdout (`claude -p ... > /tmp/dbg.json`) and check shape, then extend `_normalize_item` in PubMedFetcher.
- **PubMed MCP server availability:** The connector is hosted by Anthropic; outages surface as `status='failed'`. Auto-recovers on the next nightly run when the MCP comes back.
- **`--allowedTools` flag:** Required to bypass claude CLI's interactive permission prompt for MCP tool use. PubMedFetcher declares both `search_articles` and `get_article_metadata`.
