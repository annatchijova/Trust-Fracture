"""End-to-end Level 1 test: ingestion -> normalization -> real Relate store."""

from __future__ import annotations

import json
from pathlib import Path

from trust_fracture.graph_store import GraphStore
from trust_fracture.loader import load_scenario_into_store
from trust_fracture.schema import NodeType


def test_load_scenario_file_into_real_store(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"type": "Agent", "id": "agent-1", "provenance": "test"},
                    {"type": "Tool", "id": "tool-1", "provenance": "test"},
                ],
                "relationships": [
                    {
                        "type": "INVOKES",
                        "id": "rel-1",
                        "source": "agent-1",
                        "target": "tool-1",
                        "epistemic_status": "derived",
                        "provenance": "test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    db_path = tmp_path / "loaded.rl"
    with GraphStore(db_path) as store:
        graph = load_scenario_into_store(scenario_path, store)
        assert len(graph.nodes) == 2
        assert store.count_nodes(NodeType.AGENT) == 1
        assert store.count_nodes(NodeType.TOOL) == 1

    # Reopen in a new GraphStore instance -- the write actually persisted.
    with GraphStore(db_path, read_only=True) as reopened:
        assert reopened.count_nodes(NodeType.AGENT) == 1
