#!/usr/bin/env python3
"""Identity of data under substitution and transformation.

Chronus orders. Theseus swaps every part. Ovid changes the form.

The contract: a record has canonical bytes and a digest over them. A
declared *preserving* transformation must leave the digest identical. A
declared *breaking* transformation must change it and must emit a face
record naming the delta. The same swap can be re-declared under the
other contract. A transformation that is not in a supplied registry is
a failure.

Bidirectional is the whole point. A digest invariant under everything is
useless; one invariant under nothing flags every edit. Theseus proves the
first half, Ovid the second, and neither passes alone.

An integer float inside the exact binary64 range is the same datum as
that integer. Other floats keep a decimal form. Strings, bools, and
bytes stay tagged so they do not collide with those numbers. Dictionary
keys must already be strings. This digest is not
`chronus.canon.canonical_bytes`, which rejects floats.

The chain is bound to the record digest it starts from. Each face must
start where the previous face ended, and its timestamp is part of the
link. This digest contract is separate from the process-local Theseus
store and the Ovid content-addressed pointers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Sequence

LOG = logging.getLogger("identity")

# index, name, at, before, predecessor digest, after
Link = tuple[int, str, float, str, str, str]
EXACT_INT_FLOAT = 2**53


class IdentityError(RuntimeError):
    """Raised when the identity contract is violated."""


def canonical(value: Any) -> bytes:
    """Canonical bytes for a record. Sorted keys, no spaces."""
    return json.dumps(
        _normalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        for key in value:
            if type(key) is not str:
                raise IdentityError(
                    f"dictionary keys must be strings, got {type(key).__name__}"
                )
        pairs = [[key, _normalise(item)] for key, item in value.items()]
        pairs.sort(key=lambda pair: pair[0])
        return ["object", pairs]
    if isinstance(value, (list, tuple)):
        return ["list", [_normalise(item) for item in value]]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, bool):
        return ["bool", value]
    if value is None:
        return ["null", None]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer() and abs(value) < EXACT_INT_FLOAT:
            return ["int", int(value)]
        return ["float", format(value, ".17g")]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    raise IdentityError(f"not canonicalisable: {type(value).__name__}")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class Transformation:
    """A named change. `preserving` decides what the digest must do."""

    name: str
    apply: Callable[[dict], dict]
    preserving: bool

    def as_breaking(self) -> "Transformation":
        """Re-declare the same change under the breaking contract."""
        return replace(self, preserving=False)


@dataclass(frozen=True)
class Face:
    """One face of the data. Recorded only for breaking transformations."""

    index: int
    transformation: str
    at: float
    before: str
    after: str
    changed_keys: tuple[str, ...]


def _changed(before: dict, after: dict, prefix: str = "") -> tuple[str, ...]:
    changed: list[str] = []
    for key in sorted(set(before) | set(after)):
        path = f"{prefix}.{key}" if prefix else key
        if (key in before) != (key in after):
            changed.append(path)
            continue
        left, right = before[key], after[key]
        if isinstance(left, dict) and isinstance(right, dict):
            changed.extend(_changed(left, right, path))
        elif canonical(left) != canonical(right):
            changed.append(path)
    return tuple(changed)


def _apply(change: Transformation, record: dict) -> tuple[dict, dict]:
    """Return a snapshot and the transformation of a separate copy."""
    snapshot = copy.deepcopy(record)
    moved = change.apply(copy.deepcopy(snapshot))
    return snapshot, moved


def assert_theseus(
    record: dict,
    swaps: Sequence[Transformation],
    *,
    declared: Iterable[str] | None = None,
) -> str:
    """Every preserving swap must leave the digest byte-identical."""
    if declared is not None:
        check_registry_complete(declared, (swap.name for swap in swaps))
    original = digest(record)
    for swap in swaps:
        if not swap.preserving:
            raise IdentityError(f"{swap.name} is not preserving")
        snapshot, moved = _apply(swap, record)
        if digest(moved) != digest(snapshot):
            raise IdentityError(f"{swap.name} moved the digest while preserving")
    LOG.info("theseus: %d swaps, identity held", len(swaps))
    return original


def assert_ovid(
    record: dict,
    changes: Sequence[Transformation],
    *,
    declared: Iterable[str] | None = None,
) -> list[Face]:
    """Every breaking change must move the digest and name what moved."""
    if declared is not None:
        check_registry_complete(declared, (change.name for change in changes))
    faces: list[Face] = []
    current = copy.deepcopy(record)
    for change in changes:
        if change.preserving:
            raise IdentityError(f"{change.name} is not breaking")
        snapshot, moved = _apply(change, current)
        before = digest(snapshot)
        after = digest(moved)
        if after == before:
            raise IdentityError(f"{change.name} broke nothing")
        faces.append(
            Face(
                len(faces),
                change.name,
                time.time(),
                before,
                after,
                _changed(snapshot, moved),
            )
        )
        current = moved
    return faces


def _link_digest(index: int, name: str, at: float, before: str, previous: str, after: str) -> str:
    return digest({"i": index, "n": name, "t": at, "b": before, "p": previous, "a": after})


@dataclass
class Chain:
    """Chronus: ordered faces, each bound to its predecessor and to the record's origin."""

    origin: str
    links: list[Link] = field(default_factory=list)

    @classmethod
    def for_record(cls, record: dict) -> "Chain":
        return cls(digest(record))

    def _bound(self, link: Link) -> str:
        index, name, at, before, recorded, after = link
        return _link_digest(index, name, at, before, recorded, after)

    def append(self, face: Face) -> None:
        if face.index != len(self.links):
            raise IdentityError(f"gap at {face.index}, expected {len(self.links)}")
        if self.links:
            if face.before != self.links[-1][5]:
                raise IdentityError(
                    f"{face.transformation} does not start where {len(self.links) - 1} ended"
                )
            recorded = self._bound(self.links[-1])
        else:
            if face.before != self.origin:
                raise IdentityError(
                    f"{face.transformation} does not start at the record origin"
                )
            recorded = self.origin
        self.links.append(
            (face.index, face.transformation, face.at, face.before, recorded, face.after)
        )

    def verify(self) -> int:
        """Recompute the chain. Returns the length; raises on any gap."""
        previous = self.origin
        for expected, link in enumerate(self.links):
            index, name, at, before, recorded, after = link
            if index != expected:
                raise IdentityError(f"gap at {index}, expected {expected}")
            if recorded != previous:
                raise IdentityError(f"{name} is not bound to its predecessor")
            if expected == 0 and before != self.origin:
                raise IdentityError(f"{name} does not start at the record origin")
            if expected and self.links[expected - 1][5] != before:
                raise IdentityError(f"{name} does not start where {expected - 1} ended")
            previous = _link_digest(index, name, at, before, previous, after)
        return len(self.links)


