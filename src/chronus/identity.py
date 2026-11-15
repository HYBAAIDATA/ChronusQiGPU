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

Canonical bytes tag each value with its type. A float is not a string, a
bool is not an int, bytes are not a dictionary, and dictionary keys must
already be strings. This digest is not `chronus.canon.canonical_bytes`,
which rejects floats.

This digest contract is separate from the process-local Theseus store and
the Ovid content-addressed pointers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

LOG = logging.getLogger("identity")

# index, name, before, after, changed keys, predecessor digest
Link = tuple[int, str, str, str, tuple[str, ...], str]


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
        # Binary64 bits, not decimal text: distinct NaN payloads stay distinct.
        return ["float", struct.pack("!d", value).hex()]
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


@dataclass(frozen=True)
class Face:
    """One face of the data. Recorded only for breaking transformations."""

    index: int
    transformation: str
    before: str
    after: str
    changed_keys: tuple[str, ...]


def _changed(before: dict, after: dict) -> tuple[str, ...]:
    keys = set(before) | set(after)
    changed: list[str] = []
    for key in sorted(keys):
        if (key in before) != (key in after):
            changed.append(key)
        elif canonical(before[key]) != canonical(after[key]):
            changed.append(key)
    return tuple(changed)


def _apply(change: Transformation, record: dict) -> tuple[dict, dict]:
    """Return a snapshot and the transformation of a separate copy."""
    snapshot = copy.deepcopy(record)
    moved = change.apply(copy.deepcopy(snapshot))
    return snapshot, moved


def assert_theseus(
    record: dict, swaps: Sequence[Transformation], *, declared: Iterable[str]
) -> str:
    """Every preserving swap must leave the digest byte-identical."""
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
    record: dict, changes: Sequence[Transformation], *, declared: Iterable[str]
) -> list[Face]:
    """Every breaking change must move the digest and name what moved."""
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
            Face(len(faces), change.name, before, after, _changed(snapshot, moved))
        )
        current = moved
    return faces


def _link_digest(
    index: int,
    name: str,
    before: str,
    after: str,
    changed: tuple[str, ...],
    previous: str,
) -> str:
    return digest(
        {
            "i": index,
            "n": name,
            "b": before,
            "a": after,
            "k": list(changed),
            "p": previous,
        }
    )


@dataclass
class Chain:
    """Chronus: ordered faces, each bound to its predecessor and its outcome."""

    links: list[Link] = field(default_factory=list)

    def append(self, face: Face) -> None:
        if face.index != len(self.links):
            raise IdentityError(f"gap at {face.index}, expected {len(self.links)}")
        previous = "0" * 64
        if self.links:
            prior = self.links[-1]
            if face.before != prior[3]:
                raise IdentityError(
                    f"{face.transformation} does not continue {prior[1]}"
                )
            previous = _link_digest(*prior[:5], prior[5])
        self.links.append(
            (
                face.index,
                face.transformation,
                face.before,
                face.after,
                face.changed_keys,
                previous,
            )
        )

    def tip(self) -> str:
        """Digest of the last committed face. Edits to that face change it."""
        previous = "0" * 64
        for link in self.links:
            previous = _link_digest(*link[:5], previous)
        return previous

    def verify(self, *, tip: str | None = None) -> int:
        """Recompute the chain. Returns the length; raises on any gap."""
        previous = "0" * 64
        prior_after: str | None = None
        for expected, link in enumerate(self.links):
            index, name, before, after, _changed_keys, recorded = link
            if index != expected:
                raise IdentityError(f"gap at {index}, expected {expected}")
            if recorded != previous:
                raise IdentityError(f"{name} is not bound to its predecessor")
            if prior_after is not None and before != prior_after:
                raise IdentityError(f"{name} does not continue its predecessor")
            previous = _link_digest(*link[:5], previous)
            prior_after = after
        if tip is not None and previous != tip:
            raise IdentityError("terminal digest does not match")
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
    swap_names = [swap.name for swap in swaps]
    break_names = [change.name for change in breaks]

    original = assert_theseus(record, swaps, declared=swap_names)
    assert original == digest(record)
    assert record["amount"] == 1250.0

    faces = assert_ovid(record, breaks, declared=break_names)
    assert len(faces) == 2
    assert faces[0].changed_keys == ("verified",)
    assert faces[1].changed_keys == ("amount",)
    assert faces[1].before == faces[0].after

    chain = Chain()
    for face in faces:
        chain.append(face)
    tip = chain.tip()
    assert chain.verify(tip=tip) == 2

    try:
        assert_theseus(record, swaps, declared=["swap:jurisdiction"])
    except IdentityError as exc:
        if "undeclared" not in str(exc):
            raise
    else:
        raise AssertionError("undeclared preserving swap must fail")

    try:
        assert_ovid(record, [_swap("amount", 1250.0, preserving=False)], declared=["swap:amount"])
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

    assert digest({"x": 1.0}) != digest({"x": "1"})
    assert digest(b"\xde\xad") != digest({"$bytes": "dead"})
    LOG.info("identity self test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _self_test()
    print("theseus held, ovid recorded, chain verified")
