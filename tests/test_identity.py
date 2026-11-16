"""Digest identity: Theseus preserves, Ovid breaks, Chronus orders the faces."""

import copy
import json

import pytest

from chronus.identity import (
    EXACT_INT_FLOAT,
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
    _swap,
)


RECORD = {
    "claim": "CO-014",
    "amount": 1250.0,
    "jurisdiction": "DIFC",
    "verified": True,
    "absent": [],
    "result": {"lucas": "123", "index": 10},
}


def test_self_test_passes():
    _self_test()


def test_integer_float_is_the_same_datum_inside_the_exact_range():
    assert digest({"n": 123}) == digest({"n": 123.0})
    assert digest({"n": 123}) != digest({"n": "123"})
    assert digest(True) != digest(1)
    huge = float(EXACT_INT_FLOAT)
    assert digest({"n": huge}) != digest({"n": int(huge)})
    assert digest(b"\xde\xad") != digest({"$bytes": "dead"})
    with pytest.raises(IdentityError, match="dictionary keys"):
        canonical({1: "x"})


def test_same_swap_runs_under_both_contracts():
    same = _swap("status", "COMPLETED")
    record = {"status": "COMPLETED", "tenant_id": "dev"}
    assert_theseus(record, [same])
    with pytest.raises(IdentityError, match="broke nothing"):
        assert_ovid(record, [same.as_breaking()])

    changed = _swap("status", "FAILED").as_breaking()
    faces = assert_ovid(record, [changed])
    assert faces[0].changed_keys == ("status",)
    assert faces[0].before != faces[0].after


def test_theseus_accepts_structural_substitution():
    assert_theseus(
        RECORD,
        [
            Transformation("reorder", lambda record: {k: record[k] for k in reversed(list(record))}, True),
            Transformation("round-trip", lambda record: json.loads(json.dumps(record)), True),
            _swap("amount", 1250),
        ],
    )


def test_theseus_rejects_a_preserving_swap_that_moves_the_digest():
    with pytest.raises(IdentityError, match="moved the digest"):
        assert_theseus(RECORD, [_swap("amount", 1.0)])
    with pytest.raises(IdentityError, match="is not preserving"):
        assert_theseus(RECORD, [_swap("amount", 1.0, False)])


def test_theseus_and_ovid_reject_undeclared_names():
    with pytest.raises(IdentityError, match="undeclared"):
        assert_theseus(RECORD, [_swap("amount", 1250.0)], declared=[])
    with pytest.raises(IdentityError, match="undeclared"):
        assert_ovid(RECORD, [_swap("amount", 1.0).as_breaking()], declared=["drop:verified"])


def test_ovid_names_dotted_paths_and_presence():
    faces = assert_ovid(
        {"keep": 1, "gone": None, "flag": True, "result": {"lucas": "123"}},
        [
            Transformation(
                "drop:gone",
                lambda record: {key: value for key, value in record.items() if key != "gone"},
                False,
            ),
            Transformation("swap:flag", lambda record: {**record, "flag": 1}, False),
            Transformation(
                "edit:lucas",
                lambda record: {**record, "result": {**record["result"], "lucas": "322"}},
                False,
            ),
        ],
    )
    assert faces[0].changed_keys == ("gone",)
    assert faces[1].changed_keys == ("flag",)
    assert faces[2].changed_keys == ("result.lucas",)


def test_dotted_key_is_not_a_nested_path():
    top = assert_ovid(
        {"a.b": 1},
        [Transformation("edit:top", lambda record: {**record, "a.b": 2}, False)],
    )
    nested = assert_ovid(
        {"a": {"b": 1}},
        [Transformation("edit:nested", lambda record: {"a": {"b": 2}}, False)],
    )
    assert top[0].changed_keys == ("a\\.b",)
    assert nested[0].changed_keys == ("a.b",)


