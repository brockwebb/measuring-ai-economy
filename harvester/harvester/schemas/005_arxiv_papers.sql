-- Migration 005: arxiv_papers — densely-typed analytical table.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.arxiv_papers (
    id                  BIGSERIAL PRIMARY KEY,
    arxiv_id            TEXT NOT NULL UNIQUE,
    arxiv_id_short      TEXT NOT NULL,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_category    TEXT,
    categories          TEXT[] NOT NULL DEFAULT '{}',
    published_date      DATE NOT NULL,
    updated_date        DATE,
    doi                 TEXT,
    journal_ref         TEXT,
    arxiv_url           TEXT NOT NULL,
    pdf_url             TEXT,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS arxiv_papers_published_idx
    ON harvest.arxiv_papers (published_date DESC);
CREATE INDEX IF NOT EXISTS arxiv_papers_primary_cat_idx
    ON harvest.arxiv_papers (primary_category);
CREATE INDEX IF NOT EXISTS arxiv_papers_categories_gin_idx
    ON harvest.arxiv_papers USING GIN (categories);
CREATE INDEX IF NOT EXISTS arxiv_papers_doi_idx
    ON harvest.arxiv_papers (doi) WHERE doi IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('005_arxiv_papers.sql', 'PLACEHOLDER_SHA', 'arxiv_papers analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
