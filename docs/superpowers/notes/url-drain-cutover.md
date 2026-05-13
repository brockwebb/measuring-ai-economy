# URL Drain Cutover

**Cutover date:** 2026-05-13

**Old path:** `~/.wintermute/scripts/drain_url_c4a.py` (now at `~/.wintermute/scripts/_sunset/2026-05-13-drain_url_c4a.py`).

**New path:** `harvester drain-url <URL>` in `measuring-ai-economy`.

**Behavior change:** Old script staged a markdown file with YAML frontmatter to `~/.wintermute/staging/YYYY-MM/`. New CLI writes to the harvest DB (`harvest.document_metadata` + `harvest.url_drain_documents`) and lets the Runner's standard inbox-emit logic produce the staging file. The frontmatter shape is slightly different but downstream consumers (extraction, ontology builders) read both old and new shapes via field-name normalization, so no consumer needs to change.

**Caller update:** `~/.wintermute/scripts/drain_with_notes.sh:49` — single line, swapped `python3 .../drain_url_c4a.py "$URL"` for `uv run harvester drain-url "$URL"`.

**No other callers.** Confirmed via `grep -rn drain_url_c4a /Users/brock/.wintermute/scripts/`.

## First-time setup on a fresh machine

The Crawl4aiFetcher path needs:

```bash
cd /Users/brock/Documents/GitHub/measuring-ai-economy/harvester
uv sync --extra html
uv run playwright install chromium
```

This installs crawl4ai and its headless-browser dependency. One-time per machine.

## 7-day stability check (Task 8)

Each day during the week of 2026-05-13 → 2026-05-20, sample one invocation:

```bash
psql wintermute -c "
SELECT date_trunc('day', started_at) AS day,
       count(*) AS runs,
       count(*) FILTER (WHERE status='completed') AS completed,
       count(*) FILTER (WHERE status='failed') AS failed
FROM harvest.run_log
WHERE source_id='url_drain' AND started_at > now() - interval '7 days'
GROUP BY day
ORDER BY day DESC
"
```

Green criteria (cumulative over the 7 days): at least 80% of url_drain runs status=completed, no error_signatures crossing failure_patterns thresholds.
