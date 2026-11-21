"""Verify that a seal owns a snapshot of its payload."""

from trust_fracture.evidence import seal, verify_seal

SEALED_AT = "2026-11-21T00:00:00Z"


def test_seal_snapshots_nested_input() -> None:
    tags = ["catalog"]
    sealed = seal({"metadata": {"tags": tags}}, sealed_at=SEALED_AT)
    tags.append("updated")

    assert sealed.payload == {"metadata": {"tags": ["catalog"]}}
    assert verify_seal(sealed)


def test_json_export_does_not_share_nested_payload() -> None:
    sealed = seal({"metadata": {"tags": ["catalog"]}}, sealed_at=SEALED_AT)
    exported = sealed.to_json_dict()
    exported["payload"]["metadata"]["tags"].append("updated")

    assert sealed.payload == {"metadata": {"tags": ["catalog"]}}
    assert verify_seal(sealed)
