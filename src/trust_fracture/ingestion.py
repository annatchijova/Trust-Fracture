"""Level 1 ingestion layer: reads raw scenario input.

Per docs/ARCHITECTURE.md layer 1: this is the only module that touches raw
scenario input; it does not interpret or validate the content's shape
against the graph schema (that is normalization.py, layer 2), and it never
talks to Relate (that is graph_store.py, layer 3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class IngestionError(ValueError):
    """Raised when a scenario file cannot be read as JSON."""


def load_scenario_file(path: str | Path) -> dict[str, Any]:
    scenario_path = Path(path)
    try:
        raw_text = scenario_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionError(f"cannot read scenario file {scenario_path}: {exc}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise IngestionError(f"{scenario_path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise IngestionError(
            f"{scenario_path} must contain a JSON object with 'nodes' and "
            f"'relationships', got {type(data).__name__}"
        )
    return data
