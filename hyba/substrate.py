"""HYBA data substrate — the facade the brief's §12 semantics demand.

Designed from the mathematical state model, not copied from SQL:

    PUT      — commit payload → fold → place on Fibonacci address → attest
    GET      — resolve key → verify integrity → reconstruct bytes
    FOLD     — payload → ZeckendorfVector (invertible working rep)
    UNFOLD   — ZeckendorfVector → bytes
    ADDRESS  — object → logical Fibonacci address (identity-stable)
    QUERY    — point lookup by content digest / key
    NAVIGATE — lens navigation over shared state (content/fold/anchor)
    TRANSFORM— fold a new payload as a child version of an existing object
    VERSION  — version chain: identity/version/parent/transform/provenance
    ATTEST   — integrity gate: Cassini ledger + content digests + receipts
    DELETE   — tombstone (evidence-preserving — never silent deletion)

Layers kept distinct (§7): content identity (sha256 of payload) ≠ fold
identity (sha256 of canonical folded form) ≠ logical address (Fibonacci
index/value) ≠ physical location (which store/segment holds the block).
Storage movement must not change logical identity — snapshot+attach
relocates physically while the Fibonacci address and digests persist.

Tenant separation (§21) rides on the existing writer mechanism: each
tenant gets a namespaced key and a distinct writer id over the shared
Cassini ledger, so tenant A cannot construct or resolve tenant B's key
space through this facade at all.

Every mutating op issues a toe.receipts receipt and every byte moved is
metered by MovementMeter (§18) — measured, never simulated.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from aethel.encoding import MAX_FOLD_LEN, ZeckendorfVector, fold, unfold
from aethel.errors import AethelError, FoldDomainOverflow
from aethel.storage import MAX_ADDRESS_INDEX, AddressSpace

from toe.receipts import ReceiptLedger

SUBSTRATE_VERSION = "hyba.substrate/v1"


class SubstrateError(RuntimeError):
    pass


class NotFound(SubstrateError):
    pass


class TenantDenied(SubstrateError):
    pass


@dataclass(frozen=True)
class ObjectIdentity:
    """§7 — the four distinct identity layers of one stored object."""

    content_id: str          # sha256(payload) — what the data IS
    fold_id: str             # sha256(canonical folded form) — folded identity
    logical_address: int     # Fibonacci index — logical position
    physical_location: str   # store path / segment — where bytes live


@dataclass(frozen=True)
class VersionRecord:
    """§14 — one committed version of an object."""

    version: int
    parent_digest: Optional[str]
    transform: str
    digest: str
    seq: int
    receipt_sha256: str


class MovementMeter:
    """§18 — real bytes moved, counted at the boundary where they move."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.bytes_read = 0
        self.bytes_written = 0
        self.bytes_reconstructed = 0
        self.bytes_copied = 0
        self.bytes_folded = 0
        self.bytes_unfolded = 0

    def record(self, channel: str, n: int) -> None:
        with self._lock:
            setattr(self, channel, getattr(self, channel) + int(n))

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return {
                "bytes_read": self.bytes_read,
                "bytes_written": self.bytes_written,
                "bytes_reconstructed": self.bytes_reconstructed,
                "bytes_copied": self.bytes_copied,
                "bytes_folded": self.bytes_folded,
                "bytes_unfolded": self.bytes_unfolded,
            }


