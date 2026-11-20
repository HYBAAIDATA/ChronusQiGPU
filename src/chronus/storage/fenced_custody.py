"""Distributed THESEUS custody primitives for 1,000-GPU scale.

Provides:
- FencedReceiptEnvelope: exact-integer, length-prefixed, BLAKE3-chained custody record.
- LocalSingleNodeFencer / EtcdLeaseFencer: monotonic 64-bit fencing token providers.
- Blake3MerkleTree & MerkleInclusionProof: RFC 6962 non-malleable Merkle commitments.
- EpochAnchor, TheseusCustodyStore, & EpochAnchorer: SQLite WAL Tier-1 edge store
  with fail-closed custody watermarks, Gate G2 crash-tail recovery, and Tier-2 quorum anchoring.
"""

from __future__ import annotations

import dataclasses
from contextlib import closing
from enum import Enum
import hmac
import json
import logging
from pathlib import Path
import sqlite3
import struct
import threading
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Sequence, Tuple

try:
    import blake3 as _blake3  # type: ignore[import-not-found]
except ImportError:
    _blake3 = None


# ---------------------------------------------------------------------------
# Cryptographic constants & domain separation tags
# ---------------------------------------------------------------------------
DIGEST_LEN = 32
GENESIS_HASH = b"\x00" * DIGEST_LEN

DOMAIN_PAYLOAD = b"CHRONUS:THESEUS:PAYLOAD:v1"
DOMAIN_CHAIN_RECORD = b"CHRONUS:THESEUS:CHAIN:v1"
DOMAIN_MERKLE_LEAF = b"CHRONUS:THESEUS:LEAF:v1"
DOMAIN_MERKLE_NODE = b"CHRONUS:THESEUS:NODE:v1"
DOMAIN_EPOCH_ANCHOR = b"CHRONUS:THESEUS:ANCHOR:v1"

logger = logging.getLogger("chronus.theseus.custody")


# ---------------------------------------------------------------------------
# Fail-closed exception hierarchy
# ---------------------------------------------------------------------------
class CustodyError(RuntimeError):
    """Base error for all THESEUS custody invariant violations."""


class CustodyDependencyError(CustodyError):
    """Raised when a required cryptographic or consensus dependency is absent."""


class ChainIntegrityError(CustodyError):
    """Raised when hash-chain linkage or record digest verification fails."""


class StaleFencingEpochError(CustodyError):
    """Raised when a write or anchor presents a fencing epoch below the fence floor."""


class LeaseLostError(CustodyError):
    """Raised when the host fencing lease has expired or lost safety margin."""


class CustodyHaltError(CustodyError):
    """Raised when unanchored backlog exceeds the hard custody watermark."""


class QuorumUnavailableError(CustodyError):
    """A quorum read failed before an anchoring write was attempted."""


class AnchorCommitUncertainError(CustodyError):
    """A quorum write may have succeeded without a usable acknowledgement."""


class CustodyHealth(Enum):
    HEALTHY = "HEALTHY"
    UNANCHORED_WARN = "UNANCHORED_WARN"
    CUSTODY_HALT = "CUSTODY_HALT"


# ---------------------------------------------------------------------------
# Exact binary framing & BLAKE3 helpers
# ---------------------------------------------------------------------------
def _require_blake3():
    if _blake3 is None:
        raise CustodyDependencyError(
            "The 'blake3' package is required for THESEUS custody; "
            "silent fallback to another hash algorithm is forbidden."
        )
    return _blake3


def _lp(data: bytes) -> bytes:
    """Length-prefix bytes with big-endian uint32 to prevent boundary collisions."""
    if len(data) > 0xFFFFFFFF:
        raise ValueError("Field exceeds uint32 framing limit")
    return struct.pack(">I", len(data)) + data


def _u64(value: int, name: str) -> bytes:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer, got {type(value).__name__}")
    if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"{name} must be an unsigned 64-bit integer, got {value!r}")
    return struct.pack(">Q", value)


