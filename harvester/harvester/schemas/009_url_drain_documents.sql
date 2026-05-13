-- Migration 009: url_drain_documents — densely-typed analytical table for
-- on-demand single-URL fetches via Crawl4aiFetcher.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.url_drain_documents (
    id                  BIGSERIAL PRIMARY KEY,
    source_url          TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    source_type         TEXT NOT NULL,    -- arxiv_paper | youtube_transcript | github_repo | pdf_document | web_article
    host                TEXT,             -- normalized hostname for filtering
    byte_size           INTEGER NOT NULL, -- markdown char count, useful for sanity
    fetched_at          TIMESTAMPTZ NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS url_drain_documents_source_type_idx
    ON harvest.url_drain_documents (source_type);
CREATE INDEX IF NOT EXISTS url_drain_documents_host_idx
    ON harvest.url_drain_documents (host);
CREATE INDEX IF NOT EXISTS url_drain_documents_fetched_at_idx
    ON harvest.url_drain_documents (fetched_at DESC);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('009_url_drain_documents.sql', 'PLACEHOLDER_SHA', 'url_drain_documents analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
