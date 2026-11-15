#!/usr/bin/env python3
"""Identity of data under substitution and transformation.

Chronus orders. Theseus swaps every part. Ovid changes the form.

The contract: a record has canonical bytes and a digest over them. A
declared *preserving* transformation must leave the digest identical. A
declared *breaking* transformation must change it and must emit a face
record naming the delta. A transformation that is not declared is a
failure, so the registry is exhaustive-checked rather than trusted.

Bidirectional is the whole point. A digest invariant under everything is
useless; one invariant under nothing flags every edit. Theseus proves the
first half, Ovid the second, and neither passes alone.

This digest contract is separate from the process-local Theseus store and
the Ovid content-addressed pointers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

LOG = logging.getLogger("identity")


class IdentityError(RuntimeError):
    """Raised when the identity contract is violated."""


def canonical(value: Any) -> bytes:
    """Canonical bytes for a record. Sorted keys, exact floats, no spaces."""
    return json.dumps(
        _normalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _normalise(value: Any) -> Any:
    """Type-tagged encoding: every value is [tag, payload], so no two
    distinct Python types can produce the same canonical bytes."""
    if value is None:
        return ["none", None]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["float", format(value, ".17g")]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, list):
        return ["list", [_normalise(v) for v in value]]
    if isinstance(value, tuple):
        return ["tuple", [_normalise(v) for v in value]]
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise IdentityError(
                    f"dictionary keys must be str, got {type(k).__name__}"
                )
        return ["dict", {k: _normalise(v) for k, v in value.items()}]
    raise IdentityError(f"not canonicalisable: {type(value).__name__}")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class Transformation:
    """A named change. `preserving` decides what the digest must do."""

    name: str
    apply: Callable[[dict], dict]
    preserving: bool


@dataclass(frozen=True)
class Face:
    """One face of the data. Recorded only for breaking transformations."""

    index: int
    transformation: str
    before: str
    after: str
    changed_keys: tuple[str, ...]


def _diff(before: dict, after: dict) -> tuple[str, ...]:
    keys = set(before) | set(after)
    return tuple(sorted(k for k in keys if before.get(k) != after.get(k)))


def assert_theseus(record: dict, swaps: Sequence[Transformation]) -> str:
    """Every preserving swap must leave the digest byte-identical."""
    original = digest(record)
    for swap in swaps:
        if not swap.preserving:
            raise IdentityError(f"{swap.name} is not preserving")
        if digest(swap.apply(record)) != original:
            raise IdentityError(f"{swap.name} moved the digest while preserving")
    LOG.info("theseus: %d swaps, identity held", len(swaps))
    return original


def assert_ovid(record: dict, changes: Sequence[Transformation]) -> list[Face]:
    """Every breaking change must move the digest and name what moved."""
    faces: list[Face] = []
    current = record
    for change in changes:
        if change.preserving:
            raise IdentityError(f"{change.name} is not breaking")
        before = digest(current)
        moved = change.apply(current)
        after = digest(moved)
        if after == before:
            raise IdentityError(f"{change.name} broke nothing")
        faces.append(
            Face(len(faces), change.name, before, after, _diff(current, moved))
        )
        current = moved
    return faces


def _face_record(face: Face) -> dict:
    return {
        "i": face.index,
        "n": face.transformation,
        "b": face.before,
        "a": face.after,
        "c": list(face.changed_keys),
    }


def _link_digest(face: Face, previous: str) -> str:
    return digest({"face": _face_record(face), "p": previous})


@dataclass
class Chain:
    """Chronus: ordered faces, each bound to its predecessor.

    Each link stores the complete face and the digest of the link before it.
    Consecutive faces must describe a continuous history: a face's `before`
    digest must equal the previous face's `after` digest.
    """

    links: list[tuple[Face, str]] = field(default_factory=list)

    def append(self, face: Face) -> None:
        if face.index != len(self.links):
            raise IdentityError(f"gap at {face.index}, expected {len(self.links)}")
        previous = "0" * 64
        if self.links:
            last_face, last_recorded = self.links[-1]
            if face.before != last_face.after:
                raise IdentityError(
                    f"{face.transformation} does not continue from {last_face.transformation}"
                )
            previous = _link_digest(last_face, last_recorded)
        self.links.append((face, previous))

    def verify(self) -> int:
        """Recompute the chain. Returns the length; raises on any gap."""
        previous = "0" * 64
        prior: Face | None = None
        for expected, (face, recorded) in enumerate(self.links):
            if face.index != expected:
                raise IdentityError(f"gap at {face.index}, expected {expected}")
            if recorded != previous:
                raise IdentityError(f"{face.transformation} is not bound to its predecessor")
            if prior is not None and face.before != prior.after:
                raise IdentityError(f"{face.transformation} does not continue from {prior.transformation}")
            previous = _link_digest(face, recorded)
            prior = face
        return len(self.links)


def check_registry_complete(
    declared: Iterable[str], present: Iterable[str]
) -> None:
    """Every transformation in the codebase must be declared."""
    missing = sorted(set(present) - set(declared))
    if missing:
        raise IdentityError(f"undeclared transformations: {missing}")


def _swap(field_name: str, value: Any, *, preserving: bool = True) -> Transformation:
    return Transformation(
        name=f"swap:{field_name}",
        apply=lambda record, field_name=field_name, value=value: {
            **record,
            field_name: value,
        },
        preserving=preserving,
    )


def _drop(field_name: str) -> Transformation:
    return Transformation(
        name=f"drop:{field_name}",
        apply=lambda record, field_name=field_name: {
            key: item for key, item in record.items() if key != field_name
        },
        preserving=False,
    )


def _self_test() -> None:
    record = {
        "claim": "CO-014",
        "amount": 1250.0,
        "jurisdiction": "DIFC",
        "verified": True,
        "absent": [],
    }
    swaps = [_swap("jurisdiction", "DIFC"), _swap("verified", True)]
    breaks = [_drop("verified"), _swap("amount", 1250.5, preserving=False)]

    original = assert_theseus(record, swaps)
    assert original == digest(record)

    faces = assert_ovid(record, breaks)
    assert len(faces) == 2
    assert faces[0].changed_keys == ("verified",)
    assert faces[1].changed_keys == ("amount",)

    chain = Chain()
    for face in faces:
        chain.append(face)
    assert chain.verify() == 2

    try:
        assert_ovid(record, [_swap("amount", 1250.0, preserving=False)])
    except IdentityError as exc:
        if "broke nothing" not in str(exc):
            raise
    else:
        raise AssertionError("no-op declared as breaking must fail")

    try:
        canonical(object())
    except IdentityError:
        pass
    else:
        raise AssertionError("opaque type must be rejected")

    # Value-type collisions must not share a digest.
    assert digest({"x": 1250.0}) != digest({"x": "1250"})
    assert digest({"x": b"\xde\xad"}) != digest({"x": {"$bytes": "dead"}})
    assert digest({"x": True}) != digest({"x": 1})

    # Non-string keys are rejected rather than silently stringified.
    try:
        canonical({1: "x"})
    except IdentityError:
        pass
    else:
        raise AssertionError("non-str key must be rejected")

    # Deletion of a None-valued key and Python-equal swaps are named.
    assert _diff({"k": None}, {}) == ("k",)
    assert _diff({"k": True}, {"k": 1}) == ("k",)

    # Unrelated faces with correct indices must not form a chain.
    unrelated = [
        Face(0, "a", "1" * 64, "2" * 64, ("x",)),
        Face(1, "b", "3" * 64, "4" * 64, ("y",)),
    ]
    bad = Chain()
    bad.append(unrelated[0])
    try:
        bad.append(unrelated[1])
    except IdentityError:
        pass
    else:
        raise AssertionError("discontinuous faces must not chain")

    LOG.info("identity self test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _self_test()
    print("theseus held, ovid recorded, chain verified")
