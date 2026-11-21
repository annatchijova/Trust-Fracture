"""Level 3, part 1: canonical serialization and SHA-256 sealing.

Per CLAUDE.md 5.2 (deterministic core) and docs/ARCHITECTURE.md layer 6
("Evidence management"): one canonical encoder, used everywhere --
type-tagged (bool checked before int, since `isinstance(True, int)` is
True in Python), recursively key-sorted, stamped with a version. No float
is accepted anywhere in a sealed payload: this project's decision path
never produces one (counts and ratios would use `fractions.Fraction`, not
needed yet since Level 3 seals structural findings, not ratios), and this
encoder fails closed rather than silently truncating one if it ever did.

The independent verifier this module's docstring promises is NOT a
function in this module -- see scripts/verify_finding.py, a separate,
stdlib-only script that does not import trust_fracture at all, so a bug
in this encoder cannot silently propagate into the thing meant to catch it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

CANONICALIZE_VERSION = "1"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized -- includes any float,
    since this project's sealed path never carries one (CLAUDE.md 5.2)."""


def canonicalize(value: Any) -> bytes:
    return _encode(value).encode("utf-8")


def _encode(value: Any) -> str:
    # bool MUST be checked before int: isinstance(True, int) is True.
    if isinstance(value, bool):
        return "b:" + ("1" if value else "0")
    if isinstance(value, int):
        return "i:" + str(value)
    if isinstance(value, float):
        raise CanonicalizationError(
            "float is never permitted in a sealed payload (CLAUDE.md 5.2)"
        )
    if value is None:
        return "n:"
    if isinstance(value, str):
        return "s:" + json.dumps(value, ensure_ascii=True)
    if isinstance(value, (list, tuple)):
        return "l:[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("all dict keys in a sealed payload must be strings")
        items = sorted(value.items(), key=lambda kv: kv[0])
        return "m:{" + ",".join(f"{_encode(k)}:{_encode(v)}" for k, v in items) + "}"
    raise CanonicalizationError(f"unsupported type in sealed payload: {type(value).__name__}")


@dataclass(frozen=True)
class SealedFinding:
    canonicalize_version: str
    payload: dict[str, Any]
    digest: str
    # Chain-of-custody metadata recorded OUTSIDE the hashed payload
    # (CLAUDE.md 5.2): changing this never changes the digest, and the
    # digest never vouches for it -- it is provenance about the seal, not
    # part of what was sealed.
    sealed_at: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "canonicalize_version": self.canonicalize_version,
            "payload": self.payload,
            "digest": self.digest,
            "sealed_at": self.sealed_at,
        }


def seal(payload: dict[str, Any], *, sealed_at: str) -> SealedFinding:
    digest = hashlib.sha256(canonicalize(payload)).hexdigest()
    return SealedFinding(
        canonicalize_version=CANONICALIZE_VERSION,
        payload=payload,
        digest=digest,
        sealed_at=sealed_at,
    )


def verify_seal(sealed: SealedFinding) -> bool:
    """Checks the canonicalization version and recomputes the payload digest.
    This lives in the engine
    for convenience (e.g. a same-process round-trip test); the actual
    reproducibility contract this project relies on is
    scripts/verify_finding.py, which does this independently of all of
    this module's code.
    """
    if sealed.canonicalize_version != CANONICALIZE_VERSION:
        return False
    return hashlib.sha256(canonicalize(sealed.payload)).hexdigest() == sealed.digest
