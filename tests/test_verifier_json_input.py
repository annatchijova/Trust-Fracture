"""Check JSON object validation at the independent verifier boundary."""

from pathlib import Path
import subprocess
import sys

import pytest

VERIFIER = Path(__file__).resolve().parents[1] / "scripts" / "verify_finding.py"


@pytest.mark.parametrize(
    "document",
    [
        '{"label": "catalog", "label": "catalog"}',
        '{"payload": {"labels": [{"name": "catalog", "name": "catalog"}]}}',
    ],
    ids=["envelope", "nested-object"],
)
def test_verifier_rejects_duplicate_json_members(tmp_path: Path, document: str) -> None:
    path = tmp_path / "finding.json"
    path.write_text(document, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("INVALID: duplicate JSON object member")
    assert not result.stdout
