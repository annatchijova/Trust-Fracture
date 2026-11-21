"""Verify that the CLI persists a trace observation as a unit."""

from pathlib import Path

from click.testing import CliRunner

from trust_fracture.cli import main
from trust_fracture.graph_store import GraphStore


def test_failed_observation_leaves_no_trace_or_links(tmp_path: Path) -> None:
    runner = CliRunner()
    path = tmp_path / "observations.rl"
    database = ["--database", str(path)]
    fixture = Path(__file__).with_name("fixtures") / "minimal_scenario.json"
    loaded = runner.invoke(main, ["load", str(fixture), *database])
    assert loaded.exit_code == 0, loaded.output

    observation = [
        "observe", *database, "--trace-event", "trace-1",
        "--observed-at", "2026-11-21T00:00:00Z",
        "--node", "agent-1", "--node", "tool-1",
    ]
    failed = runner.invoke(main, [*observation, "--node", "missing-node"])
    assert failed.exit_code == 1
    assert "no node with id 'missing-node' exists" in failed.output

    with GraphStore(path, read_only=True) as store:
        assert store.get_node("trace-1") is None
        assert store.common_trace_events("agent-1", "tool-1") == ()

    retried = runner.invoke(main, observation)
    assert retried.exit_code == 0, (retried.output, retried.exception)
    with GraphStore(path, read_only=True) as store:
        assert store.common_trace_events("agent-1", "tool-1") == ("trace-1",)
