"""Digest identity: Theseus preserves, Ovid breaks, Chronus orders the faces."""

import pytest

from chronus.identity import (
    Chain,
    Face,
    IdentityError,
    Transformation,
    assert_ovid,
    assert_theseus,
    canonical,
    check_registry_complete,
    digest,
    _self_test,
)


RECORD = {
    "claim": "CO-014",
    "amount": 1250.0,
    "jurisdiction": "DIFC",
    "verified": True,
    "absent": [],
}


def _swap(name: str, value, *, preserving: bool) -> Transformation:
    return Transformation(
        name,
        lambda record, value=value: {**record, "amount": value},
        preserving,
    )


def test_self_test_passes():
    _self_test()


def test_canonical_bytes_are_stable_and_reject_opaque_values():
    assert canonical(RECORD) == canonical(dict(reversed(list(RECORD.items()))))
    assert digest(RECORD) == digest(RECORD)
    with pytest.raises(IdentityError, match="not canonicalisable"):
        canonical(object())


def test_theseus_rejects_a_preserving_swap_that_moves_the_digest():
    with pytest.raises(IdentityError, match="moved the digest"):
        assert_theseus(RECORD, [_swap("swap:amount", 1.0, preserving=True)])


def test_ovid_names_the_keys_that_moved():
    faces = assert_ovid(
        RECORD,
        [
            Transformation(
                "drop:verified",
                lambda record: {k: v for k, v in record.items() if k != "verified"},
                False,
            ),
            _swap("swap:amount", 1250.5, preserving=False),
        ],
    )
    assert [face.changed_keys for face in faces] == [("verified",), ("amount",)]
    assert faces[0].before != faces[0].after


def test_chain_binds_each_face_to_its_predecessor():
    face = Face(0, "drop:verified", "a" * 64, "b" * 64, ("verified",))
    chain = Chain()
    chain.append(face)
    assert chain.verify() == 1

    broken = Chain()
    broken.append(face)
    broken.links.append((1, "swap:amount", "c" * 64, "0" * 64))
    with pytest.raises(IdentityError, match="not bound"):
        broken.verify()


def test_chain_rejects_a_gap():
    chain = Chain()
    chain.links.append((1, "swap:amount", "a" * 64, "0" * 64))
    with pytest.raises(IdentityError, match="gap"):
        chain.verify()


def test_registry_is_exhaustive():
    check_registry_complete(["swap:amount"], ["swap:amount"])
    with pytest.raises(IdentityError, match="undeclared"):
        check_registry_complete(["swap:amount"], ["swap:amount", "drop:verified"])
