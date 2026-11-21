"""Level 3 canonicalization and sealing tests."""

from __future__ import annotations

import hashlib

import pytest

from trust_fracture.evidence import CanonicalizationError, canonicalize, seal, verify_seal


def test_canonicalize_sorts_dict_keys_regardless_of_input_order() -> None:
    a = canonicalize({"b": 1, "a": 2})
    b = canonicalize({"a": 2, "b": 1})
    assert a == b


def test_canonicalize_distinguishes_bool_from_int() -> None:
    assert canonicalize(True) != canonicalize(1)
    assert canonicalize(False) != canonicalize(0)


def test_canonicalize_distinguishes_int_from_string() -> None:
    assert canonicalize(1) != canonicalize("1")


def test_canonicalize_rejects_float() -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize(1.5)


def test_canonicalize_rejects_float_nested_in_structure() -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize({"ratio": 0.5})


def test_canonicalize_is_deterministic_across_repeated_calls() -> None:
    payload = {"z": [1, 2, {"y": "x"}], "a": None, "flag": True}
    assert canonicalize(payload) == canonicalize(payload)


def test_seal_digest_matches_direct_sha256_of_canonical_bytes() -> None:
    payload = {"finding_id": "f1", "epistemic_state": "POTENTIAL_PATH"}
    sealed = seal(payload, sealed_at="2026-11-21T00:00:00+00:00")
    expected = hashlib.sha256(canonicalize(payload)).hexdigest()
    assert sealed.digest == expected


def test_verify_seal_accepts_an_untampered_seal() -> None:
    sealed = seal({"a": 1}, sealed_at="2026-11-21T00:00:00+00:00")
    assert verify_seal(sealed)


def test_verify_seal_rejects_a_tampered_payload() -> None:
    sealed = seal({"a": 1}, sealed_at="2026-11-21T00:00:00+00:00")
    tampered = type(sealed)(
        canonicalize_version=sealed.canonicalize_version,
        payload={"a": 2},
        digest=sealed.digest,
        sealed_at=sealed.sealed_at,
    )
    assert not verify_seal(tampered)


def test_sealed_at_is_not_part_of_the_digest() -> None:
    """Chain-of-custody metadata recorded outside the hashed payload must
    not change the digest -- CLAUDE.md 5.2."""
    payload = {"a": 1}
    sealed_1 = seal(payload, sealed_at="2026-01-01T00:00:00+00:00")
    sealed_2 = seal(payload, sealed_at="2099-01-01T00:00:00+00:00")
    assert sealed_1.digest == sealed_2.digest
