-- Migration 011: ssrn_records — densely-typed analytical table for the SSRN
-- source. Two-stage Crawl4ai flow (search → paper page) lands one row per
-- paper page.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.ssrn_records (
    id                  BIGSERIAL PRIMARY KEY,
    ssrn_id             BIGINT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    doi                 TEXT,
    publication_date    DATE,
    jel_codes           TEXT[] NOT NULL DEFAULT '{}',
    institution         TEXT,
    ssrn_url            TEXT NOT NULL,
    byte_size           INTEGER NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ssrn_records_published_idx
    ON harvest.ssrn_records (publication_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ssrn_records_jel_gin_idx
    ON harvest.ssrn_records USING GIN (jel_codes);
CREATE INDEX IF NOT EXISTS ssrn_records_doi_idx
    ON harvest.ssrn_records (doi) WHERE doi IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('011_ssrn_records.sql', 'PLACEHOLDER_SHA', 'ssrn_records analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
