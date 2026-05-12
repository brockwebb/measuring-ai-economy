"""Neo4j ontology bootstrap.

Reads seed_entities.yaml and MERGEs nodes into Neo4j keyed on (label, name).
Idempotent — re-running upgrades properties but does not duplicate.

Env vars (matching Wintermute's existing convention):
    NEO4J_URI       (default: bolt://localhost:7687)
    NEO4J_USER      (default: neo4j)
    NEO4J_PASS      (required)
    NEO4J_DB        (default: neo4j)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from neo4j import GraphDatabase


_SEED_PATH = Path(__file__).parent / "seed_entities.yaml"


def _driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASS"]
    return GraphDatabase.driver(uri, auth=(user, password))


def _database() -> str:
    return os.environ.get("NEO4J_DB", "neo4j")


def bootstrap() -> None:
    """MERGE all seed entities into Neo4j."""
    seed = yaml.safe_load(_SEED_PATH.read_text())
    version = seed.pop("bootstrap_version", 1)
    driver = _driver()
    try:
        with driver.session(database=_database()) as session:
            for label, items in seed.items():
                for item in items:
                    name = item.get("name")
                    if not name:
                        continue
                    props = {**item, "bootstrap_version": version}
                    session.run(
                        f"MERGE (n:{label} {{name: $name}}) SET n += $props",
                        name=name,
                        props=props,
                    )
    finally:
        driver.close()


def count_entities() -> dict[str, int]:
    """Return {label: count} for the seed labels."""
    seed = yaml.safe_load(_SEED_PATH.read_text())
    labels = [k for k in seed.keys() if k != "bootstrap_version"]
    driver = _driver()
    counts: dict[str, int] = {}
    try:
        with driver.session(database=_database()) as session:
            for label in labels:
                rec = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
                counts[label] = rec["c"] if rec else 0
    finally:
        driver.close()
    return counts


if __name__ == "__main__":
    bootstrap()
    print(count_entities())
