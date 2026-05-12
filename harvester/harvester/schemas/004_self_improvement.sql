-- Migration 004: Self-improvement tables.
-- Phase 2 populates triage_results; Phase 3 populates the rest.

BEGIN;

-- Expansion candidates: papers/authors/terms proposed by adaptive loops (Phase 3)
CREATE TABLE IF NOT EXISTS harvest.expansion_candidates (
    id              BIGSERIAL PRIMARY KEY,
    kind            TEXT NOT NULL CHECK (kind IN ('paper', 'author', 'term')),
    payload         JSONB NOT NULL,
    parent_doc_id   BIGINT REFERENCES harvest.document_metadata(doc_id),
    depth           INTEGER NOT NULL DEFAULT 1 CHECK (depth BETWEEN 1 AND 3),
    score           REAL,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'approved', 'rejected', 'ingested')),
    proposed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT,
    UNIQUE (kind, payload)
);
CREATE INDEX IF NOT EXISTS expansion_candidates_kind_status_idx
    ON harvest.expansion_candidates (kind, status, score DESC);

-- Cross-source co-occurrence ledger (Phase 3)
CREATE TABLE IF NOT EXISTS harvest.co_sources (
    id              BIGSERIAL PRIMARY KEY,
    canonical_key   TEXT NOT NULL,
    canonical_kind  TEXT NOT NULL CHECK (canonical_kind IN ('doi', 'content_hash', 'url')),
    source_id       TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canonical_key, source_id, source_url)
);
CREATE INDEX IF NOT EXISTS co_sources_key_idx
    ON harvest.co_sources (canonical_key, canonical_kind);

CREATE OR REPLACE VIEW harvest.co_occurrence AS
SELECT canonical_key,
       canonical_kind,
       array_agg(DISTINCT source_id ORDER BY source_id) AS sources,
       count(DISTINCT source_id) AS source_count,
       count(*) AS total_encounters,
       min(first_seen_at) AS first_seen,
       max(first_seen_at) AS latest_seen
FROM harvest.co_sources
GROUP BY canonical_key, canonical_kind;

-- Failure pattern clustering (Phase 3)
CREATE TABLE IF NOT EXISTS harvest.failure_patterns (
    id              BIGSERIAL PRIMARY KEY,
    source_id       TEXT NOT NULL,
    error_signature TEXT NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    sample_error    TEXT,
    mitigation_status TEXT DEFAULT 'unaddressed'
                    CHECK (mitigation_status IN ('unaddressed', 'in_progress', 'mitigated', 'wontfix')),
    UNIQUE (source_id, error_signature)
);
CREATE INDEX IF NOT EXISTS failure_patterns_source_idx
    ON harvest.failure_patterns (source_id, last_seen_at DESC);

-- run_log gains a post-extraction signal (saturation monitor reads this)
ALTER TABLE harvest.run_log
    ADD COLUMN IF NOT EXISTS new_graph_nodes INTEGER;

-- Triage results (Phase 2 populates this on every arxiv document)
CREATE TABLE IF NOT EXISTS harvest.triage_results (
    doc_id          BIGINT PRIMARY KEY REFERENCES harvest.document_metadata(doc_id),
    score           REAL NOT NULL,
    axes            JSONB NOT NULL,
    reason          TEXT,
    rubric_version  TEXT NOT NULL,
    model_id        TEXT,
    prompt_hash     TEXT,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed        BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS triage_results_score_idx
    ON harvest.triage_results (score DESC, scored_at DESC);

-- Saturation view (read-only, derived; Phase 3 alerting reads this)
CREATE OR REPLACE VIEW harvest.saturation AS
SELECT source_id,
       date_trunc('day', started_at) AS day,
       sum(items_fetched) AS total_fetched,
       sum(items_deposited) AS total_deposited,
       CASE WHEN sum(items_fetched) > 0
            THEN sum(items_deposited)::float / sum(items_fetched)
            ELSE 0
       END AS deposit_ratio,
       sum(new_graph_nodes) AS new_nodes
FROM harvest.run_log
WHERE status = 'completed'
GROUP BY source_id, date_trunc('day', started_at)
ORDER BY day DESC;

INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('004_self_improvement.sql', 'PLACEHOLDER_SHA', 'Self-improvement tables (Phase 2-3 substrate)')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
