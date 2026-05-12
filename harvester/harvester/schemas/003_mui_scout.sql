-- Migration 003: MUI scout discovery notes on data_sources.

BEGIN;

ALTER TABLE harvest.data_sources
    ADD COLUMN IF NOT EXISTS discovery_notes JSONB,
    ADD COLUMN IF NOT EXISTS last_scouted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS data_sources_scouted_idx
    ON harvest.data_sources (last_scouted_at DESC NULLS LAST);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('003_mui_scout.sql', 'PLACEHOLDER_SHA', 'MUI scout discovery_notes column on data_sources')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
