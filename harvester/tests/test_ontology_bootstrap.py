"""Tests for Neo4j ontology bootstrap.

Skipped unless NEO4J_URI / NEO4J_USER / NEO4J_PASS env vars are set.
"""

import os
import pytest

from harvester.ontology.bootstrap import bootstrap, count_entities


@pytest.mark.skipif(
    not (os.environ.get("NEO4J_URI") and os.environ.get("NEO4J_PASS")),
    reason="NEO4J_URI/NEO4J_PASS not set; skipping Neo4j integration test",
)
def test_bootstrap_creates_expected_entities():
    bootstrap()
    counts = count_entities()
    assert counts.get("Technology", 0) >= 6
    assert counts.get("MeasurementProblem", 0) >= 4
    assert counts.get("Agency", 0) >= 7
    assert counts.get("Dataset", 0) >= 6


@pytest.mark.skipif(
    not (os.environ.get("NEO4J_URI") and os.environ.get("NEO4J_PASS")),
    reason="NEO4J_URI/NEO4J_PASS not set; skipping Neo4j integration test",
)
def test_bootstrap_is_idempotent():
    before = count_entities()
    bootstrap()
    after = count_entities()
    assert before == after, f"counts changed on re-run: {before} -> {after}"
