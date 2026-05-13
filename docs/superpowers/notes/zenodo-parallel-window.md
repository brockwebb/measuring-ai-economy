# Zenodo Migration — 3-Day Soak Window

**Started:** 2026-05-13T14:10:36Z

**Old endpoint:** `~/.wintermute/scripts/search_papers.py` zenodo block (stages markdown to `~/.wintermute/staging/`; not in harvest DB).

**New endpoint:** `harvester run zenodo --tier=tier_1` via `com.wintermute.harvest-zenodo` (lands in `harvest.document_metadata` + `harvest.zenodo_records`).

**Verification model:** Soak test, not coverage overlap. Legacy zenodo never wrote to the harvest DB, so `harvester compare-sources` is not applicable.

## Daily check (run each morning during the soak)

```bash
# 1. Did the nightly cron fire and complete?
tail -30 /Users/brock/.wintermute/logs/cron/harvest_zenodo.log

# 2. Run-log: every run for the last 24h
psql wintermute -c "
SELECT id, source_id, status, items_fetched, items_deposited, items_failed, started_at
FROM harvest.run_log
WHERE source_id='zenodo' AND started_at > now() - interval '24 hours'
ORDER BY id DESC
"

# 3. Per-term deposit rate (look for terms returning 0 systematically)
psql wintermute -c "
SELECT (request_params->>'q') AS term,
       count(*) AS runs,
       sum(items_fetched) AS fetched,
       sum(items_deposited) AS deposited
FROM harvest.run_log
WHERE source_id='zenodo' AND started_at > now() - interval '24 hours'
GROUP BY term
ORDER BY deposited DESC
"

# 4. Triage scoring is happening
psql wintermute -c "
SELECT count(*) AS scored, avg(score)::numeric(4,2) AS avg_score
FROM harvest.triage_results
WHERE doc_id IN (
    SELECT id FROM harvest.document_metadata
    WHERE source_id='zenodo' AND created_at > now() - interval '24 hours'
)
"

# 5. No new failure_patterns alerted
psql wintermute -c "
SELECT error_signature, occurrence_count, last_seen_at, mitigation_status
FROM harvest.failure_patterns
WHERE source_id='zenodo' AND last_seen_at > now() - interval '24 hours'
"
```

## Green criteria (all three for 3 consecutive days)

1. ≥1 `status='completed'` run in `harvest.run_log` per day, with sum(items_deposited) > 0.
2. ≥10% of deposited docs have a triage score recorded (LLM is reaching them).
3. No `harvest.failure_patterns` row crosses `occurrence_count >= 5` with `mitigation_status='unaddressed'`.

If a criterion fails on day N, restart the 3-day clock and root-cause the failure before continuing.

## Cutover

When all three days pass:
1. Update this note: "Cutover date: YYYY-MM-DD"
2. Proceed to Task 7 (sunset legacy zenodo path).
