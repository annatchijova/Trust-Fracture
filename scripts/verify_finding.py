#!/usr/bin/env python3
"""Independent, stdlib-only verifier for a sealed Trust Fracture finding.

Per CLAUDE.md 5.2: "The verifier is stdlib-only and independent of the
producing code." This script does not import trust_fracture, and
deliberately reimplements the canonical encoding from
src/trust_fracture/evidence.py rather than importing it -- so a bug in
that module's encoder cannot silently escape detection by also being
present in the thing meant to catch it. If this script's output ever
disagrees with trust_fracture.evidence.verify_seal on the same file, that
disagreement is itself a finding: treat it as a determinism defect to
investigate, not as "pick whichever answer you prefer."

Usage: python3 scripts/verify_finding.py <finding.json>
Exit code 0 for a matching v1 seal, 1 for invalid input or mismatch, 2 for usage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

SUPPORTED_CANONICALIZE_VERSION = "1"


def encode(value: Any) -> str:
    if isinstance(value, bool):
        return "b:" + ("1" if value else "0")
    if isinstance(value, int):
        return "i:" + str(value)
    if isinstance(value, float):
        raise ValueError("float is never permitted in a sealed payload")
    if value is None:
        return "n:"
    if isinstance(value, str):
        return "s:" + json.dumps(value, ensure_ascii=True)
    if isinstance(value, list):
        return "l:[" + ",".join(encode(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("all dict keys in a sealed payload must be strings")
        items = sorted(value.items(), key=lambda kv: kv[0])
        return "m:{" + ",".join(f"{encode(k)}:{encode(v)}" for k, v in items) + "}"
    raise ValueError(f"unsupported type in sealed payload: {type(value).__name__}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <finding.json>", file=sys.stderr)
        return 2

    try:
        with open(argv[1], encoding="utf-8") as f:
            sealed = json.load(f)
        if not isinstance(sealed, dict):
            raise ValueError("expected a JSON object")
        version = sealed.get("canonicalize_version")
        if version != SUPPORTED_CANONICALIZE_VERSION:
            raise ValueError(f"unsupported or missing canonicalization version: {version!r}")
        payload = sealed.get("payload")
        claimed_digest = sealed.get("digest")
        if not isinstance(payload, dict) or not isinstance(claimed_digest, str):
            raise ValueError("expected an object payload and a string digest")
        canonical_bytes = encode(payload).encode("utf-8")
    except (OSError, ValueError, RecursionError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    recomputed_digest = hashlib.sha256(canonical_bytes).hexdigest()

    if recomputed_digest == claimed_digest:
        print(f"OK: digest matches ({recomputed_digest})")
        return 0

    print(
        "MISMATCH: the payload's recomputed digest does not match the "
        f"claimed digest.\n  claimed:    {claimed_digest}\n  recomputed: {recomputed_digest}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
