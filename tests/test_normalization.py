"""Unit tests for the normalization layer -- schema validation, dangling
references, duplicate ids, unknown types."""

from __future__ import annotations

import pytest

from trust_fracture.normalization import NormalizationError, normalize_scenario


def _base_scenario() -> dict:
    return {
        "nodes": [
            {"type": "Agent", "id": "agent-1", "provenance": "p"},
            {"type": "Tool", "id": "tool-1", "provenance": "p"},
        ],
        "relationships": [
            {
                "type": "INVOKES",
                "id": "rel-1",
                "source": "agent-1",
                "target": "tool-1",
                "epistemic_status": "derived",
                "provenance": "p",
            }
        ],
    }


def test_valid_scenario_normalizes() -> None:
    graph = normalize_scenario(_base_scenario(), source="test")
    assert len(graph.nodes) == 2
    assert len(graph.relationships) == 1
    assert graph.relationships[0].source_id == "agent-1"


def test_nodes_must_be_a_list() -> None:
    scenario = _base_scenario()
    scenario["nodes"] = {}
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")


def test_unknown_node_type_rejected() -> None:
    scenario = _base_scenario()
    scenario["nodes"][0]["type"] = "NotARealType"
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")


def test_duplicate_node_id_rejected() -> None:
    scenario = _base_scenario()
    scenario["nodes"].append({"type": "Agent", "id": "agent-1", "provenance": "p"})
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")


def test_relationship_dangling_source_rejected() -> None:
    scenario = _base_scenario()
    scenario["relationships"][0]["source"] = "no-such-node"
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")


def test_relationship_dangling_target_rejected() -> None:
    scenario = _base_scenario()
    scenario["relationships"][0]["target"] = "no-such-node"
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")


def test_relationship_unknown_epistemic_status_rejected() -> None:
    scenario = _base_scenario()
    scenario["relationships"][0]["epistemic_status"] = "definitely_true"
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")


def test_missing_provenance_rejected() -> None:
    scenario = _base_scenario()
    del scenario["nodes"][0]["provenance"]
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")
