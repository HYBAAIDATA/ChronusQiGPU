"""Versioned Ovid fold/unfold registry — reject unknown versions.

Transform v1 uses aethel.encoding Zeckendorf fold/unfold.
Working form stored as UTF-8 JSON describing the ZeckendorfVector.
"""
from __future__ import annotations

import base64
import json
from typing import Callable, Dict, Tuple

from .errors import SchemaVersionError
from .schema import OVID_TRANSFORM_V1


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _fold_v1(payload: bytes) -> bytes:
    from aethel.encoding import fold

    vector = fold(payload)
    doc = {
        "kind": "zeckendorf_vector_v1",
        "blocks": [[int(off), int(mask)] for off, mask in vector.blocks],
        "total_bytes": int(vector.total_bytes),
        "folded_units": int(vector.folded_units),
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _unfold_v1(working: bytes) -> bytes:
    from aethel.encoding import ZeckendorfVector, unfold

    if isinstance(working, str):
        working = working.encode("utf-8")
    doc = json.loads(working.decode("utf-8"))
    if doc.get("kind") != "zeckendorf_vector_v1":
        raise SchemaVersionError(f"unknown working-form kind: {doc.get('kind')!r}")
    blocks = tuple((int(o), int(m)) for o, m in doc["blocks"])
    vector = ZeckendorfVector(blocks=blocks, total_bytes=int(doc["total_bytes"]))
    if not vector.verify():
        raise SchemaVersionError("working-form ZeckendorfVector failed verify")
    out = unfold(vector)
    return out


class OvidRegistry:
    """Maps ovid_transform_version -> (fold, unfold) callables."""

    def __init__(self) -> None:
        self._reg: Dict[int, Tuple[Callable[[bytes], bytes], Callable[[bytes], bytes]]] = {
            OVID_TRANSFORM_V1: (_fold_v1, _unfold_v1),
        }

    def register(
        self,
        version: int,
        fold_fn: Callable[[bytes], bytes],
        unfold_fn: Callable[[bytes], bytes],
    ) -> None:
        if version < 1:
            raise SchemaVersionError("transform version must be >= 1")
        self._reg[int(version)] = (fold_fn, unfold_fn)

    def supported(self) -> tuple[int, ...]:
        return tuple(sorted(self._reg))

    def fold(self, payload: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
        if version not in self._reg:
            raise SchemaVersionError(f"unknown ovid_transform_version={version}")
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("fold payload must be bytes")
        return self._reg[version][0](bytes(payload))

    def unfold(self, working: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
        if version not in self._reg:
            raise SchemaVersionError(f"unknown ovid_transform_version={version}")
        return self._reg[version][1](working)


DEFAULT_OVID_REGISTRY = OvidRegistry()


def fold_versioned(payload: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
    return DEFAULT_OVID_REGISTRY.fold(payload, version)


def unfold_versioned(working: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
    return DEFAULT_OVID_REGISTRY.unfold(working, version)


def supported_transform_versions() -> tuple[int, ...]:
    return DEFAULT_OVID_REGISTRY.supported()


__all__ = [
    "OvidRegistry",
    "DEFAULT_OVID_REGISTRY",
    "fold_versioned",
    "unfold_versioned",
    "supported_transform_versions",
    "b64e",
    "b64d",
]
