"""Exercise observation validation through the CLI and real Relate storage."""

from pathlib import Path

from click.testing import CliRunner
import pytest

from trust_fracture.cli import main
from trust_fracture.graph_store import GraphStore


@pytest.mark.parametrize(
    ("event", "timestamp", "error"),
    [
        ("trace-1", "2026-02-30T00:00:00Z", "explicit UTC offset"),
        ("trace-1", "2026-11-21T00:00:00", "explicit UTC offset"),
        ("tool-1", "2026-11-21T00:00:00Z", "must be a TraceEvent"),
        ("trace-1", "2026-11-21T00:00:00-03:00", None),
    ],
)
def test_observe_validates_event_and_timestamp(
    tmp_path: Path, event: str, timestamp: str, error: str | None,
) -> None:
    runner = CliRunner()
    path = tmp_path / "observations.rl"
    database = ["--database", str(path)]
    fixture = Path(__file__).with_name("fixtures") / "minimal_scenario.json"
    loaded = runner.invoke(main, ["load", str(fixture), *database])
    assert loaded.exit_code == 0, loaded.output

    result = runner.invoke(main, [
        "observe", *database, "--trace-event", event, "--observed-at", timestamp,
        "--node", "agent-1", "--node", "tool-1",
    ])
    with GraphStore(path, read_only=True) as store:
        if error is None:
            assert result.exit_code == 0, (result.output, result.exception)
            assert store.common_trace_events("agent-1", "tool-1") == (event,)
        else:
            assert result.exit_code == 1, result.output
            assert error in result.output
            assert store.get_node("trace-1") is None
            assert store.common_trace_events("agent-1", "tool-1") == ()
