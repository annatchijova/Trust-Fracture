"""Regression tests for the versioned v1 seal contract."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from trust_fracture.evidence import seal, verify_seal

VERIFIER = Path(__file__).resolve().parents[1] / "scripts" / "verify_finding.py"
V1_DIGEST = "fd37a939f99b2937864fe0c667c77bfbeb41885aed25c7b38fbbf57ec1d16540"


def test_verify_seal_rejects_unsupported_version() -> None:
    sealed = seal({"decision": "verified"}, sealed_at="2026-11-21T00:00:00Z")
    assert not verify_seal(replace(sealed, canonicalize_version="2"))


@pytest.mark.parametrize("version", ["1", "2", 1, True, None])
def test_standalone_verifier_checks_version(tmp_path: Path, version: object) -> None:
    sealed = seal({"decision": "verified"}, sealed_at="2026-11-21T00:00:00Z")
    assert sealed.digest == V1_DIGEST
    document = sealed.to_json_dict()
    if version is None:
        del document["canonicalize_version"]
    else:
        document["canonicalize_version"] = version

    path = tmp_path / "finding.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(VERIFIER), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if version == "1":
        assert result.returncode == 0
        assert f"OK: digest matches ({V1_DIGEST})" in result.stdout
    else:
        assert result.returncode == 1
        assert "unsupported or missing canonicalization version" in result.stderr
        assert "Traceback" not in result.stderr
