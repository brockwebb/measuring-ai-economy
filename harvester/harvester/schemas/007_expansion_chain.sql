-- Migration 007: Extend harvest.expansion_candidates for the seed-feedback loop.
-- Adds expanded_at to mark which approved candidates have had their reference
-- lists fetched, and parent_candidate_id to link depth-2 candidates back to
-- the approved depth-1 parent that produced them.

BEGIN;

ALTER TABLE harvest.expansion_candidates
    ADD COLUMN IF NOT EXISTS expanded_at TIMESTAMPTZ NULL;

ALTER TABLE harvest.expansion_candidates
    ADD COLUMN IF NOT EXISTS parent_candidate_id BIGINT NULL
        REFERENCES harvest.expansion_candidates(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS expansion_candidates_unexpanded_idx
    ON harvest.expansion_candidates (score DESC NULLS LAST, proposed_at ASC)
    WHERE status = 'approved' AND expanded_at IS NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('007_expansion_chain.sql', 'PLACEHOLDER_SHA',
        'Add expanded_at + parent_candidate_id to expansion_candidates')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
