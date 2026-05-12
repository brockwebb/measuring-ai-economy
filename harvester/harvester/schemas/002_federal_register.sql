-- Migration 002: Federal Register documents — densely-typed analytical table.

BEGIN;

CREATE TABLE IF NOT EXISTS harvest.federal_register_documents (
    id                          BIGSERIAL PRIMARY KEY,
    document_number             TEXT NOT NULL UNIQUE,
    title                       TEXT NOT NULL,
    abstract                    TEXT,
    document_type               TEXT NOT NULL,
    presidential_document_type  TEXT,
    executive_order_number      INTEGER,
    publication_date            DATE NOT NULL,
    effective_date              DATE,
    signing_date                DATE,
    agencies                    TEXT[] NOT NULL DEFAULT '{}',
    agency_ids                  INTEGER[] NOT NULL DEFAULT '{}',
    cfr_references              JSONB,
    citation                    TEXT,
    page_length                 INTEGER,
    html_url                    TEXT NOT NULL,
    pdf_url                     TEXT,
    full_text_xml_url           TEXT,
    body_html_url               TEXT,
    body_text                   TEXT,
    docket_ids                  TEXT[],
    regulations_dot_gov_url     TEXT,
    raw_hash                    TEXT NOT NULL,
    created_by_run_id           BIGINT REFERENCES harvest.run_log(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fr_docs_publication_date_idx
    ON harvest.federal_register_documents (publication_date DESC);
CREATE INDEX IF NOT EXISTS fr_docs_doc_type_idx
    ON harvest.federal_register_documents (document_type);
CREATE INDEX IF NOT EXISTS fr_docs_agencies_gin_idx
    ON harvest.federal_register_documents USING GIN (agencies);

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('002_federal_register.sql', 'PLACEHOLDER_SHA', 'Federal Register documents table')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
