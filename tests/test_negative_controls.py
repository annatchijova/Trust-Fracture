"""Run the Level 4 negative controls through the CLI and independent verifier."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys

from click.testing import CliRunner
import pytest

from trust_fracture.cli import main

FIXTURE = Path(__file__).with_name("fixtures") / "negative_controls.json"
VERIFIER = Path(__file__).resolve().parents[1] / "scripts" / "verify_finding.py"


@dataclass(frozen=True)
class NegativeControl:
    name: str
    state: str
    path: tuple[str, ...]
    reason: str
    observations: tuple[tuple[str, ...], ...] = ()
    supporting_traces: tuple[int, ...] = ()
    max_hops: int = 6
    observed_edges: tuple[str, ...] = ()


CASES = (
    NegativeControl("benign-content", "INSUFFICIENT_EVIDENCE", (), "no path found",
                    observations=(("source", "actor"),)),
    NegativeControl("quoted-data", "INSUFFICIENT_EVIDENCE", (), "no path found",
                    observations=(("source", "artifact", "actor"),)),
    NegativeControl("authorized", "OBSERVED_FLOW", ("source", "actor", "operation", "target"),
                    "holds every permission",
                    observations=(("source", "actor"), ("actor", "operation"), ("operation", "target")),
                    supporting_traces=(0, 1, 2),
                    observed_edges=("actor-reads-source", "actor-invokes-operation", "operation-targets-target")),
    NegativeControl("structural-only", "POTENTIAL_PATH", ("source", "actor", "operation", "target"),
                    "no TraceEvent backs"),
    NegativeControl("insufficient", "INSUFFICIENT_EVIDENCE", (), "no path found within max_hops=2",
                    max_hops=2),
    NegativeControl("blocked", "POTENTIAL_PATH", ("source", "actor", "operation", "target"),
                    "blocked-actor -> blocked-operation",
                    observations=(("source", "actor"), ("actor", "control")), supporting_traces=(0,),
                    observed_edges=("actor-reads-source",)),
)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_negative_control(case: NegativeControl, tmp_path: Path) -> None:
    runner = CliRunner()
    database = ["--database", str(tmp_path / "scenario.rl")]
    result = runner.invoke(main, ["load", str(FIXTURE), *database])
    assert result.exit_code == 0, (result.output, result.exception)

    for index, observation in enumerate(case.observations):
        node_args = [argument for node in observation for argument in ("--node", f"{case.name}-{node}")]
        edge_args = []
        if index < len(case.observed_edges):
            edge_args = ["--relationship", f"{case.name}-{case.observed_edges[index]}"]
        result = runner.invoke(main, [
            "observe", *database, "--trace-event", f"{case.name}-trace-{index}",
            "--observed-at", f"2026-11-21T00:00:0{index}Z", *node_args, *edge_args,
        ])
        assert result.exit_code == 0, (result.output, result.exception)

    finding_path = tmp_path / "finding.json"
    seal_args = [
        "seal-finding", *database, "--source", f"{case.name}-source",
        "--target", f"{case.name}-target", "--actor", f"{case.name}-actor",
        "--operation", f"{case.name}-operation", "--finding-id", case.name,
        "--out", str(finding_path),
    ]
    result = runner.invoke(main, [*seal_args, "--max-hops", str(case.max_hops)])
    assert result.exit_code == 0, (result.output, result.exception)
    payload = json.loads(finding_path.read_text(encoding="utf-8"))["payload"]
    assert payload["epistemic_state"] == case.state
    assert payload["path_node_ids"] == [f"{case.name}-{node}" for node in case.path]
    assert payload["trace_event_ids"] == [f"{case.name}-trace-{i}" for i in case.supporting_traces]
    assert any(case.reason in reason for reason in payload["reasons"])

    verification = subprocess.run(
        [sys.executable, "-I", "-S", str(VERIFIER), str(finding_path)],
        capture_output=True, text=True, check=False,
    )
    assert verification.returncode == 0, verification.stderr

    if case.name == "insufficient":
        result = runner.invoke(main, [*seal_args, "--max-hops", "3"])
        assert result.exit_code == 0, (result.output, result.exception)
        expanded = json.loads(finding_path.read_text(encoding="utf-8"))["payload"]
        assert expanded["epistemic_state"] == "POTENTIAL_PATH"
        assert expanded["path_node_ids"] == [
            "insufficient-source", "insufficient-actor", "insufficient-operation", "insufficient-target",
        ]
