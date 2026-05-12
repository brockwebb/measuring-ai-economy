-- Migration 001: Initialize harvest schema with operational + registry + metadata tables.
-- Idempotent; safe to re-run.

BEGIN;

CREATE SCHEMA IF NOT EXISTS harvest;

-- ---------------------------------------------------------------------------
-- schema_migrations: tracks which migrations have been applied
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.schema_migrations (
    id              SERIAL PRIMARY KEY,
    filename        TEXT NOT NULL UNIQUE,
    sha256          TEXT NOT NULL,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by      TEXT NOT NULL DEFAULT current_user,
    description     TEXT
);

-- ---------------------------------------------------------------------------
-- run_log: one row per harvester invocation
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.run_log (
    id                          BIGSERIAL PRIMARY KEY,
    source_id                   TEXT NOT NULL,
    started_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at                 TIMESTAMPTZ,
    code_sha                    TEXT,
    expected_schema_version     INTEGER,
    args                        JSONB,
    model_versions              JSONB,
    items_fetched               INTEGER DEFAULT 0,
    items_deposited             INTEGER DEFAULT 0,
    items_failed                INTEGER DEFAULT 0,
    llm_cost_usd                NUMERIC(10, 4) DEFAULT 0,
    status                      TEXT NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    error                       TEXT
);
CREATE INDEX IF NOT EXISTS run_log_source_started_idx
    ON harvest.run_log (source_id, started_at DESC);

-- ---------------------------------------------------------------------------
-- fetched_items: every item we've encountered, indexed for seen-checks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.fetched_items (
    item_id         TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL,
    raw_hash        TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          TEXT NOT NULL DEFAULT 'fetched'
                    CHECK (status IN ('fetched', 'deposited', 'skipped', 'failed')),
    run_id          BIGINT REFERENCES harvest.run_log(id),
    inbox_path      TEXT,
    error           TEXT
);
CREATE INDEX IF NOT EXISTS fetched_items_source_idx
    ON harvest.fetched_items (source_id, fetched_at DESC);

-- ---------------------------------------------------------------------------
-- query_log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.query_log (
    id                  BIGSERIAL PRIMARY KEY,
    source_id           TEXT NOT NULL,
    query               JSONB NOT NULL,
    executed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    results_count       INTEGER,
    new_items_count     INTEGER,
    run_id              BIGINT REFERENCES harvest.run_log(id)
);

-- ---------------------------------------------------------------------------
-- data_sources
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.data_sources (
    source_id                   TEXT PRIMARY KEY,
    name                        TEXT NOT NULL,
    provider                    TEXT,
    provider_type               TEXT,
    construct                   TEXT,
    unit_of_analysis            TEXT,
    population_description      TEXT,
    sampling_frame              TEXT,
    representativeness          TEXT,
    measurement_method          TEXT,
    temporal_resolution         TEXT,
    geographic_coverage         TEXT,
    access_url                  TEXT,
    access_method               TEXT,
    machine_readable            BOOLEAN,
    normalization_category      INTEGER CHECK (normalization_category BETWEEN 1 AND 4),
    crosswalk_status            TEXT,
    ontology_mappings           JSONB,
    discovery_date              DATE,
    last_checked                TIMESTAMPTZ,
    status                      TEXT NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active', 'proposed', 'rejected', 'dormant'))
);

-- ---------------------------------------------------------------------------
-- construct_mappings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.construct_mappings (
    construct_id            TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    definition              TEXT NOT NULL,
    ontology_entity         TEXT,
    comparable_constructs   JSONB,
    comparison_caveats      TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- crosswalks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.crosswalks (
    id                  BIGSERIAL PRIMARY KEY,
    from_taxonomy       TEXT NOT NULL,
    from_code           TEXT NOT NULL,
    to_taxonomy         TEXT NOT NULL,
    to_code             TEXT NOT NULL,
    mapping_type        TEXT CHECK (mapping_type IN ('1-1', '1-many', 'many-1', 'approximate')),
    confidence          NUMERIC(3, 2),
    source              TEXT,
    valid_from          DATE,
    valid_to            DATE,
    UNIQUE (from_taxonomy, from_code, to_taxonomy, to_code)
);

-- ---------------------------------------------------------------------------
-- document_metadata
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.document_metadata (
    doc_id              BIGSERIAL PRIMARY KEY,
    source_id           TEXT NOT NULL,
    title               TEXT,
    authors             JSONB,
    doi                 TEXT,
    source_url          TEXT NOT NULL,
    published_date      DATE,
    document_type       TEXT,
    payload             JSONB,
    raw_hash            TEXT,
    created_by_run_id   BIGINT REFERENCES harvest.run_log(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, source_url)
);
CREATE INDEX IF NOT EXISTS document_metadata_source_idx
    ON harvest.document_metadata (source_id, published_date DESC);

-- ---------------------------------------------------------------------------
-- stochastic_provenance
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.stochastic_provenance (
    table_name      TEXT NOT NULL,
    row_pk          BIGINT NOT NULL,
    field           TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    prompt_hash     TEXT NOT NULL,
    params          JSONB,
    confidence      REAL,
    reviewed        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (table_name, row_pk, field)
);

-- ---------------------------------------------------------------------------
-- raw_manifest mirror (parquet is canonical; this exists for SQL joins)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS harvest.raw_manifest (
    raw_hash            TEXT PRIMARY KEY,
    source_id           TEXT NOT NULL,
    source_url          TEXT NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL,
    request_params      JSONB,
    content_type        TEXT,
    byte_size           BIGINT,
    file_path_relative  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS raw_manifest_source_idx
    ON harvest.raw_manifest (source_id, fetched_at DESC);

-- ---------------------------------------------------------------------------
-- Record this migration as applied
-- ---------------------------------------------------------------------------
INSERT INTO harvest.schema_migrations (filename, sha256, description)
VALUES ('001_harvest_init.sql', 'PLACEHOLDER_SHA', 'Initialize harvest schema')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
