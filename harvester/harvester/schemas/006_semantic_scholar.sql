-- Migration 006: Semantic Scholar papers — densely-typed analytical table.
-- Mirrors arxiv_papers in shape. Used by both standalone SemanticScholarFetcher
-- runs and by CitationChain verification.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.semantic_scholar_papers (
    id                  BIGSERIAL PRIMARY KEY,
    ss_paper_id         TEXT NOT NULL UNIQUE,          -- Semantic Scholar Paper ID
    doi                 TEXT,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    venue               TEXT,
    year                INTEGER,
    published_date      DATE,
    s2_url              TEXT NOT NULL,                  -- canonical Semantic Scholar page URL
    open_access_pdf_url TEXT,
    citation_count      INTEGER,
    reference_count     INTEGER,
    influential_count   INTEGER,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ss_papers_published_idx
    ON harvest.semantic_scholar_papers (published_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ss_papers_doi_idx
    ON harvest.semantic_scholar_papers (doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS ss_papers_citation_count_idx
    ON harvest.semantic_scholar_papers (citation_count DESC NULLS LAST);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('006_semantic_scholar.sql', 'PLACEHOLDER_SHA', 'Semantic Scholar papers table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
