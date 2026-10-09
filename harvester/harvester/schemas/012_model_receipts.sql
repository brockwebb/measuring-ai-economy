-- Migration 012: served-model receipts (seldon AD-035 R6, MODEL-001 Part C).
-- Every triage call now records {requested, served, side_models, ok}: the id the
-- harvester asked for (from the seldon lock) and the id the CLI's modelUsage
-- says answered. It sits beside the call's other facts: triage_results for the
-- runner's triage hook, expansion_candidates for the citation-chain triage. A
-- served id that differs from the requested one stops the unit
-- (model_substituted); a citation-chain candidate keeps status 'proposed' and
-- records the refused receipt here. Rows written before this migration hold
-- NULL: their model_id column is what they were made with (history, AD-035 R7).

BEGIN;

ALTER TABLE harvest.triage_results
    ADD COLUMN IF NOT EXISTS model_receipt JSONB NULL;

ALTER TABLE harvest.expansion_candidates
    ADD COLUMN IF NOT EXISTS model_receipt JSONB NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('012_model_receipts.sql', 'PLACEHOLDER_SHA',
        'model_receipt JSONB on triage_results and expansion_candidates (seldon AD-035 R6)')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