def _reject_floats(obj: Any, path: str = "$") -> None:
    """Reject IEEE-754 floats inside custody payloads to enforce exact arithmetic."""
    if isinstance(obj, float):
        raise TypeError(
            f"Floating-point value forbidden in custody payload at {path}: {obj!r}. "
            "Use exact integers (e.g., nanoseconds, micro-units) or canonical strings."
        )
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"Custody payload dict keys must be str at {path}, got {type(k).__name__}")
            _reject_floats(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            _reject_floats(item, f"{path}[{idx}]")


def canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    """Produce deterministic canonical JSON bytes for an exact-arithmetic payload."""
    if type(payload) is not dict:
        raise TypeError("Custody payload must be an object")
    _reject_floats(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def blake3_digest(domain: bytes, *parts: bytes) -> bytes:
    b3 = _require_blake3()
    h = b3.blake3()
    h.update(_lp(domain))
    for part in parts:
        h.update(part)
    return h.digest(length=DIGEST_LEN)


def hash_payload(payload: Dict[str, Any]) -> Tuple[bytes, bytes]:
    raw = canonical_payload_bytes(payload)
    return raw, blake3_digest(DOMAIN_PAYLOAD, _lp(raw))


# ---------------------------------------------------------------------------
# 1. FencedReceiptEnvelope
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True, slots=True)
class FencedReceiptEnvelope:
    """Immutable custody record with a fencing epoch in a BLAKE3 hash chain."""

    node_id: str
    slot_id: str
    tenant_id: str
    fencing_epoch: int
    seq: int
    ts_ns: int
    event_type: str
    payload_digest: bytes
    prev_hash: bytes
    record_hash: bytes

    def __post_init__(self) -> None:
        for field_name in ("node_id", "slot_id", "tenant_id", "event_type"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val or not val.isascii():
                raise ValueError(f"{field_name} must be a non-empty ASCII string")
        for name in ("fencing_epoch", "seq", "ts_ns"):
            _u64(getattr(self, name), name)
        if self.fencing_epoch <= 0:
            raise ValueError(f"fencing_epoch must be >= 1, got {self.fencing_epoch!r}")
        if self.seq <= 0:
            raise ValueError(f"seq must be >= 1, got {self.seq!r}")
        if self.ts_ns < 0:
            raise ValueError(f"ts_ns must be >= 0, got {self.ts_ns!r}")
        for digest_name in ("payload_digest", "prev_hash", "record_hash"):
            d = getattr(self, digest_name)
            if not isinstance(d, bytes) or len(d) != DIGEST_LEN:
                raise ValueError(f"{digest_name} must be exactly {DIGEST_LEN} bytes")

    @staticmethod
    def compute_hash(
        *,
        node_id: str,
        slot_id: str,
        tenant_id: str,
        fencing_epoch: int,
        seq: int,
        ts_ns: int,
        event_type: str,
        payload_digest: bytes,
        prev_hash: bytes,
    ) -> bytes:
        if len(payload_digest) != DIGEST_LEN or len(prev_hash) != DIGEST_LEN:
            raise ValueError("Digests must be 32 bytes")
        return blake3_digest(
            DOMAIN_CHAIN_RECORD,
            prev_hash,
            _lp(node_id.encode("ascii")),
            _lp(slot_id.encode("ascii")),
            _lp(tenant_id.encode("ascii")),
            _u64(fencing_epoch, "fencing_epoch"),
            _u64(seq, "seq"),
            _u64(ts_ns, "ts_ns"),
            _lp(event_type.encode("ascii")),
            payload_digest,
        )

    @classmethod
    def create(
        cls,
        *,
        node_id: str,
        slot_id: str,
        tenant_id: str,
        fencing_epoch: int,
        seq: int,
        ts_ns: int,
        event_type: str,
        payload: Dict[str, Any],
        prev_hash: bytes,
    ) -> Tuple["FencedReceiptEnvelope", bytes]:
        canonical_bytes, payload_digest = hash_payload(payload)
        record_hash = cls.compute_hash(
            node_id=node_id,
            slot_id=slot_id,
            tenant_id=tenant_id,
            fencing_epoch=fencing_epoch,
            seq=seq,
            ts_ns=ts_ns,
            event_type=event_type,
            payload_digest=payload_digest,
            prev_hash=prev_hash,
        )
        envelope = cls(
            node_id=node_id,
            slot_id=slot_id,
            tenant_id=tenant_id,
            fencing_epoch=fencing_epoch,
            seq=seq,
            ts_ns=ts_ns,
            event_type=event_type,
            payload_digest=payload_digest,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )
        return envelope, canonical_bytes

    def canonical_leaf_bytes(self) -> bytes:
        """Deterministic binary serialization committed as a Merkle tree leaf."""
        return b"".join(
            (
                _lp(self.node_id.encode("ascii")),
                _lp(self.slot_id.encode("ascii")),
                _lp(self.tenant_id.encode("ascii")),
                _u64(self.fencing_epoch, "fencing_epoch"),
                _u64(self.seq, "seq"),
                _u64(self.ts_ns, "ts_ns"),
                _lp(self.event_type.encode("ascii")),
                self.payload_digest,
                self.prev_hash,
                self.record_hash,
            )
        )

    def verify_link(self, expected_prev_hash: bytes, expected_seq: Optional[int] = None) -> None:
        if expected_seq is not None and self.seq != expected_seq:
            raise ChainIntegrityError(f"Sequence gap: expected {expected_seq}, got {self.seq}")
        if not hmac.compare_digest(self.prev_hash, expected_prev_hash):
            raise ChainIntegrityError(
                f"Broken hash chain at seq={self.seq}: "
                f"expected prev={expected_prev_hash.hex()}, got {self.prev_hash.hex()}"
            )
        recomputed = self.compute_hash(
            node_id=self.node_id,
            slot_id=self.slot_id,
            tenant_id=self.tenant_id,
            fencing_epoch=self.fencing_epoch,
            seq=self.seq,
            ts_ns=self.ts_ns,
            event_type=self.event_type,
            payload_digest=self.payload_digest,
            prev_hash=self.prev_hash,
        )
        if not hmac.compare_digest(self.record_hash, recomputed):
            raise ChainIntegrityError(
                f"Corrupted record_hash at seq={self.seq}: "
                f"expected {recomputed.hex()}, got {self.record_hash.hex()}"
            )


# ---------------------------------------------------------------------------
# 2. Fencing Providers: LocalSingleNodeFencer & EtcdLeaseFencer
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True, slots=True)
class FencingToken:
    slot_key: str
    node_id: str
    epoch: int
    lease_id: int
    ttl_s: int
    acquired_monotonic_ns: int


class FencingProvider(Protocol):
    def acquire(self) -> FencingToken: ...
    def current_valid_token(self) -> FencingToken: ...
    def release(self) -> None: ...


class LocalSingleNodeFencer:
    """Single-host SQLite-backed monotonic fencer for CI and single-node deployments."""

    def __init__(self, db_path: Path, node_id: str, slot_id: str) -> None:
        self._db_path = Path(db_path)
        self._node_id = node_id
        self._slot_key = slot_id
        self._lock = threading.Lock()
        self._token: Optional[FencingToken] = None
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), isolation_level=None, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_table(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS theseus_local_fences (
                    slot_key TEXT PRIMARY KEY,
                    epoch INTEGER NOT NULL
                );
                """
            )

    def acquire(self) -> FencingToken:
        with self._lock, closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                row = conn.execute(
                    "SELECT epoch FROM theseus_local_fences WHERE slot_key = ?;",
                    (self._slot_key,),
                ).fetchone()
                if row is not None and (type(row[0]) is not int or row[0] < 1):
                    raise ChainIntegrityError("Invalid persisted local fencing epoch")
                next_epoch = 1 if row is None else row[0] + 1
                if next_epoch > 0x7FFFFFFFFFFFFFFF:
                    raise CustodyError("Local fencing epoch exhausted")
                conn.execute(
                    """
                    INSERT INTO theseus_local_fences(slot_key, epoch)
                    VALUES (?, ?)
                    ON CONFLICT(slot_key) DO UPDATE SET epoch = excluded.epoch;
                    """,
                    (self._slot_key, next_epoch),
                )
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            self._token = FencingToken(
                slot_key=self._slot_key,
                node_id=self._node_id,
                epoch=next_epoch,
                lease_id=0,
                ttl_s=0,
                acquired_monotonic_ns=time.monotonic_ns(),
            )
            return self._token

    def current_valid_token(self) -> FencingToken:
        with self._lock:
            if self._token is None:
                raise LeaseLostError("LocalSingleNodeFencer has not acquired an epoch")
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT epoch FROM theseus_local_fences WHERE slot_key = ?",
                    (self._slot_key,),
                ).fetchone()
            if row is None or row[0] != self._token.epoch:
                raise StaleFencingEpochError("Local fence has been superseded")
            return self._token

    def release(self) -> None:
        with self._lock:
            self._token = None


class EtcdClientProtocol(Protocol):
    """Minimal etcd v3 client surface (compatible with etcd3 or custom gRPC wrapper)."""

    def lease(self, ttl: int) -> Any: ...
    def get(self, key: str) -> Tuple[Any, Any]: ...
    def transaction(self, compare: Sequence[Any], success: Sequence[Any], failure: Sequence[Any]) -> Tuple[bool, Sequence[Any]]: ...
    @property
    def transactions(self) -> Any: ...


class EtcdLeaseFencer:
    """Distributed etcd v3 lease-backed fencer with Kleppmann safety-margin enforcement.

    The fencing epoch is the etcd key's ModRevision produced atomically by a CAS
    transaction (create_revision == 0). Because Raft revisions are globally strictly
    monotonic across cluster lifetime, zombie hosts cannot reuse or forge an epoch.
    """

    def __init__(
        self,
        *,
        etcd_client: EtcdClientProtocol,
        node_id: str,
        slot_id: str,
        key_prefix: str = "/chronus/theseus/fences",
        ttl_s: int = 12,
        safety_margin_s: int = 3,
        on_lease_lost: Optional[Callable[[str], None]] = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if type(ttl_s) is not int or type(safety_margin_s) is not int:
            raise TypeError("Lease durations must be integer seconds")
        for identifier in (node_id, slot_id):
            if not identifier or not identifier.isascii() or "/" in identifier or any(ord(c) < 33 for c in identifier):
                raise ValueError("Invalid etcd fence identity")
        if ttl_s < 4:
            raise ValueError("ttl_s must be >= 4 seconds")
        if safety_margin_s <= 0 or safety_margin_s >= ttl_s:
            raise ValueError("safety_margin_s must satisfy 0 < safety_margin_s < ttl_s")

        self._etcd = etcd_client
        self._node_id = node_id
        self._slot_id = slot_id
        self._slot_key = f"{key_prefix.rstrip('/')}/{slot_id}"
        self._ttl_s = ttl_s
        self._safety_margin_ns = safety_margin_s * 1_000_000_000
        self._refresh_interval_s = max(1, (ttl_s - safety_margin_s) // 3)
        self._on_lease_lost = on_lease_lost
        self._clock_ns = clock_ns

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._lease_healthy = threading.Event()
        self._lease_obj: Any = None
        self._token: Optional[FencingToken] = None
        self._lease_deadline_ns: int = 0
        self._keepalive_thread: Optional[threading.Thread] = None

    @property
    def slot_key(self) -> str:
        return self._slot_key

    def acquire(self) -> FencingToken:
        with self._lock:
            if self._token is not None or self._keepalive_thread is not None:
                raise CustodyError(f"Slot {self._slot_key} must release its previous lease before acquiring")

            before_ns = self._clock_ns()
            lease = self._etcd.lease(self._ttl_s)
            tx = self._etcd.transactions
            succeeded, responses = self._etcd.transaction(
                compare=[tx.create(self._slot_key) == 0],
                success=[tx.put(self._slot_key, self._node_id, lease=lease)],
                failure=[tx.get(self._slot_key)],
            )
            if not succeeded:
                try:
                    lease.revoke()
                except Exception:
                    logger.warning("Failed to revoke unused lease after CAS contention", exc_info=True)
                raise StaleFencingEpochError(
                    f"Slot {self._slot_key} is currently fenced by another active holder"
                )

            # Extract strictly monotonic Raft revision from PutResponse header.
            revision = self._extract_revision(responses)
            if revision <= 0:
                lease.revoke()
                raise CustodyError(f"etcd returned invalid ModRevision: {revision!r}")

            if type(lease.id) is not int or lease.id == 0:
                lease.revoke()
                raise CustodyError("Invalid etcd lease identity")
            token = FencingToken(
                slot_key=self._slot_key,
                node_id=self._node_id,
                epoch=revision,
                lease_id=lease.id,
                ttl_s=self._ttl_s,
                acquired_monotonic_ns=before_ns,
            )
            if self._clock_ns() >= before_ns + self._ttl_s * 1_000_000_000 - self._safety_margin_ns:
                lease.revoke()
                raise LeaseLostError("Lease grant consumed its safety margin")
            self._lease_obj = lease
            self._token = token
            # Bound expiry strictly from pre-RPC clock so RPC latency never eats the safety margin.
            self._lease_deadline_ns = before_ns + (self._ttl_s * 1_000_000_000)
            self._stop_event.clear()
            self._lease_healthy.set()

            self._keepalive_thread = threading.Thread(
                target=self._keepalive_loop,
                name=f"theseus-fence-{self._slot_id}",
                daemon=True,
            )
            self._keepalive_thread.start()
            return token

    @staticmethod
    def _extract_revision(responses: Sequence[Any]) -> int:
        if not responses:
            return 0
        resp = responses[0]
        if hasattr(resp, "header") and hasattr(resp.header, "revision"):
            revision = resp.header.revision
        elif hasattr(resp, "response_put") and hasattr(resp.response_put, "header"):
            revision = resp.response_put.header.revision
        else:
            raise CustodyError(f"Cannot extract Raft revision from etcd response: {type(resp).__name__}")
        if type(revision) is not int or not 1 <= revision <= 0x7FFFFFFFFFFFFFFF:
            raise CustodyError("Invalid Raft revision")
        return revision

    def _keepalive_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._refresh_interval_s):
            with self._lock:
                lease = self._lease_obj
                if lease is None or not self._lease_healthy.is_set():
                    return
            try:
                before_ns = self._clock_ns()
                # refresh() yields LeaseKeepAliveResponse in python-etcd3; consume one tick.
                refreshed = lease.refresh()
                resp = next(iter(refreshed)) if not hasattr(refreshed, "TTL") else refreshed
                granted_ttl = getattr(resp, "TTL", 0)
                if type(granted_ttl) is not int or granted_ttl <= 0:
                    raise LeaseLostError("etcd keepalive returned TTL <= 0 (lease expired)")
                with self._lock:
                    if self._stop_event.is_set() or not self._lease_healthy.is_set():
                        return
                    if self._clock_ns() >= self._lease_deadline_ns - self._safety_margin_ns:
                        raise LeaseLostError("Keepalive crossed existing safety cutoff")
                    renewed_deadline_ns = before_ns + (granted_ttl * 1_000_000_000)
                    if self._clock_ns() >= renewed_deadline_ns - self._safety_margin_ns:
                        raise LeaseLostError("Renewed lease has insufficient safety margin")
                    self._lease_deadline_ns = renewed_deadline_ns
            except Exception as exc:
                self._fail_lease(f"etcd keepalive failed for {self._slot_key}: {exc}")
                return

    def _fail_lease(self, reason: str) -> None:
        with self._lock:
            if not self._lease_healthy.is_set():
                return
            self._lease_healthy.clear()
            self._stop_event.set()
        logger.error("THESEUS FENCE LOST: %s", reason)
        if self._on_lease_lost is not None:
            self._on_lease_lost(reason)

    def current_valid_token(self) -> FencingToken:
        with self._lock:
            if self._token is None or not self._lease_healthy.is_set():
                raise LeaseLostError(f"No healthy fencing lease for {self._slot_key}")
            if self._clock_ns() < self._lease_deadline_ns - self._safety_margin_ns:
                return self._token
        self._fail_lease(f"Lease safety margin breached for {self._slot_key}")
        raise LeaseLostError(f"Lease safety margin breached for {self._slot_key}")

    def release(self) -> None:
        with self._lock:
            self._stop_event.set()
            self._lease_healthy.clear()
            lease = self._lease_obj
            thread = self._keepalive_thread
        if thread is threading.current_thread():
            raise CustodyError("Lease keepalive cannot release itself")
        if thread is not None:
            thread.join(timeout=2)
            if thread.is_alive():
                raise CustodyError("Lease keepalive did not terminate; reacquisition forbidden")
        if lease is not None:
            lease.revoke()
        with self._lock:
            self._lease_obj = None
            self._token = None
            self._keepalive_thread = None


# ---------------------------------------------------------------------------
# 3. Non-Malleable RFC 6962 BLAKE3 Merkle Tree & Inclusion Proofs
# ---------------------------------------------------------------------------
Side = Literal["L", "R"]


def merkle_leaf_hash(leaf_bytes: bytes) -> bytes:
    return blake3_digest(DOMAIN_MERKLE_LEAF, b"\x00", _lp(leaf_bytes))


def merkle_node_hash(left: bytes, right: bytes) -> bytes:
    if len(left) != DIGEST_LEN or len(right) != DIGEST_LEN:
        raise ValueError("Merkle child hashes must be 32 bytes")
    return blake3_digest(DOMAIN_MERKLE_NODE, b"\x01", left, right)


def _largest_power_of_two_less_than(n: int) -> int:
    if n <= 1:
        raise ValueError("n must be > 1")
    return 1 << ((n - 1).bit_length() - 1)


def _expected_proof_sides(leaf_index: int, leaf_count: int) -> List[Side]:
    if (type(leaf_index) is not int or type(leaf_count) is not int
            or not 1 <= leaf_count <= 0xFFFFFFFFFFFFFFFF or not 0 <= leaf_index < leaf_count):
        raise ValueError(f"Invalid leaf_index={leaf_index} for leaf_count={leaf_count}")
    if leaf_count == 1:
        return []
    k = _largest_power_of_two_less_than(leaf_count)
    if leaf_index < k:
        return _expected_proof_sides(leaf_index, k) + ["R"]
    return _expected_proof_sides(leaf_index - k, leaf_count - k) + ["L"]


@dataclasses.dataclass(frozen=True, slots=True)
class MerkleInclusionProof:
    leaf_index: int
    leaf_count: int
    steps: Tuple[Tuple[bytes, Side], ...]

    def verify(self, leaf_bytes: bytes, expected_root: bytes) -> bool:
        if not isinstance(expected_root, bytes) or len(expected_root) != DIGEST_LEN:
            return False
        try:
            expected_sides = _expected_proof_sides(self.leaf_index, self.leaf_count)
        except ValueError:
            return False
        if type(leaf_bytes) is not bytes or type(self.steps) is not tuple or len(self.steps) != len(expected_sides):
            return False

        acc = merkle_leaf_hash(leaf_bytes)
        for step, expected_side in zip(self.steps, expected_sides):
            if type(step) is not tuple or len(step) != 2:
                return False
            sibling_hash, side = step
            if side != expected_side or not isinstance(sibling_hash, bytes) or len(sibling_hash) != DIGEST_LEN:
                return False
            if side == "R":
                acc = merkle_node_hash(acc, sibling_hash)
            else:
                acc = merkle_node_hash(sibling_hash, acc)
        return hmac.compare_digest(acc, expected_root)


class Blake3MerkleTree:
    """RFC 6962 binary BLAKE3 Merkle tree with O(K) build and O(log K) proofs."""

    def __init__(self, leaves: Sequence[bytes]) -> None:
        if not leaves:
            raise ValueError("Cannot build Blake3MerkleTree over an empty batch")
        self._leaf_hashes: Tuple[bytes, ...] = tuple(merkle_leaf_hash(item) for item in leaves)
        self._cache: Dict[Tuple[int, int], bytes] = {}
        self._root: bytes = self._mth(0, len(self._leaf_hashes))

    @property
    def leaf_count(self) -> int:
        return len(self._leaf_hashes)

    @property
    def root(self) -> bytes:
        return self._root

    def _mth(self, start: int, end: int) -> bytes:
        n = end - start
        if n == 1:
            return self._leaf_hashes[start]
        key = (start, end)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        k = _largest_power_of_two_less_than(n)
        digest = merkle_node_hash(self._mth(start, start + k), self._mth(start + k, end))
        self._cache[key] = digest
        return digest

    def proof_for(self, leaf_index: int) -> MerkleInclusionProof:
        n = self.leaf_count
        if type(leaf_index) is not int or leaf_index < 0 or leaf_index >= n:
            raise IndexError(f"leaf_index {leaf_index} out of range [0, {n})")
        steps = tuple(self._audit_path(leaf_index, 0, n))
        return MerkleInclusionProof(leaf_index=leaf_index, leaf_count=n, steps=steps)

    def _audit_path(self, m: int, start: int, end: int) -> List[Tuple[bytes, Side]]:
        n = end - start
        if n == 1:
            return []
        k = _largest_power_of_two_less_than(n)
        if m < k:
            return self._audit_path(m, start, start + k) + [(self._mth(start + k, end), "R")]
        return self._audit_path(m - k, start + k, end) + [(self._mth(start, start + k), "L")]


# ---------------------------------------------------------------------------
# 4. Signed Epoch Anchors & Tier-2 Quorum Protocol
# ---------------------------------------------------------------------------
AnchorKind = Literal["REGULAR", "RECOVERY_TAIL"]


class EpochSigner(Protocol):
    @property
    def key_id(self) -> str: ...
    @property
    def hardware_backed(self) -> bool: ...
    def sign(self, message: bytes) -> bytes: ...
    def verify(self, message: bytes, signature: bytes) -> bool: ...


@dataclasses.dataclass(frozen=True, slots=True)
class EpochAnchor:
    node_id: str
    slot_id: str
    fencing_epoch: int
    anchor_kind: AnchorKind
    seq_start: int
    seq_end: int
    leaf_count: int
    merkle_root: bytes
    head_record_hash: bytes
    anchored_ts_ns: int
    signer_key_id: str
    hardware_backed: bool
    signature: bytes

    def __post_init__(self) -> None:
        for name in ("fencing_epoch", "seq_start", "seq_end", "leaf_count", "anchored_ts_ns"):
            _u64(getattr(self, name), name)
        if (self.fencing_epoch < 1 or self.seq_start < 1
                or self.seq_end < self.seq_start or self.leaf_count != self.seq_end - self.seq_start + 1):
            raise ValueError("Invalid epoch range or fencing epoch")
        if self.anchor_kind not in ("REGULAR", "RECOVERY_TAIL") or type(self.hardware_backed) is not bool:
            raise ValueError("Invalid epoch metadata")
        for identifier in (self.node_id, self.slot_id, self.signer_key_id):
            if not isinstance(identifier, str) or not identifier or not identifier.isascii() or "/" in identifier:
                raise ValueError("Invalid anchor identity")
        for digest in (self.merkle_root, self.head_record_hash):
            if type(digest) is not bytes or len(digest) != DIGEST_LEN:
                raise ValueError("Invalid anchor digest")
        if type(self.signature) is not bytes:
            raise TypeError("Invalid signature type")

    def signing_preimage(self) -> bytes:
        return blake3_digest(
            DOMAIN_EPOCH_ANCHOR,
            _lp(self.node_id.encode("ascii")),
            _lp(self.slot_id.encode("ascii")),
            _u64(self.fencing_epoch, "fencing_epoch"),
            _lp(self.anchor_kind.encode("ascii")),
            _u64(self.seq_start, "seq_start"),
            _u64(self.seq_end, "seq_end"),
            _u64(self.leaf_count, "leaf_count"),
            self.merkle_root,
            self.head_record_hash,
            _u64(self.anchored_ts_ns, "anchored_ts_ns"),
            _lp(self.signer_key_id.encode("ascii")),
            b"\x01" if self.hardware_backed else b"\x00",
        )


class AnchorQuorumClient(Protocol):
    def commit_anchor(self, anchor: EpochAnchor) -> int:
        """Atomically commit anchor if fencing_epoch is current; return quorum revision."""
        ...

    def last_anchored_seq(self, node_id: str, slot_id: str) -> int: ...
    def read_anchor(self, node_id: str, slot_id: str, seq_end: int) -> Tuple[EpochAnchor, int]: ...


class EtcdAnchorQuorumClient:
    """Tier-2 etcd Raft anchor committer that rejects stale fencing epochs atomically."""

    def __init__(
        self,
        etcd_client: EtcdClientProtocol,
        fence_prefix: str = "/chronus/theseus/fences",
        anchor_prefix: str = "/chronus/theseus/anchors",
        *, verify_anchor: Callable[[EpochAnchor], bool],
    ) -> None:
        self._etcd = etcd_client
        self._fence_prefix = fence_prefix.rstrip("/")
        self._anchor_prefix = anchor_prefix.rstrip("/")
        self._verify_anchor = verify_anchor

    def _fence_key(self, slot_id: str) -> str:
        return f"{self._fence_prefix}/{slot_id}"

    def _anchor_head_key(self, node_id: str, slot_id: str) -> str:
        return f"{self._anchor_prefix}/{node_id}/{slot_id}/head"

    def _anchor_log_key(self, node_id: str, slot_id: str, seq_end: int) -> str:
        return f"{self._anchor_prefix}/{node_id}/{slot_id}/epochs/{seq_end:020d}"

    def _read(self, key: str):
        try:
            return self._etcd.get(key)
        except (ConnectionError, TimeoutError) as exc:
            raise QuorumUnavailableError("Quorum read unavailable before write") from exc

    @staticmethod
    def _decode_head(value: bytes | None) -> int:
        if value is None:
            return 0
        if type(value) is not bytes or not value.isdigit() or len(value) > 19:
            raise ChainIntegrityError("Invalid quorum anchor watermark")
        seq = int(value)
        if not 1 <= seq <= 0x7FFFFFFFFFFFFFFF or str(seq).encode("ascii") != value:
            raise ChainIntegrityError("Noncanonical quorum anchor watermark")
        return seq

    def commit_anchor(self, anchor: EpochAnchor) -> int:
        if not anchor.signature or not self._verify_anchor(anchor):
            raise ChainIntegrityError("Anchor signature or signer authority refused")
        fence_key = self._fence_key(anchor.slot_id)
        head_key = self._anchor_head_key(anchor.node_id, anchor.slot_id)
        log_key = self._anchor_log_key(anchor.node_id, anchor.slot_id, anchor.seq_end)

        serialized = json.dumps(
            {
                "node_id": anchor.node_id,
                "slot_id": anchor.slot_id,
                "fencing_epoch": anchor.fencing_epoch,
                "anchor_kind": anchor.anchor_kind,
                "seq_start": anchor.seq_start,
                "seq_end": anchor.seq_end,
                "leaf_count": anchor.leaf_count,
                "merkle_root": anchor.merkle_root.hex(),
                "head_record_hash": anchor.head_record_hash.hex(),
                "anchored_ts_ns": anchor.anchored_ts_ns,
                "signer_key_id": anchor.signer_key_id,
                "hardware_backed": anchor.hardware_backed,
                "signature": anchor.signature.hex(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        tx = self._etcd.transactions
        head, head_meta = self._read(head_key)
        last_seq = self._decode_head(head)
        if last_seq >= anchor.seq_end:
            stored, rev = self.read_anchor(anchor.node_id, anchor.slot_id, anchor.seq_end)
            if stored != anchor:
                raise ChainIntegrityError("Conflicting previously committed anchor")
            ok, _ = self._etcd.transaction(
                compare=[tx.mod(fence_key) == anchor.fencing_epoch,
                         tx.value(fence_key) == anchor.node_id.encode("ascii")],
                success=[], failure=[])
            if not ok:
                raise StaleFencingEpochError("Replayed anchor under a stale fence")
            return rev
        if last_seq != anchor.seq_start - 1:
            raise ChainIntegrityError("Quorum anchor would create a sequence gap")
        # Atomic CAS: commit ONLY if this node STILL holds the exact ModRevision fence.
        try:
            succeeded, responses = self._etcd.transaction(
                compare=[
                    tx.mod(fence_key) == anchor.fencing_epoch,
                    tx.value(fence_key) == anchor.node_id.encode("ascii"),
                    tx.mod(head_key) == (0 if head_meta is None else head_meta.mod_revision),
                    tx.create(log_key) == 0,
                ],
                success=[
                    tx.put(log_key, serialized),
                    tx.put(head_key, str(anchor.seq_end)),
                ],
                failure=[],
            )
        except (ConnectionError, TimeoutError) as exc:
            raise AnchorCommitUncertainError("Anchor CAS acknowledgement unavailable; recover before writing") from exc
        if not succeeded:
            raise StaleFencingEpochError(
                f"Quorum rejected anchor for {anchor.node_id}/{anchor.slot_id}: "
                f"fencing_epoch={anchor.fencing_epoch} is no longer the active holder."
            )
        return EtcdLeaseFencer._extract_revision(responses)

    def read_anchor(self, node_id: str, slot_id: str, seq_end: int) -> Tuple[EpochAnchor, int]:
        value, meta = self._read(self._anchor_log_key(node_id, slot_id, seq_end))
        if value is None or meta is None:
            raise ChainIntegrityError("Missing quorum anchor")
        try:
            data = json.loads(value)
            for key in ("merkle_root", "head_record_hash", "signature"):
                data[key] = bytes.fromhex(data[key])
            anchor = EpochAnchor(**data)
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise ChainIntegrityError("Invalid quorum anchor record") from exc
        if (anchor.node_id, anchor.slot_id, anchor.seq_end) != (node_id, slot_id, seq_end):
            raise ChainIntegrityError("Quorum anchor identity mismatch")
        if not anchor.signature or not self._verify_anchor(anchor):
            raise ChainIntegrityError("Quorum anchor signature refused")
        if type(meta.mod_revision) is not int or not 1 <= meta.mod_revision <= 0x7FFFFFFFFFFFFFFF:
            raise ChainIntegrityError("Invalid quorum anchor revision")
        return anchor, meta.mod_revision

    def last_anchored_seq(self, node_id: str, slot_id: str) -> int:
        value, _meta = self._read(self._anchor_head_key(node_id, slot_id))
        return self._decode_head(value)


# ---------------------------------------------------------------------------
# 5. Tier-1 SQLite WAL Store + EpochAnchorer (with Watermarks & Gate G2)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True, slots=True)
class CustodyWatermarks:
    warn_unanchored_s: int = 10
    halt_unanchored_s: int = 30
    warn_unanchored_records: int = 10_000
    halt_unanchored_records: int = 50_000

    def __post_init__(self) -> None:
        for warn, halt in ((self.warn_unanchored_s, self.halt_unanchored_s), (self.warn_unanchored_records, self.halt_unanchored_records)):
            if type(warn) is not int or type(halt) is not int or not 0 < warn < halt:
                raise ValueError("Invalid custody watermarks")


class FencedTheseusEdgeStore:
    """Tier-1 SQLite WAL custody store with fencing enforcement and Merkle epoch anchoring."""

    def __init__(
        self,
        *,
        db_path: Path,
        node_id: str,
        slot_id: str,
        fencer: FencingProvider,
        signer: EpochSigner,
        quorum: AnchorQuorumClient,
        watermarks: CustodyWatermarks = CustodyWatermarks(),
        clock_ns: Callable[[], int] = time.time_ns,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        _require_blake3()
        self._db_path = Path(db_path)
        self._node_id = node_id
        self._slot_id = slot_id
        self._fencer = fencer
        self._signer = signer
        self._quorum = quorum
        self._watermarks = watermarks
        self._clock_ns = clock_ns
        self._monotonic_ns = monotonic_ns

        self._write_lock = threading.RLock()
        self._recovery_complete = False
        self._last_anchor_monotonic_ns = monotonic_ns()
        self._conn = self._open_wal_connection()
        self._init_schema()

    def _open_wal_connection(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            timeout=5.0,
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_schema(self) -> None:
        with self._write_lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS theseus_local_fences (
                    slot_key TEXT PRIMARY KEY,
                    epoch INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS theseus_fenced_receipts (
                    seq INTEGER PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    fencing_epoch INTEGER NOT NULL,
                    ts_ns INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json BLOB NOT NULL,
                    payload_digest BLOB NOT NULL,
                    prev_hash BLOB NOT NULL,
                    record_hash BLOB NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_theseus_tenant_seq
                    ON theseus_fenced_receipts(tenant_id, seq);
                CREATE INDEX IF NOT EXISTS idx_theseus_fencing_epoch
                    ON theseus_fenced_receipts(fencing_epoch);

                CREATE TABLE IF NOT EXISTS theseus_epoch_anchors (
                    seq_end INTEGER PRIMARY KEY,
                    seq_start INTEGER NOT NULL,
                    fencing_epoch INTEGER NOT NULL,
                    anchor_kind TEXT NOT NULL,
                    leaf_count INTEGER NOT NULL,
                    merkle_root BLOB NOT NULL,
                    head_record_hash BLOB NOT NULL,
                    anchored_ts_ns INTEGER NOT NULL,
                    signer_key_id TEXT NOT NULL,
                    hardware_backed INTEGER NOT NULL,
                    signature BLOB NOT NULL,
                    quorum_revision INTEGER NOT NULL
                );
                """
            )

    def _valid_token(self) -> FencingToken:
        token = self._fencer.current_valid_token()
        if type(token.epoch) is not int or not 1 <= token.epoch <= 0x7FFFFFFFFFFFFFFF:
            raise StaleFencingEpochError("Invalid fence epoch")
        if token.node_id != self._node_id or token.slot_key.rsplit("/", 1)[-1] != self._slot_id:
            raise LeaseLostError("Fence does not match custody stream")
        return token

    def assert_write_ready(self) -> None:
        with self._write_lock:
            if not self._recovery_complete:
                raise CustodyError("Must call reconcile_recovery_tail() before dispatch")
            self._valid_token()
            if self.health_status() is CustodyHealth.CUSTODY_HALT:
                raise CustodyHaltError("Custody hard watermark exceeded")

    def close(self) -> None:
        with self._write_lock:
            self._conn.close()

    def _head_state_locked(self) -> Tuple[int, bytes, int]:
        row = self._conn.execute(
            """
            SELECT seq, record_hash, fencing_epoch
            FROM theseus_fenced_receipts
            ORDER BY seq DESC
            LIMIT 1;
            """
        ).fetchone()
        if row is None:
            return 0, GENESIS_HASH, 0
        if (type(row[0]) is not int or type(row[1]) is not bytes
                or len(row[1]) != DIGEST_LEN or type(row[2]) is not int
                or row[0] < 1 or row[2] < 1):
            raise ChainIntegrityError("Invalid stored custody head")
        max_epoch = self._conn.execute("SELECT MAX(fencing_epoch) FROM theseus_fenced_receipts").fetchone()[0]
        if type(max_epoch) is not int or max_epoch != row[2]:
            raise ChainIntegrityError("Nonmonotonic stored custody epoch floor")
        return row[0], row[1], max_epoch

    def _last_local_anchored_seq_locked(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq_end), 0) FROM theseus_epoch_anchors;"
        ).fetchone()
        if type(row[0]) is not int or row[0] < 0:
            raise ChainIntegrityError("Invalid local anchor watermark")
        return row[0]

    def health_status(self) -> CustodyHealth:
        with self._write_lock:
            head_seq, _, _ = self._head_state_locked()
            anchored_seq = self._last_local_anchored_seq_locked()
            backlog = head_seq - anchored_seq
            if backlog < 0:
                raise ChainIntegrityError("Local anchor watermark exceeds receipt head")
            if backlog == 0:
                return CustodyHealth.HEALTHY
            elapsed_s = (self._monotonic_ns() - self._last_anchor_monotonic_ns) // 1_000_000_000
            if (
                elapsed_s >= self._watermarks.halt_unanchored_s
                or backlog >= self._watermarks.halt_unanchored_records
            ):
                return CustodyHealth.CUSTODY_HALT
            if (
                elapsed_s >= self._watermarks.warn_unanchored_s
                or backlog >= self._watermarks.warn_unanchored_records
            ):
                return CustodyHealth.UNANCHORED_WARN
            return CustodyHealth.HEALTHY

    def reconcile_recovery_tail(self) -> Optional[EpochAnchor]:
        """Validate the complete local chain and reconcile signed quorum anchors."""
        with self._write_lock:
            self._recovery_complete = False
            token = self._valid_token()
            if token.node_id != self._node_id:
                raise LeaseLostError("Fence holder does not match custody node")
            rows = self._conn.execute(
                "SELECT seq, node_id, slot_id, tenant_id, fencing_epoch, ts_ns, "
                "event_type, payload_digest, prev_hash, record_hash, payload_json "
                "FROM theseus_fenced_receipts ORDER BY seq"
            ).fetchall()
            envelopes = [self._row_to_envelope(row) for row in rows]
            prev = GENESIS_HASH
            epoch = 0
            for seq, env in enumerate(envelopes, 1):
                if (env.node_id, env.slot_id) != (self._node_id, self._slot_id):
                    raise ChainIntegrityError("Receipt belongs to a different edge stream")
                if not epoch <= env.fencing_epoch <= token.epoch:
                    raise StaleFencingEpochError("Non-monotonic or future epoch in receipt chain")
                env.verify_link(prev, seq)
                prev, epoch = env.record_hash, env.fencing_epoch
            remote = self._quorum.last_anchored_seq(self._node_id, self._slot_id)
            local = self._last_local_anchored_seq_locked()
            if local > remote or remote > len(rows):
                raise ChainIntegrityError("Local/quorum anchor watermark mismatch")
            # Walk immutable quorum anchors backwards; rehydrate only authenticated
            # anchors whose commitments match the complete local records.
            pending = []
            end = remote
            while end:
                anchor, rev = self._quorum.read_anchor(self._node_id, self._slot_id, end)
                part = envelopes[anchor.seq_start - 1:anchor.seq_end]
                if (len(part) != anchor.leaf_count or not part
                        or part[-1].record_hash != anchor.head_record_hash
                        or Blake3MerkleTree([env.canonical_leaf_bytes() for env in part]).root != anchor.merkle_root):
                    raise ChainIntegrityError("Quorum anchor does not match verified local chain")
                pending.append((anchor, rev))
                end = anchor.seq_start - 1
            for anchor, rev in reversed(pending):
                found = self._conn.execute(
                    "SELECT seq_start, fencing_epoch, anchor_kind, leaf_count, merkle_root, "
                    "head_record_hash, anchored_ts_ns, signer_key_id, hardware_backed, signature, quorum_revision "
                    "FROM theseus_epoch_anchors WHERE seq_end = ?", (anchor.seq_end,)
                ).fetchone()
                expected = (anchor.seq_start, anchor.fencing_epoch, anchor.anchor_kind,
                            anchor.leaf_count, anchor.merkle_root, anchor.head_record_hash,
                            anchor.anchored_ts_ns, anchor.signer_key_id, int(anchor.hardware_backed),
                            anchor.signature, rev)
                if found is not None and tuple(found) != expected:
                    raise ChainIntegrityError("Local anchor differs from quorum anchor")
                if found is None:
                    self._persist_anchor_locked(anchor, rev)
            local_count = self._conn.execute("SELECT COUNT(*) FROM theseus_epoch_anchors").fetchone()[0]
            if local_count != len(pending):
                raise ChainIntegrityError("Unrecognised local anchor rows")
            anchor = None
            if remote < len(rows):
                anchor = self._seal_range_locked(
                    rows=rows[remote:], fencing_epoch=token.epoch, anchor_kind="RECOVERY_TAIL")
            self._valid_token()
            self._recovery_complete = True
            self._last_anchor_monotonic_ns = self._monotonic_ns()
            return anchor

    def append_receipt(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> FencedReceiptEnvelope:
        """Append a fenced, hash-chained receipt to local SQLite WAL (fail-closed)."""
        with self._write_lock:
            if not self._recovery_complete:
                raise CustodyError("Must call reconcile_recovery_tail() before accepting new writes")

            if self.health_status() is CustodyHealth.CUSTODY_HALT:
                raise CustodyHaltError(
                    "Unanchored custody backlog exceeded hard watermark; compute dispatch halted."
                )

            token = self._valid_token()
            if token.node_id != self._node_id:
                raise LeaseLostError("Fence holder does not match custody node")
            head_seq, prev_hash, max_seen_epoch = self._head_state_locked()
            if token.epoch < max_seen_epoch:
                raise StaleFencingEpochError(
                    f"Refusing write under stale epoch {token.epoch} < local max {max_seen_epoch}"
                )

            envelope, canonical_json = FencedReceiptEnvelope.create(
                node_id=self._node_id,
                slot_id=self._slot_id,
                tenant_id=tenant_id,
                fencing_epoch=token.epoch,
                seq=head_seq + 1,
                ts_ns=self._clock_ns(),
                event_type=event_type,
                payload=payload,
                prev_hash=prev_hash,
            )

            self._conn.execute("BEGIN IMMEDIATE;")
            try:
                # Cross-process contenders cannot append from a stale head.
                if self._head_state_locked() != (head_seq, prev_hash, max_seen_epoch):
                    raise StaleFencingEpochError("Concurrent edge writer changed head; recover before retry")
                if self._valid_token() != token:
                    raise LeaseLostError("Fence changed before receipt write")
                self._conn.execute(
                    """
                    INSERT INTO theseus_fenced_receipts (
                        seq, node_id, slot_id, tenant_id, fencing_epoch, ts_ns,
                        event_type, payload_json, payload_digest, prev_hash, record_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        envelope.seq,
                        envelope.node_id,
                        envelope.slot_id,
                        envelope.tenant_id,
                        envelope.fencing_epoch,
                        envelope.ts_ns,
                        envelope.event_type,
                        canonical_json,
                        envelope.payload_digest,
                        envelope.prev_hash,
                        envelope.record_hash,
                    ),
                )
                if self._valid_token() != token:
                    raise LeaseLostError("Fence changed before receipt commit")
                self._conn.execute("COMMIT;")
            except Exception:
                self._conn.execute("ROLLBACK;")
                raise
            if head_seq == self._last_local_anchored_seq_locked():
                self._last_anchor_monotonic_ns = self._monotonic_ns()
            return envelope

    def seal_pending_epoch(self, max_batch_size: int = 10_000) -> Optional[EpochAnchor]:
        """Build, sign, and commit a BLAKE3 Merkle epoch anchor for pending WAL rows."""
        if type(max_batch_size) is not int or max_batch_size <= 0:
            raise ValueError("max_batch_size must be a positive integer")
        with self._write_lock:
            if not self._recovery_complete:
                raise CustodyError("Must call reconcile_recovery_tail() before sealing")
            token = self._valid_token()
            last_anchored = self._last_local_anchored_seq_locked()
            rows = self._conn.execute(
                """
                SELECT seq, node_id, slot_id, tenant_id, fencing_epoch, ts_ns,
                       event_type, payload_digest, prev_hash, record_hash, payload_json
                FROM theseus_fenced_receipts
                WHERE seq > ?
                ORDER BY seq ASC
                LIMIT ?;
                """,
                (last_anchored, max_batch_size),
            ).fetchall()
            if not rows:
                self._last_anchor_monotonic_ns = self._monotonic_ns()
                return None

            anchor = self._seal_range_locked(
                rows=rows,
                fencing_epoch=token.epoch,
                anchor_kind="REGULAR",
            )
            if self._head_state_locked()[0] == anchor.seq_end:
                self._last_anchor_monotonic_ns = self._monotonic_ns()
            return anchor

    def inclusion_proof_for_seq(self, seq: int) -> Tuple[FencedReceiptEnvelope, EpochAnchor, MerkleInclusionProof]:
        """Rebuild an anchored batch and return its logarithmic-size inclusion proof."""
        if type(seq) is not int or seq < 1:
            raise TypeError("Receipt sequence must be a positive exact integer")
        with self._write_lock:
            anchor_row = self._conn.execute(
                """
                SELECT seq_start, seq_end, fencing_epoch, anchor_kind, leaf_count,
                       merkle_root, head_record_hash, anchored_ts_ns,
                       signer_key_id, hardware_backed, signature
                FROM theseus_epoch_anchors
                WHERE seq_start <= ? AND seq_end >= ?
                LIMIT 1;
                """,
                (seq, seq),
            ).fetchone()
            if anchor_row is None:
                raise CustodyError(f"Receipt seq={seq} has not been anchored yet")

            expected_types = (int, int, int, str, int, bytes, bytes, int, str, int, bytes)
            if (any(type(value) is not expected for value, expected in zip(anchor_row, expected_types))
                    or anchor_row[9] not in (0, 1)):
                raise ChainIntegrityError("Invalid stored anchor field type")
            seq_start, seq_end = anchor_row[0], anchor_row[1]
            rows = self._conn.execute(
                """
                SELECT seq, node_id, slot_id, tenant_id, fencing_epoch, ts_ns,
                       event_type, payload_digest, prev_hash, record_hash, payload_json
                FROM theseus_fenced_receipts
                WHERE seq BETWEEN ? AND ?
                ORDER BY seq ASC;
                """,
                (seq_start, seq_end),
            ).fetchall()

            envelopes = [self._row_to_envelope(r) for r in rows]
            tree = Blake3MerkleTree([e.canonical_leaf_bytes() for e in envelopes])
            target_idx = seq - seq_start
            proof = tree.proof_for(target_idx)

            anchor = EpochAnchor(
                node_id=self._node_id,
                slot_id=self._slot_id,
                fencing_epoch=anchor_row[2],
                anchor_kind=anchor_row[3],
                seq_start=seq_start,
                seq_end=seq_end,
                leaf_count=anchor_row[4],
                merkle_root=anchor_row[5],
                head_record_hash=anchor_row[6],
                anchored_ts_ns=anchor_row[7],
                signer_key_id=anchor_row[8],
                hardware_backed=bool(anchor_row[9]),
                signature=anchor_row[10],
            )
            remote, _ = self._quorum.read_anchor(self._node_id, self._slot_id, anchor.seq_end)
            if remote != anchor or tree.root != anchor.merkle_root or tree.leaf_count != anchor.leaf_count:
                raise ChainIntegrityError("Inclusion proof does not match authenticated quorum anchor")
            return envelopes[target_idx], anchor, proof

    def _seal_range_locked(
        self,
        *,
        rows: Sequence[Tuple[Any, ...]],
        fencing_epoch: int,
        anchor_kind: AnchorKind,
    ) -> EpochAnchor:
        envelopes = [self._row_to_envelope(r) for r in rows]
        prev_hash = self._hash_at_seq_locked(envelopes[0].seq - 1)
        expected_seq = self._last_local_anchored_seq_locked() + 1
        for env in envelopes:
            if (env.node_id, env.slot_id) != (self._node_id, self._slot_id) or env.fencing_epoch > fencing_epoch:
                raise ChainIntegrityError("Receipt identity or fencing epoch mismatch")
            env.verify_link(expected_prev_hash=prev_hash, expected_seq=expected_seq)
            prev_hash = env.record_hash
            expected_seq += 1

        tree = Blake3MerkleTree([env.canonical_leaf_bytes() for env in envelopes])
        unsigned = EpochAnchor(
            node_id=self._node_id,
            slot_id=self._slot_id,
            fencing_epoch=fencing_epoch,
            anchor_kind=anchor_kind,
            seq_start=envelopes[0].seq,
            seq_end=envelopes[-1].seq,
            leaf_count=tree.leaf_count,
            merkle_root=tree.root,
            head_record_hash=envelopes[-1].record_hash,
            anchored_ts_ns=self._clock_ns(),
            signer_key_id=self._signer.key_id,
            hardware_backed=self._signer.hardware_backed,
            signature=b"",
        )
        sig = self._signer.sign(unsigned.signing_preimage())
        anchor = dataclasses.replace(unsigned, signature=sig)

        # Commit to Tier-2 Raft quorum FIRST; local anchor watermark advances only after quorum ack.
        if not self._signer.verify(anchor.signing_preimage(), anchor.signature):
            raise ChainIntegrityError("Signer returned an invalid signature")
        try:
            quorum_rev = self._quorum.commit_anchor(anchor)
        except QuorumUnavailableError:
            # No write attempted; preserve the unanchored backlog and its age.
            raise
        except Exception:
            # A write may have committed, or the fence may have changed.
            self._recovery_complete = False
            raise
        try:
            self._persist_anchor_locked(anchor, quorum_rev)
        except Exception:
            self._recovery_complete = False
            raise
        return anchor

    def _persist_anchor_locked(self, anchor: EpochAnchor, quorum_rev: int) -> None:
        self._conn.execute("BEGIN IMMEDIATE;")
        try:
            self._conn.execute(
                """
                INSERT INTO theseus_epoch_anchors (
                    seq_end, seq_start, fencing_epoch, anchor_kind, leaf_count,
                    merkle_root, head_record_hash, anchored_ts_ns,
                    signer_key_id, hardware_backed, signature, quorum_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    anchor.seq_end,
                    anchor.seq_start,
                    anchor.fencing_epoch,
                    anchor.anchor_kind,
                    anchor.leaf_count,
                    anchor.merkle_root,
                    anchor.head_record_hash,
                    anchor.anchored_ts_ns,
                    anchor.signer_key_id,
                    1 if anchor.hardware_backed else 0,
                    anchor.signature,
                    quorum_rev,
                ),
            )
            self._conn.execute("COMMIT;")
        except Exception:
            self._conn.execute("ROLLBACK;")
            raise

    def _hash_at_seq_locked(self, seq: int) -> bytes:
        if seq <= 0:
            return GENESIS_HASH
        row = self._conn.execute(
            "SELECT record_hash FROM theseus_fenced_receipts WHERE seq = ?;",
            (seq,),
        ).fetchone()
        if row is None:
            raise ChainIntegrityError(f"Missing baseline record at seq={seq}")
        if type(row[0]) is not bytes or len(row[0]) != DIGEST_LEN:
            raise ChainIntegrityError("Invalid stored baseline digest")
        return row[0]

    @staticmethod
    def _row_to_envelope(row: Tuple[Any, ...]) -> FencedReceiptEnvelope:
        # SQLite uses dynamic typing. Coercing REAL to int or TEXT to str
        # can hide on-disk tampering while recreating the original hash.
        expected_types = (int, str, str, str, int, int, str, bytes, bytes, bytes, bytes)
        if len(row) != len(expected_types) or any(
            type(value) is not expected for value, expected in zip(row, expected_types)
        ):
            raise ChainIntegrityError("Invalid stored custody field type")
        try:
            envelope = FencedReceiptEnvelope(
                seq=row[0],
                node_id=row[1],
                slot_id=row[2],
                tenant_id=row[3],
                fencing_epoch=row[4],
                ts_ns=row[5],
                event_type=row[6],
                payload_digest=row[7],
                prev_hash=row[8],
                record_hash=row[9],
            )
        except (TypeError, ValueError) as exc:
            raise ChainIntegrityError("Invalid stored custody envelope") from exc
        payload = row[10]
        try:
            canonical = canonical_payload_bytes(json.loads(payload))
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ChainIntegrityError("Invalid stored custody payload") from exc
        if canonical != payload or not hmac.compare_digest(
                blake3_digest(DOMAIN_PAYLOAD, _lp(payload)), envelope.payload_digest):
            raise ChainIntegrityError("Stored payload digest mismatch")
        return envelope

class EdgeAnchorSidecar:
    """Explicitly owned custody worker; no network or hardware claims."""
    def __init__(self, store: FencedTheseusEdgeStore, *, on_fault: Callable[[], None],
                 interval_s: int = 1) -> None:
        if type(interval_s) is not int or interval_s < 1:
            raise ValueError("interval_s must be a positive integer")
        self.store = store
        self.on_fault = on_fault
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._fault = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self.error: Optional[Exception] = None

    def start(self) -> None:
        if self._thread is not None:
            raise CustodyError("Sidecar cannot be started twice")
        self.store._fencer.acquire()
        try:
            self.store.reconcile_recovery_tail()
        except BaseException:
            self.store._fencer.release()
            raise
        self._started = True
        self._thread = threading.Thread(target=self._run, name="theseus-anchor", daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._started = False
            self.store._fencer.release()
            raise

    def assert_healthy(self) -> None:
        if self._fault.is_set():
            raise CustodyHaltError("Anchor sidecar fault") from self.error
        self.store.assert_write_ready()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                self.assert_healthy()
                self.store.seal_pending_epoch()
            except QuorumUnavailableError:
                # A pre-write outage is not an acknowledgement. Retry while
                # the independently checked lease and hard watermark permit.
                logger.warning("THESEUS quorum read unavailable; retaining unanchored WAL")
                continue
            except Exception as exc:
                self.error = exc
                self._fault.set()
                logger.exception("THESEUS anchor sidecar halted")
                self.on_fault()
                return

    def stop(self, timeout_s: int = 5) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout_s)
            if self._thread.is_alive():
                raise CustodyHaltError("Anchor sidecar did not stop")
        if not self._started:
            return
        try:
            if self._fault.is_set():
                raise CustodyHaltError("Anchor sidecar failed") from self.error
            self.store.seal_pending_epoch()
        finally:
            self._started = False
            self.store._fencer.release()