def test_empty_key_is_not_dropped_from_the_path():
    faces = assert_ovid(
        {"": {"x": 1}, "x": 1},
        [Transformation("edit", lambda record: {"": {"x": 2}, "x": 2}, False)],
    )
    assert faces[0].changed_keys == (".x", "x")


def test_ovid_snapshots_an_in_place_edit():
    record = {"amount": 1250.0, "nested": {"x": 0}}
    original = copy.deepcopy(record)

    def mutate(current):
        current["amount"] = 1
        current["nested"]["x"] = 2
        return current

    faces = assert_ovid(record, [Transformation("mutate", mutate, False)])
    assert record == original
    assert faces[0].changed_keys == ("amount", "nested.x")


def test_chain_is_tied_to_the_record_and_rejects_a_reroot():
    faces = assert_ovid(RECORD, [_swap("amount", 1).as_breaking(), _swap("verified", False).as_breaking()])
    chain = Chain.for_record(RECORD)
    for face in faces:
        chain.append(face)
    assert chain.verify() == 2
    assert faces[1].before == faces[0].after

    dated = chain.links[0]
    chain.links[0] = (dated[0], dated[1], dated[2] - 10.0, dated[3], dated[4], dated[5])
    with pytest.raises(IdentityError, match="not bound"):
        chain.verify()

    truncated = Chain(origin="0" * 64)
    second = faces[1]
    truncated.links.append(
        (0, second.transformation, second.at, second.before, "0" * 64, second.after)
    )
    with pytest.raises(IdentityError, match="record origin"):
        truncated.verify()


def test_expected_head_rejects_a_tail_edit():
    one = assert_ovid(RECORD, [_swap("amount", 1).as_breaking()])
    single = Chain.for_record(RECORD)
    single.append(one[0])
    stored = single.head()
    assert single.verify(stored) == 1
    link = single.links[0]
    single.links[0] = (link[0], link[1], link[2] - 5.0, link[3], link[4], link[5])
    with pytest.raises(IdentityError, match="chain head"):
        single.verify(stored)

    two = assert_ovid(
        RECORD,
        [_swap("amount", 1).as_breaking(), _swap("verified", False).as_breaking()],
    )
    chain = Chain.for_record(RECORD)
    for face in two:
        chain.append(face)
    stored = chain.head()
    last = chain.links[-1]
    chain.links[-1] = (last[0], last[1], last[2], last[3], last[4], "f" * 64)
    with pytest.raises(IdentityError, match="chain head"):
        chain.verify(stored)
    assert chain.verify() == 2


def test_chain_rejects_a_gap():
    chain = Chain.for_record(RECORD)
    chain.links.append((1, "swap:amount", 0.0, "a" * 64, chain.origin, "b" * 64))
    with pytest.raises(IdentityError, match="gap"):
        chain.verify()


def test_seed_42_record_is_not_hardcoded_to_one_payload():
    with open("evidence/chronus/modeA_42.json", encoding="utf-8") as handle:
        evidence = json.load(handle)
    held = digest(evidence)
    assert_theseus(evidence, [_swap("device_run", "NOT_RUN")])
    faces = assert_ovid(evidence, [_swap("device_run", "RUN").as_breaking()])
    assert faces[0].changed_keys == ("device_run",)
    assert digest(evidence) == held


def test_registry_is_exhaustive():
    check_registry_complete(["swap:amount"], ["swap:amount"])
    with pytest.raises(IdentityError, match="undeclared"):
        check_registry_complete(["swap:amount"], ["swap:amount", "drop:verified"])


def test_unrelated_face_does_not_continue():
    origin = digest(RECORD)
    face = Face(0, "swap:amount", 1.0, origin, digest({"n": 1}), ("amount",))
    chain = Chain(origin)
    chain.append(face)
    with pytest.raises(IdentityError, match="does not start where"):
        chain.append(Face(1, "swap:verified", 2.0, "c" * 64, "d" * 64, ("verified",)))
