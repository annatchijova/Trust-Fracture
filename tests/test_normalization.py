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


def test_derived_only_relationship_type_rejected_from_scenario_input() -> None:
    """Regression for the Level 1 red-team finding: a scenario file could
    declare CROSSES_BOUNDARY/DERIVED_FROM/SUPPORTED_BY/OBSERVED_IN directly
    as a hand-asserted fact, even though docs/GRAPH_MODEL.md classifies
    them as derived-only -- they must exist only once the engine itself
    has computed or observed them, never as ingested scenario content."""
    scenario = _base_scenario()
    scenario["nodes"].append({"type": "TrustBoundary", "id": "boundary-1", "provenance": "p"})
    scenario["relationships"][0]["type"] = "CROSSES_BOUNDARY"
    scenario["relationships"][0]["target"] = "boundary-1"
    with pytest.raises(NormalizationError):
        normalize_scenario(scenario, source="test")
