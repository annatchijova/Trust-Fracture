"""Wires ingestion -> normalization -> persistence for Level 1.

Kept as its own module (rather than inlined in the CLI) so the same load
path is reusable from tests and, later, from the scenario corpus (Level 4)
without going through argument parsing.
"""

from __future__ import annotations

from pathlib import Path

from trust_fracture.graph_store import GraphStore
from trust_fracture.ingestion import load_scenario_file
from trust_fracture.normalization import ScenarioGraph, normalize_scenario


def load_scenario_into_store(scenario_path: str | Path, store: GraphStore) -> ScenarioGraph:
    raw = load_scenario_file(scenario_path)
    graph = normalize_scenario(raw, source=str(scenario_path))

    for node in graph.nodes:
        store.create_node(
            node.node_type,
            node.node_id,
            node.properties,
            provenance=node.provenance,
        )

    for rel in graph.relationships:
        store.create_relationship(
            rel.rel_type,
            rel.source_id,
            rel.target_id,
            relationship_id=rel.relationship_id,
            epistemic_status=rel.epistemic_status,
            provenance=rel.provenance,
            run_id=rel.run_id,
            observed_at=rel.observed_at,
        )

    return graph
