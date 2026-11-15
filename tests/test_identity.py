"""Digest identity: Theseus preserves, Ovid breaks, Chronus orders the faces."""

import copy

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


def test_canonical_bytes_distinguish_types():
    assert canonical(RECORD) == canonical(dict(reversed(list(RECORD.items()))))
    assert digest({"x": 1.0}) != digest({"x": "1"})
    assert digest(True) != digest(1)
    assert digest(b"\xde\xad") != digest({"$bytes": "dead"})
    with pytest.raises(IdentityError, match="dictionary keys"):
        canonical({1: "x"})
    with pytest.raises(IdentityError, match="not canonicalisable"):
        canonical(object())


def test_theseus_rejects_a_preserving_swap_that_moves_the_digest():
    with pytest.raises(IdentityError, match="moved the digest"):
        assert_theseus(
            RECORD,
            [_swap("swap:amount", 1.0, preserving=True)],
            declared=["swap:amount"],
        )


def test_theseus_and_ovid_reject_undeclared_names():
    preserving = _swap("swap:amount", 1250.0, preserving=True)
    breaking = _swap("swap:amount", 1.0, preserving=False)
    with pytest.raises(IdentityError, match="undeclared"):
        assert_theseus(RECORD, [preserving], declared=[])
    with pytest.raises(IdentityError, match="undeclared"):
        assert_ovid(RECORD, [breaking], declared=["drop:verified"])


def test_ovid_names_presence_and_canonical_deltas():
    faces = assert_ovid(
        {"keep": 1, "gone": None, "flag": True},
        [
            Transformation(
                "drop:gone",
                lambda record: {key: value for key, value in record.items() if key != "gone"},
                False,
            ),
            Transformation(
                "swap:flag",
                lambda record: {**record, "flag": 1},
                False,
            ),
        ],
        declared=["drop:gone", "swap:flag"],
    )
    assert faces[0].changed_keys == ("gone",)
    assert faces[1].changed_keys == ("flag",)


def test_ovid_snapshots_an_in_place_edit():
    record = {"amount": 1250.0, "nested": {"x": 0}}
    original = copy.deepcopy(record)

    def mutate(current):
        current["amount"] = 1
        current["nested"]["x"] = 2
        return current

    faces = assert_ovid(
        record,
        [Transformation("mutate", mutate, False)],
        declared=["mutate"],
    )
    assert record == original
    assert faces[0].changed_keys == ("amount", "nested")


def test_chain_binds_outcome_and_terminal_digest():
    face = Face(0, "drop:verified", "a" * 64, "b" * 64, ("verified",))
    chain = Chain()
    chain.append(face)
    tip = chain.tip()
    assert chain.verify(tip=tip) == 1

    chain.links[-1] = (
        0,
        "tampered",
        face.before,
        face.after,
        face.changed_keys,
        chain.links[-1][5],
    )
    with pytest.raises(IdentityError, match="terminal digest"):
        chain.verify(tip=tip)

    unrelated = Face(1, "swap:amount", "c" * 64, "d" * 64, ("amount",))
    fresh = Chain()
    fresh.append(face)
    with pytest.raises(IdentityError, match="does not continue"):
        fresh.append(unrelated)


def test_chain_rejects_a_gap_and_a_broken_predecessor():
    chain = Chain()
    chain.links.append((1, "swap:amount", "a" * 64, "b" * 64, ("amount",), "0" * 64))
    with pytest.raises(IdentityError, match="gap"):
        chain.verify()

    bound = Chain()
    first = Face(0, "drop:verified", "a" * 64, "b" * 64, ("verified",))
    bound.append(first)
    bound.links.append((1, "swap:amount", "b" * 64, "c" * 64, ("amount",), "0" * 64))
    with pytest.raises(IdentityError, match="not bound"):
        bound.verify()


def test_registry_is_exhaustive():
    check_registry_complete(["swap:amount"], ["swap:amount"])
    with pytest.raises(IdentityError, match="undeclared"):
        check_registry_complete(["swap:amount"], ["swap:amount", "drop:verified"])
