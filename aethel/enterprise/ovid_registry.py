"""Versioned Ovid fold/unfold registry — reject unknown versions.

Transform v1 uses aethel.encoding Zeckendorf fold/unfold.
Working form stored as UTF-8 JSON describing the ZeckendorfVector.

Every registered version carries a declared
:class:`aethel.ovid.TransformContract`: exactness class, domain, invariants,
residual/error contract. A version registered without a contract is still
executable for compatibility, but :meth:`OvidRegistry.contract` then fails
closed — an undeclared transform is never silently classified EXACT. A
transform declared UNSUPPORTED cannot fold or unfold at all.
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, Tuple

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


def _v1_contract() -> Any:
    """The declared contract for the v1 Zeckendorf transform."""
    from aethel.encoding import MAX_FOLD_LEN
    from aethel.ovid import Exactness, TransformContract, ZECKENDORF_TRANSFORM_ID

    contract = TransformContract(
        transform_id=ZECKENDORF_TRANSFORM_ID,
        version=OVID_TRANSFORM_V1,
        exactness=Exactness.EXACT,
        reversible=True,
        domain=(
            ("payload_bytes_max", MAX_FOLD_LEN),
            ("chunk_bytes", 8),
            ("element", "bytes"),
            ("working_form", "zeckendorf_vector_v1 JSON"),
        ),
        invariants=(
            "every mask satisfies non-adjacency: mask & (mask << 1) == 0",
            "working-form JSON is canonical (sort_keys, compact separators)",
            "unknown working-form kinds fail closed",
        ),
        residuals="none — every payload chunk retains a Zeckendorf mask",
        error_bound=0.0,
        support="len(payload) <= max_fold_len; larger payloads shard upstream",
    )
    contract.validate()
    return contract


def _check_contract(contract: Any) -> None:
    """Validate a registered contract's declaration consistency."""
    from aethel.ovid import TransformContract

    if not isinstance(contract, TransformContract):
        raise SchemaVersionError(
            "transform contract must be an aethel.ovid.TransformContract"
        )
    try:
        contract.validate()
    except ValueError as exc:
        raise SchemaVersionError(f"transform contract inconsistent: {exc}") from exc


def _contract_unsupported(contract: Any) -> bool:
    from aethel.ovid import Exactness

    return contract is not None and contract.exactness is Exactness.UNSUPPORTED


class OvidRegistry:
    """Maps ovid_transform_version -> (fold, unfold) callables + contract."""

    def __init__(self) -> None:
        self._reg: Dict[int, Tuple[Callable[[bytes], bytes], Callable[[bytes], bytes]]] = {
            OVID_TRANSFORM_V1: (_fold_v1, _unfold_v1),
        }
        self._contracts: Dict[int, Any] = {OVID_TRANSFORM_V1: _v1_contract()}
        # Unfold is a pure, keyless function of (version, working bytes). The
        # custody plane authenticates every envelope (HMAC + digests) on each
        # load, and each load unfolds the same immutable record several times
        # (primary, replica, read-back); repeated health reconciliation would
        # otherwise redo the exact Zeckendorf decode for every record, making
        # strict-M3 checks O(ledger) in arithmetic. Results are memoised by the
        # SHA-256 of the exact input bytes, so any altered byte misses the
        # cache and is unfolded (and authenticated) afresh. Bounded by bytes.
        self._unfold_cache: "OrderedDict[tuple[int, bytes], bytes]" = OrderedDict()
        self._unfold_cache_bytes = 0
        self._unfold_lock = threading.Lock()

    def register(
        self,
        version: int,
        fold_fn: Callable[[bytes], bytes],
        unfold_fn: Callable[[bytes], bytes],
        *,
        contract: Any = None,
    ) -> None:
        if version < 1:
            raise SchemaVersionError("transform version must be >= 1")
        if contract is not None:
            _check_contract(contract)
        self._reg[int(version)] = (fold_fn, unfold_fn)
        self._contracts[int(version)] = contract
        with self._unfold_lock:
            self._unfold_cache.clear()
            self._unfold_cache_bytes = 0

    def supported(self) -> tuple[int, ...]:
        return tuple(sorted(self._reg))

    def contract(self, version: int) -> Any:
        """The declared contract for ``version`` — fails closed when absent."""
        if version not in self._reg:
            raise SchemaVersionError(f"unknown ovid_transform_version={version}")
        contract = self._contracts.get(version)
        if contract is None:
            raise SchemaVersionError(
                f"ovid_transform_version={version} has no declared transform "
                "contract — refusing to classify it implicitly"
            )
        return contract

    def contracts(self) -> Dict[int, Dict[str, Any]]:
        """Declared contracts for every registered version (serializable)."""
        out: Dict[int, Dict[str, Any]] = {}
        for version in self.supported():
            contract = self._contracts.get(version)
            out[version] = contract.to_dict() if contract is not None else None
        return out

    def _gate(self, version: int) -> None:
        if version not in self._reg:
            raise SchemaVersionError(f"unknown ovid_transform_version={version}")
        if _contract_unsupported(self._contracts.get(version)):
            raise SchemaVersionError(
                f"ovid_transform_version={version} is declared UNSUPPORTED"
            )

    def fold(self, payload: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
        self._gate(version)
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("fold payload must be bytes")
        return self._reg[version][0](bytes(payload))

    _UNFOLD_CACHE_MAX_BYTES = 64 * 1024 * 1024

    def unfold(self, working: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
        self._gate(version)
        if not isinstance(working, (bytes, bytearray)):
            return self._reg[version][1](working)
        key = (int(version), hashlib.sha256(bytes(working)).digest())
        with self._unfold_lock:
            hit = self._unfold_cache.get(key)
            if hit is not None:
                self._unfold_cache.move_to_end(key)
                return hit
        result = self._reg[version][1](working)
        if isinstance(result, bytes) and len(result) <= self._UNFOLD_CACHE_MAX_BYTES // 8:
            with self._unfold_lock:
                if key not in self._unfold_cache:
                    self._unfold_cache[key] = result
                    self._unfold_cache_bytes += len(result)
                    while self._unfold_cache_bytes > self._UNFOLD_CACHE_MAX_BYTES:
                        _, old = self._unfold_cache.popitem(last=False)
                        self._unfold_cache_bytes -= len(old)
        return result


DEFAULT_OVID_REGISTRY = OvidRegistry()


def fold_versioned(payload: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
    return DEFAULT_OVID_REGISTRY.fold(payload, version)


def unfold_versioned(working: bytes, version: int = OVID_TRANSFORM_V1) -> bytes:
    return DEFAULT_OVID_REGISTRY.unfold(working, version)


def supported_transform_versions() -> tuple[int, ...]:
    return DEFAULT_OVID_REGISTRY.supported()


def transform_contract(version: int = OVID_TRANSFORM_V1) -> Any:
    return DEFAULT_OVID_REGISTRY.contract(version)


def transform_contracts() -> Dict[int, Dict[str, Any]]:
    return DEFAULT_OVID_REGISTRY.contracts()


__all__ = [
    "OvidRegistry",
    "DEFAULT_OVID_REGISTRY",
    "fold_versioned",
    "unfold_versioned",
    "supported_transform_versions",
    "transform_contract",
    "transform_contracts",
    "b64e",
    "b64d",
]
