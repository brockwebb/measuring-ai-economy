-- Migration 010: pubmed_papers — densely-typed analytical table for the
-- PubMed source. Backed by the PubMed MCP server (mcp__claude_ai_PubMed_*).

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.pubmed_papers (
    id                  BIGSERIAL PRIMARY KEY,
    pmid                TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    abstract            TEXT,
    authors             JSONB NOT NULL DEFAULT '[]'::jsonb,
    journal             TEXT,
    publication_date    DATE,
    doi                 TEXT,
    pmcid               TEXT,
    mesh_terms          TEXT[] NOT NULL DEFAULT '{}',
    pmc_full_text_url   TEXT,
    pubmed_url          TEXT NOT NULL,
    raw_hash            TEXT NOT NULL,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pubmed_papers_published_idx
    ON harvest.pubmed_papers (publication_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS pubmed_papers_mesh_gin_idx
    ON harvest.pubmed_papers USING GIN (mesh_terms);
CREATE INDEX IF NOT EXISTS pubmed_papers_doi_idx
    ON harvest.pubmed_papers (doi) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS pubmed_papers_pmcid_idx
    ON harvest.pubmed_papers (pmcid) WHERE pmcid IS NOT NULL;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('010_pubmed_papers.sql', 'PLACEHOLDER_SHA', 'pubmed_papers analytical table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
