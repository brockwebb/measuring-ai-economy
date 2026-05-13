-- Migration 008: zenodo_records — densely-typed analytical table.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.zenodo_records (
    id                  BIGSERIAL PRIMARY KEY,
    zenodo_id           BIGINT NOT NULL UNIQUE,
    doi                 TEXT,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    resource_type       TEXT,
    resource_subtype    TEXT,
    keywords            TEXT[] NOT NULL DEFAULT '{}',
    publication_date    DATE,
    license             TEXT,
    zenodo_url          TEXT NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS zenodo_records_published_idx
    ON harvest.zenodo_records (publication_date DESC);
CREATE INDEX IF NOT EXISTS zenodo_records_resource_type_idx
    ON harvest.zenodo_records (resource_type, resource_subtype);
CREATE INDEX IF NOT EXISTS zenodo_records_keywords_gin_idx
    ON harvest.zenodo_records USING GIN (keywords);
CREATE INDEX IF NOT EXISTS zenodo_records_doi_idx
    ON harvest.zenodo_records (doi) WHERE doi IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('008_zenodo_records.sql', 'PLACEHOLDER_SHA', 'zenodo_records analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
