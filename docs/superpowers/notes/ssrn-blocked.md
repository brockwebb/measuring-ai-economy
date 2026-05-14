# SSRN Migration — BLOCKED at Live Smoke

**Date:** 2026-05-14
**Plan:** `docs/superpowers/plans/2026-05-13-ssrn-migration.md`
**Branch state at block:** `d7b4c30` (4 commits: migration + fetcher + ETL + sources.yaml)

## Block

Task 5 (live smoke) hit Cloudflare WAF on the first real fetch:

```
GET https://papers.ssrn.com/sol3/results.cfm?...
→ 307 Temporary Redirect
→ /cdn-cgi/challenge-platform/h/g/orchestrate/managed/v1
   "Performing security verification — This website uses a security service to
    protect against malicious bots."
   Ray ID: 9fb65e597a6943dc
```

crawl4ai's headless Chromium gets intercepted at the WAF before the search page renders. The fetcher returns 0 items, no exceptions thrown — the ETL and regex extractors never run.

This is the BLOCKED scenario the plan anticipated. Per plan Task 5 Step 4:
> "This is the structural blocker the plan anticipates. Document and STOP — do NOT try to engineer around it (custom headers, session cookies, anti-bot bypass tricks). That's beyond Task 5's scope."

Tasks 6 (launchd + soak note) and Task 7 (cutover of `search_papers.py` SSRN block) are **skipped** — there's nothing to soak or cut over to.

## What ships on this branch (if merged)

| Artifact | State |
|---|---|
| Migration 011 (`harvest.ssrn_records`) | Applied. Empty table; harmless to keep. |
| `SsrnFetcher` (Crawl4aiFetcher two-stage flow) | Tested, works in mocks. Real fetches blocked. |
| `SsrnETL` (markdown → structured rows) | Tested against 3 synthetic fixtures. Never exercised on real data. |
| 17 new tests | All passing under mock. |
| `sources.yaml` `ssrn:` entry | Registers the source. **If merged as-is, the source is reachable by `harvester run ssrn` and the nightly cron mechanism — but every fetch will produce 0 items.** |

## Options for the operator

1. **Merge anyway**, with a follow-up "disable SSRN in sources.yaml" cleanup. The infrastructure (schema + code) is preserved for a future bot-bypass spike. Downside: someone might later schedule it and produce noise in run_log.

2. **Merge with sources.yaml entry removed.** Schema, fetcher, ETL, and tests merge; the source isn't routable from the CLI until re-registered. Cleanest path for the "build now, ship later" model.

3. **Discard the branch.** All 4 commits go away. If/when SSRN becomes reachable, the migration would have to be re-planned from scratch.

4. **Keep the branch open** (Option 3 of finishing-a-development-branch). Re-evaluate after a separate "SSRN bot-bypass spike" task determines whether SSRN is reachable at all.

## Possible bot-bypass approaches (out of scope for this plan)

- **SSRN's official API** — if `https://api.ssrn.com/` exists and supports public search, it would bypass the Cloudflare WAF entirely. Worth a quick check.
- **Institutional proxy** — Brock has academic affiliation; an authenticated session may bypass the bot challenge.
- **Captcha-solving service** — costs money, ethically gray, not recommended.
- **Different fetcher pattern** — e.g., use `httpx` with a real browser User-Agent + the Cloudflare-clearance token cookies (`cf_clearance`). Complex and brittle.

If a bypass is identified, the existing `SsrnFetcher` is straightforward to retrofit — only `iter_payloads` and `crawl_config` would change; the ETL and schema are still correct.

## Roadmap status

Per `docs/superpowers/notes/phase3-roadmap.md`, SSRN was the last 3.3 piece. With SSRN blocked, Phase 3.3 is **partially complete**: zenodo + url_drain shipped and live; ssrn shipped infrastructure-only. Phase 3 overall is done modulo this caveat.