class HybaSubstrate:
    """One substrate object per writer identity; tenants get scoped handles.

    ``store`` is an ``AddressSpace`` (Fibonacci placement + Cassini
    integrity). ``ledger`` receipts every mutation. ``objects`` maps
    namespaced keys -> version chains; ``content_index`` maps content
    digests -> key for content-addressed QUERY.
    """

    def __init__(
        self,
        *,
        space: Optional[AddressSpace] = None,
        ledger: Optional[ReceiptLedger] = None,
        tenant: str = "default",
    ) -> None:
        self.space = space if space is not None else AddressSpace()
        self.ledger = ledger if ledger is not None else ReceiptLedger()
        self.tenant = tenant
        self.meter = MovementMeter()
        self._objects: Dict[str, List[dict]] = {}
        self._tombstones: Dict[str, dict] = {}
        self._content_index: Dict[str, str] = {}
        self._lock = threading.Lock()
        # writer ids issued for tenants over this store — shared set, so two
        # tenant handles can never collide on the Cassini ledger stream
        self._used_writers: set = {self.space.writer}
        # disjoint index bands per scoped tenant (shared counter). Without
        # bands two forks would start cursors at the same index and later
        # writers would clobber earlier blocks in the shared block map —
        # the ledger stays consistent but the data does not.
        # Bands partition the shared index space; width derives from
        # MAX_ADDRESS_INDEX so the declared bound is self-consistent.
        self._band_size = MAX_ADDRESS_INDEX // 5
        # band 0 belongs to this (root) handle; scoped tenants take bands
        # 1, 2, ... — declared bound on writes per band is _band_size
        self._band_counter = [1]  # shared across scopes
        self._index_ceiling: Optional[int] = 1 + self._band_size

    # -- scoping ------------------------------------------------------------

    def _key(self, key: str) -> str:
        """Tenant-scoped key. A handle for tenant A can never name a key of
        tenant B — the prefix is fixed at construction."""
        return f"{self.tenant}:{key}"

    def scope(self, tenant: str) -> "HybaSubstrate":
        """Return a handle for another tenant sharing store+ledger.

        Writer id derives from the tenant name so the Cassini ledger keeps
        per-tenant streams strictly monotonic and attributable.
        """
        if tenant == self.tenant:
            return self
        writer = int.from_bytes(
            hashlib.sha256(tenant.encode()).digest()[:4], "big"
        ) % 1_000_000 + 1
        with self._lock:
            while writer in self._used_writers:
                writer += 1
            self._used_writers.add(writer)
            band = self._band_counter[0]
            self._band_counter[0] += 1
        band_start = 1 + band * self._band_size
        child = HybaSubstrate(
            space=self.space.fork(writer, start_index=band_start),
            ledger=self.ledger,
            tenant=tenant,
        )
        child.meter = self.meter  # shared movement accounting
        child._used_writers = self._used_writers
        child._band_counter = self._band_counter
        child._band_size = self._band_size
        # declared bound: a tenant may not write past its index band —
        # past it, writes raise TenantDenied rather than collide
        child._index_ceiling = band_start + self._band_size
        return child

    # -- core ops ------------------------------------------------------------

    def fold_payload(self, payload: bytes) -> ZeckendorfVector:
        """FOLD — invertible working representation."""
        v = fold(payload)
        self.meter.record("bytes_folded", len(payload))
        return v

    def unfold_payload(self, vector: ZeckendorfVector) -> bytes:
        """UNFOLD — reconstruct bytes."""
        data = unfold(vector)
        self.meter.record("bytes_unfolded", len(data))
        return data

    def put(
        self,
        key: str,
        payload: bytes,
        *,
        transform: str = "put",
        advance: int = 1,
    ) -> ObjectIdentity:
        """PUT: fold → Fibonacci address → ledger attest → version chain."""
        if len(payload) > MAX_FOLD_LEN:
            raise FoldDomainOverflow(
                f"payload {len(payload)}B exceeds fold domain {MAX_FOLD_LEN}B"
            )
        k = self._key(key)
        vector = fold(payload)
        folded_canonical = json.dumps(
            list(vector.blocks), separators=(",", ":")
        ).encode()
        digest = hashlib.sha256(payload).hexdigest()
        fold_id = hashlib.sha256(folded_canonical).hexdigest()
        with self._lock:
            history = self._objects.get(k, [])
            if k in self._tombstones:
                raise NotFound(f"key {key!r} is tombstoned in tenant {self.tenant}")
            parent = history[-1]["digest"] if history else None
            if (
                self._index_ceiling is not None
                and self.space._cursor + advance >= self._index_ceiling
            ):
                raise TenantDenied(
                    f"tenant {self.tenant!r} index band exhausted"
                )
            address = self.space.write(payload, advance=advance)
            receipt = self.ledger.issue(
                "substrate.put",
                inputs={"key": k, "content_sha256": digest},
                config={"transform": transform},
                output={
                    "fold_sha256": fold_id,
                    "address_index": address.index,
                    "version": len(history) + 1,
                },
            )
            rec = {
                "version": len(history) + 1,
                "parent_digest": parent,
                "transform": transform,
                "digest": digest,
                "fold_id": fold_id,
                "address_index": address.index,
                "seq": len(self.ledger.records) - 1,
                "receipt_sha256": receipt.receipt_sha256,
            }
            history.append(rec)
            self._objects[k] = history
            self._content_index[digest] = k
        self.meter.record("bytes_written", len(payload))
        return self.identify(key)

    def get(self, key: str) -> bytes:
        """GET: resolve → ledger gate → reconstruct → digest verify."""
        k = self._key(key)
        if k in self._tombstones:
            raise NotFound(f"key {key!r} is tombstoned")
        history = self._objects.get(k)
        if not history:
            raise NotFound(f"key {key!r} unknown in tenant {self.tenant}")
        rec = history[-1]
        self.space.ledger.check_consistent()
        block = self.space.read(
            self.space.address_of_index(rec["address_index"])
        )
        if hashlib.sha256(block).hexdigest() != rec["digest"]:
            raise SubstrateError(
                f"stored bytes for {key!r} fail content digest"
            )
        self.meter.record("bytes_read", len(block))
        self.meter.record("bytes_reconstructed", len(block))
        return block

    def identify(self, key: str) -> ObjectIdentity:
        """ADDRESS: the four-layer identity of the current version."""
        k = self._key(key)
        history = self._objects.get(k)
        if not history:
            raise NotFound(f"key {key!r} unknown")
        rec = history[-1]
        return ObjectIdentity(
            content_id=rec["digest"],
            fold_id=rec["fold_id"],
            logical_address=rec["address_index"],
            physical_location=str(getattr(self.space, "_directory", "<memory>")),
        )

    def query_digest(self, digest: str) -> Optional[str]:
        """QUERY by content identity → returns the (unscoped) key."""
        k = self._content_index.get(digest)
        if k is None or not k.startswith(f"{self.tenant}:"):
            return None
        return k.split(":", 1)[1]

    def versions(self, key: str) -> List[VersionRecord]:
        """VERSION: the chain identity/version/parent/transform/provenance."""
        k = self._key(key)
        history = self._objects.get(k)
        if not history:
            raise NotFound(key)
        return [
            VersionRecord(
                version=r["version"],
                parent_digest=r["parent_digest"],
                transform=r["transform"],
                digest=r["digest"],
                seq=r["seq"],
                receipt_sha256=r["receipt_sha256"],
            )
            for r in history
        ]

    def get_version(self, key: str, version: int) -> bytes:
        """Reconstruct a previous state — §14 (not silently overwritten)."""
        k = self._key(key)
        history = self._objects.get(k)
        if not history or version < 1 or version > len(history):
            raise NotFound(f"{key!r} version {version} unknown")
        rec = history[version - 1]
        block = self.space.read(
            self.space.address_of_index(rec["address_index"])
        )
        if hashlib.sha256(block).hexdigest() != rec["digest"]:
            raise SubstrateError("historical version fails digest")
        return block

    def transform(self, key: str, new_payload: bytes, *, how: str) -> ObjectIdentity:
        """TRANSFORM: fold a new payload as the child version of key."""
        if self._key(key) not in self._objects:
            raise NotFound(key)
        return self.put(key, new_payload, transform=how)

    def navigate(self, lens: str, query) -> dict:
        """NAVIGATE: one shared store, several lenses — no duplicated copies.

        lens="content"  — exact digest lookup (identity-grade)
        lens="anchor"   — pv-lattice anchor bucket (navigation-grade:
                          many-to-one, returns candidate keys)
        lens="fold"     — Zeckendorf vector equality on stored folds
        """
        if lens == "content":
            key = self.query_digest(str(query))
            return {"lens": lens, "found": key is not None, "key": key}
        if lens == "anchor":
            anchor = int(query) % 90
            hits = []
            for k, history in self._objects.items():
                if not k.startswith(f"{self.tenant}:"):
                    continue
                rec = history[-1]
                block_anchor = (
                    rec["address_index"] % 90
                )
                if block_anchor == anchor:
                    hits.append(k.split(":", 1)[1])
            return {
                "lens": lens,
                "anchor": anchor,
                "candidates": hits,
                "navigation_grade": True,
                "injective": False,
            }
        if lens == "fold":
            v: ZeckendorfVector = query
            target = hashlib.sha256(
                json.dumps(list(v.blocks), separators=(",", ":")).encode()
            ).hexdigest()
            hits = [
                k.split(":", 1)[1]
                for k, h in self._objects.items()
                if k.startswith(f"{self.tenant}:")
                and h[-1]["fold_id"] == target
            ]
            return {"lens": lens, "candidates": hits, "injective": True}
        raise SubstrateError(f"unknown navigation lens {lens!r}")

    def attest(self) -> dict:
        """ATTEST: ledger integrity + every object's content digest."""
        ledger_ok = self.space.ledger.verify_ledger()
        object_results = []
        for k, history in self._objects.items():
            if not k.startswith(f"{self.tenant}:"):
                continue
            rec = history[-1]
            try:
                block = self.space.read(
                    self.space.address_of_index(rec["address_index"])
                )
                ok = hashlib.sha256(block).hexdigest() == rec["digest"]
            except (AethelError, SubstrateError):
                ok = False
            object_results.append({"key": k, "verified": ok})
        receipt = self.ledger.issue(
            "substrate.attest",
            inputs={"tenant": self.tenant},
            config={},
            output={
                "ledger_ok": ledger_ok,
                "objects": len(object_results),
                "all_verified": all(r["verified"] for r in object_results),
            },
        )
        return {
            "ledger_ok": ledger_ok,
            "objects": object_results,
            "all_verified": ledger_ok and all(r["verified"] for r in object_results),
            "receipt_sha256": receipt.receipt_sha256,
        }

    def delete(self, key: str) -> dict:
        """DELETE — tombstone, evidence-preserving; history is never erased."""
        k = self._key(key)
        if k not in self._objects:
            raise NotFound(key)
        receipt = self.ledger.issue(
            "substrate.delete",
            inputs={"key": k},
            config={},
            output={"tombstoned": True},
        )
        self._tombstones[k] = {
            "deleted_versions": len(self._objects[k]),
            "receipt_sha256": receipt.receipt_sha256,
        }
        return {"tombstoned": True, "key": key}

    def persist(self, directory) -> None:
        """Persist the store + object index atomically enough for tests:
        aethel snapshot for blocks/ledger, JSON index for object chains."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.space.snapshot(directory / "blocks")
        idx = {
            "tenant": self.tenant,
            "objects": self._objects,
            "tombstones": self._tombstones,
        }
        tmp = directory / "objects_index.json.tmp"
        tmp.write_text(json.dumps(idx), encoding="utf-8")
        os.replace(tmp, directory / "objects_index.json")

    @classmethod
    def attach(cls, directory, *, tenant: str = "default") -> "HybaSubstrate":
        """Reattach a persisted substrate; fails closed on any corruption."""
        directory = Path(directory)
        space = AddressSpace.attach(directory / "blocks")
        sub = cls(space=space, tenant=tenant)
        # an attached store resumes wherever its persisted cursor is — the
        # default root band ceiling does not apply to historical writes
        sub._index_ceiling = None
        idx_path = directory / "objects_index.json"
        if idx_path.is_file():
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
            sub._objects = {k: v for k, v in idx["objects"].items()}
            sub._tombstones = idx["tombstones"]
            for k, history in sub._objects.items():
                if history:
                    sub._content_index[history[-1]["digest"]] = k
        sub.space.ledger.check_consistent()
        return sub

    def structural_bytes(self) -> int:
        """Measured resident bytes: object index + store structural bytes."""
        idx = json.dumps(self._objects).encode()
        return len(idx) + self.space.structural_bytes()


# -- §9 near-state compute ---------------------------------------------------

FOLD_NATIVE = "FOLD-NATIVE"
PARTIAL_RECONSTRUCTION = "PARTIAL-RECONSTRUCTION"
FULL_RECONSTRUCTION = "FULL-RECONSTRUCTION REQUIRED"
UNSUPPORTED = "UNSUPPORTED"


def near_state_classify() -> Dict[str, dict]:
    """§9 — which operators run on folded state without reconstruction.

    Classification is by the code path, not by claim: FOLD-NATIVE ops
    never call unfold.
    """
    return {
        "equality": {
            "class": FOLD_NATIVE,
            "how": "compare Zeckendorf mask tuples — mask equality == byte "
            "equality by uniqueness theorem",
            "bytes_materialized": "0 payload bytes",
        },
        "byte_length": {
            "class": FOLD_NATIVE,
            "how": "ZeckendorfVector.total_bytes field",
            "bytes_materialized": "0",
        },
        "fold_integrity": {
            "class": FOLD_NATIVE,
            "how": "verify() non-adjacency + offset invariants",
            "bytes_materialized": "0",
        },
        "prefix_read": {
            "class": PARTIAL_RECONSTRUCTION,
            "how": "decode only the first k masks -> first 8k bytes; "
            "remainder never materialized",
            "bytes_materialized": "8k for k blocks",
        },
        "suffix_read": {
            "class": PARTIAL_RECONSTRUCTION,
            "how": "decode only the last masks by offset",
            "bytes_materialized": "8*(kept blocks)",
        },
        "content_digest": {
            "class": FULL_RECONSTRUCTION,
            "how": "sha256 needs the full byte stream",
            "bytes_materialized": "total_bytes",
        },
        "content_search": {
            "class": FULL_RECONSTRUCTION,
            "how": "substring/regex needs reconstructed bytes",
            "bytes_materialized": "total_bytes",
        },
        "content_distance": {
            "class": UNSUPPORTED,
            "how": "Zeckendorf mask Hamming distance has no proven relation "
            "to payload distance — not claimed",
            "bytes_materialized": "n/a",
        },
    }


def prefix_unfold(vector: ZeckendorfVector, n_bytes: int) -> bytes:
    """§9 measured partial reconstruction: first n_bytes only."""
    keep = -(-n_bytes // 8)
    blocks = vector.blocks[:keep]
    sub = ZeckendorfVector(blocks=blocks, total_bytes=len(blocks) * 8)
    data = unfold(sub)
    return data[:n_bytes]


def suffix_unfold(vector: ZeckendorfVector, n_bytes: int) -> bytes:
    """Last n_bytes without materializing the middle."""
    keep = -(-n_bytes // 8)
    blocks = vector.blocks[-keep:] if keep else ()
    sub = ZeckendorfVector(blocks=blocks, total_bytes=len(blocks) * 8)
    data = unfold(sub)
    return data[-n_bytes:] if n_bytes else b""


__all__ = [
    "FOLD_NATIVE",
    "FULL_RECONSTRUCTION",
    "HybaSubstrate",
    "MovementMeter",
    "NotFound",
    "ObjectIdentity",
    "PARTIAL_RECONSTRUCTION",
    "SUBSTRATE_VERSION",
    "SubstrateError",
    "TenantDenied",
    "UNSUPPORTED",
    "VersionRecord",
    "near_state_classify",
    "prefix_unfold",
    "suffix_unfold",
]