def check_registry_complete(declared: Iterable[str], present: Iterable[str]) -> None:
    """Every transformation passed in must be declared."""
    missing = sorted(set(present) - set(declared))
    if missing:
        raise IdentityError(f"undeclared transformations: {missing}")


def _swap(field_name: str, value: Any, preserving: bool = True) -> Transformation:
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


def _reorder(record: dict) -> dict:
    return {key: record[key] for key in reversed(list(record))}


def _self_test() -> None:
    record = {
        "claim": "CO-014",
        "amount": 1250.0,
        "jurisdiction": "DIFC",
        "verified": True,
        "absent": [],
    }
    assert digest({"n": 123}) == digest({"n": 123.0})
    assert digest({"n": 123}) != digest({"n": "123"})
    huge = float(EXACT_INT_FLOAT)
    assert digest({"n": huge}) != digest({"n": int(huge)})

    held = _swap("amount", 1250)
    assert_theseus(record, [held])
    assert_theseus(
        record,
        [
            Transformation("reorder", _reorder, True),
            Transformation("round-trip", lambda item: json.loads(json.dumps(item)), True),
        ],
    )
    moved = _swap("amount", 1250.5).as_breaking()
    faces = assert_ovid(record, [moved])
    assert faces[0].changed_keys == ("amount",)
    assert faces[0].before != faces[0].after

    try:
        assert_ovid(record, [held.as_breaking()])
    except IdentityError as exc:
        if "broke nothing" not in str(exc):
            raise
    else:
        raise AssertionError("no-op re-declared as breaking must fail")

    chain = Chain.for_record(record)
    chain.append(faces[0])
    assert chain.verify() == 1
    assert chain.origin == faces[0].before

    try:
        canonical(object())
    except IdentityError:
        pass
    else:
        raise AssertionError("opaque type must be rejected")

    assert digest({"x": 1.0}) != digest({"x": "1"})
    assert digest(b"\xde\xad") != digest({"$bytes": "dead"})
    LOG.info("identity self test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _self_test()
    print("theseus held, ovid recorded, chain verified")
