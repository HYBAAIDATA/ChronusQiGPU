"""Defensive v4.3 reference implementation for the supplied middleware.

The entitlement map and SQLite audit store are explicit trust boundaries. The
SQLite store is durable across process restarts but is not a substitute for an
organization's managed, access-controlled audit service (for example OVID).
Call preflight_content_length() at the HTTP boundary before reading or
Deserializing a request body; process_workload() can only validate an ndarray
that already exists in memory.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger("HYBAEnterprise.LucasMiddleware")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def _tensor_digest(tensor: np.ndarray) -> str:
    """Digest tensor values plus dtype/shape, not just ambiguous raw bytes."""
    if not isinstance(tensor, np.ndarray) or tensor.dtype.hasobject:
        raise TypeError("tensor digest requires a numeric NumPy array")
    header = _canonical_json({"dtype": tensor.dtype.str, "shape": list(tensor.shape)})
    h = hashlib.sha256(header.encode("utf-8"))
    h.update(b"\0")
    h.update(np.ascontiguousarray(tensor).tobytes(order="C"))
    return h.hexdigest()


class Functor(Enum):
    F_EXEC = "F_exec"
    F_TENSOR = "F_tensor"
    F_LINEAGE = "F_lineage"


@dataclass(frozen=True)
class Receipt:
    functor: Functor
    statement: str
    method: str
    witness: Dict[str, Any]
    digest: str

    def canonical(self) -> str:
        return _canonical_json({
            "functor": self.functor.value,
            "statement": self.statement,
            "method": self.method,
            "witness": self.witness,
        })

    def recompute_digest(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        try:
            return self.recompute_digest() == self.digest
        except (TypeError, ValueError):
            return False


def make_receipt(functor: Functor, statement: str, method: str,
                 witness: Dict[str, Any]) -> Receipt:
    unsigned = Receipt(functor, statement, method, witness, "")
    return Receipt(functor, statement, method, witness,
                   hashlib.sha256(unsigned.canonical().encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class TierPolicy:
    name: str
    max_recurrence_n: int
    ops_capacity_declared: int
    ops_capacity_window_seconds: float
    precision_class: str
    precision_bound: Optional[float]
    kellogg_cert_required: bool
    description: str


COMMERCIAL_TIERS: Dict[str, TierPolicy] = {
    "free": TierPolicy("Tier 1: Developer / Free", 7, 29_000, 60.0,
                        "Moderate", 2.7e-2, True, "Prototyping & client queries"),
    "pro": TierPolicy("Tier 2: Standard Pro", 18, 100_000, 60.0,
                       "High", 1.6e-4, True, "Standard business logic"),
    "enterprise": TierPolicy("Tier 3: Enterprise Scale", 47, 500_000, 60.0,
                              "Ultra-High", 2.9e-10, True, "Deep reasoning & QAOA"),
    "hyperscale": TierPolicy("Tier 4: Hyperscale Core", 76, 1_000_000, 60.0,
                              "Exact Integer Snap", 0.0, True, "Mission-critical tensor folding"),
    "unbounded": TierPolicy("Tier 5: Infinite Unbounded", 123, 10_000_000, 60.0,
                             "Bit-Exact Unrestricted", 0.0, True, "Dedicated bare-metal clusters"),
}


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    capacity: int
    rate: float
    window: float
    last_seen: float


class TokenBucketLimiter:
    """Bounded, lock-protected token buckets with idle-state expiry."""
    def __init__(self, clock=time.monotonic, max_tenants: int = 100_000):
        if max_tenants < 1:
            raise ValueError("max_tenants must be positive")
        self._lock = threading.RLock()
        self._clock = clock
        self._max_tenants = max_tenants
        self._state: Dict[str, _Bucket] = {}

    def _prune_idle(self, now: float) -> None:
        expired = [tenant for tenant, b in self._state.items()
                   if now - b.last_seen >= b.window]
        for tenant in expired:
            self._state.pop(tenant, None)

    def _refill(self, tenant_id: str, capacity: int,
                window_seconds: float, now: float) -> float:
        rate = capacity / window_seconds
        old = self._state.get(tenant_id)
        if old is None:
            self._prune_idle(now)
            if len(self._state) >= self._max_tenants:
                raise RuntimeError("rate limiter tenant-state capacity reached")
            self._state[tenant_id] = _Bucket(
                float(capacity), now, capacity, rate, window_seconds, now
            )
            return float(capacity)
        elapsed = max(0.0, now - old.last_refill)
        # Accrue using the policy that applied during the elapsed interval.
        tokens = min(float(capacity), old.tokens + old.rate * elapsed)
        old.tokens = tokens
        old.last_refill = now
        old.capacity = capacity
        old.rate = rate
        old.window = window_seconds
        old.last_seen = now
        return tokens

    def try_consume(self, tenant_id: str, ops: int, capacity: int,
                    window_seconds: float) -> Tuple[bool, float]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id must be a non-empty string")
        if type(ops) is not int or ops < 1:
            raise ValueError("ops must be a positive integer")
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError("window_seconds must be finite and positive")
        with self._lock:
            now = self._clock()
            tokens = self._refill(tenant_id, capacity, window_seconds, now)
            if tokens >= ops:
                self._state[tenant_id].tokens = tokens - ops
                return True, self._state[tenant_id].tokens
            return False, tokens

    def peek(self, tenant_id: str, capacity: int, window_seconds: float) -> float:
        with self._lock:
            return self._refill(tenant_id, capacity, window_seconds, self._clock())

    @property
    def tenant_count(self) -> int:
        with self._lock:
            return len(self._state)


class SQLiteAuditStore:
    """Transactional local audit persistence; inject an OVID adapter in prod."""
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("audit store must be persistent; ':memory:' is not supported")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS audit_entries (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_cert TEXT NOT NULL,
                cert TEXT NOT NULL UNIQUE,
                signature_hex TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )""")
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30.0, isolation_level=None)

    def initialize(self, genesis_cert: str) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value FROM metadata WHERE key='genesis_cert'").fetchone()
            if row is None:
                conn.execute("INSERT INTO metadata(key,value) VALUES('genesis_cert',?)", (genesis_cert,))
            elif row[0] != genesis_cert:
                raise ValueError("audit store is initialized for a different signing key")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def head(self, genesis_cert: str) -> str:
        conn = self._connect()
        try:
            row = conn.execute("SELECT cert FROM audit_entries ORDER BY seq DESC LIMIT 1").fetchone()
            return row[0] if row else genesis_cert
        finally:
            conn.close()

    def append(self, parent_cert: str, cert: str, signature_hex: str,
               payload_json: str) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            meta = conn.execute("SELECT value FROM metadata WHERE key='genesis_cert'").fetchone()
            if meta is None:
                raise RuntimeError("audit store has not been initialized")
            row = conn.execute("SELECT cert FROM audit_entries ORDER BY seq DESC LIMIT 1").fetchone()
            current = row[0] if row else meta[0]
            if current != parent_cert:
                raise RuntimeError("certificate-chain head changed; refusing non-linear append")
            conn.execute(
                "INSERT INTO audit_entries(parent_cert,cert,signature_hex,payload_json,created_at) VALUES(?,?,?,?,?)",
                (parent_cert, cert, signature_hex, payload_json, time.time()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def entries(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT parent_cert,cert,signature_hex,payload_json,created_at "
                "FROM audit_entries ORDER BY seq"
            ).fetchall()
        finally:
            conn.close()
        return [{"parent_cert": p, "cert": c, "signature_hex": s,
                 "payload": json.loads(j), "created_at": ts}
                for p, c, s, j, ts in rows]


@dataclass
class ComputeRequest:
    tenant_id: str
    request_id: str
    client_tier: str
    requested_depth: int
    payload_tensor: np.ndarray
    input_provenance: str = "exact_integer"


@dataclass
class ComputeResponse:
    request_id: str
    tenant_id: str
    requested_tier: str
    tier_enforced: str
    requested_n: int
    enforced_n: int
    depth_clamp_receipt: Receipt
    cassini_receipt: Receipt
    processed_tensor: np.ndarray
    output_tensor_digest: str
    fold_bijectivity_receipt: Receipt
    integer_snap_active: bool
    integer_snap_phase: Optional[int]
    integer_snap_is_period_boundary: bool
    m_order: int
    snap_receipt: Receipt
    precision_class_declared: str
    precision_bound_declared: Optional[float]
    kellogg_cert_required: bool
    input_provenance: str
    input_scope_receipt: Receipt
    ops_capacity_declared: int
    ops_capacity_enforced: bool
    rate_limit_receipt: Receipt
    parent_certificate_hash: str
    output_certificate_hash: str = ""
    output_certificate_signature: str = ""
    lineage_receipt: Optional[Receipt] = None
    execution_latency_us: float = 0.0


class ProductionLucasTierMiddleware:
    M_COMPANION = np.array([[1, 1], [1, 0]], dtype=object)
    # The exact order of [[1, 1], [1, 0]] modulo 256 is 384 (not 768).
    M_ORDER = 384
    M15 = np.array([[219, 98], [98, 121]], dtype=np.int64)
    M15_INV = np.array([[135, 98], [98, 37]], dtype=np.int64)
    MODULUS = 256
    SNAP_THRESHOLD = 76

    def __init__(self, signing_key: Ed25519PrivateKey,
                 entitlements: Mapping[str, str],
                 audit_store: SQLiteAuditStore,
                 max_payload_elements: int = 1_000_000,
                 max_payload_bytes: int = 16_000_000,
                 max_limiter_tenants: int = 100_000,
                 in_memory_audit_entries: int = 1_000):
        if signing_key is None:
            raise ValueError("signing_key is required")
        if audit_store is None:
            raise ValueError("a persistent audit_store is required")
        if not isinstance(entitlements, Mapping):
            raise ValueError("entitlements must be a trusted tenant-to-tier mapping")
        if max_payload_elements < 0 or max_payload_bytes < 0:
            raise ValueError("payload limits must be non-negative")
        self._signing_key = signing_key
        self._public_key = signing_key.public_key()
        self._entitlements: Dict[str, str] = {}
        for tenant, tier in entitlements.items():
            if not isinstance(tenant, str) or not tenant.strip():
                raise ValueError("entitlement tenant IDs must be non-empty strings")
            normalized = tier.lower() if isinstance(tier, str) else ""
            if normalized not in COMMERCIAL_TIERS:
                raise ValueError(f"invalid entitlement tier for tenant {tenant!r}")
            self._entitlements[tenant] = normalized
        self.audit_store = audit_store
        self.max_payload_elements = max_payload_elements
        self.max_payload_bytes = max_payload_bytes
        self._rate_limiter = TokenBucketLimiter(max_tenants=max_limiter_tenants)
        self._chain_lock = threading.RLock()
        self.audit_trail = deque(maxlen=max(1, in_memory_audit_entries))
        if not self._assert_M_order(self.M_ORDER):
            raise RuntimeError("configured M_ORDER is not the exact matrix order")
        self._m15_order = self._compute_matrix_order(self.M15)
        self._m15_pow2_order = self._compute_matrix_order((self.M15 @ self.M15) % self.MODULUS)
        payload = f"HYBA-v4.3-genesis:{self._public_key_hex()}"
        self._genesis_cert = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._genesis_sig = self._signing_key.sign(payload.encode("utf-8")).hex()
        self.audit_store.initialize(self._genesis_cert)
        self._prev_cert = self.audit_store.head(self._genesis_cert)

    @classmethod
    def _mat_pow_mod(cls, matrix: np.ndarray, n: int, mod: int) -> np.ndarray:
        result = np.eye(2, dtype=np.int64)
        base = np.asarray(matrix, dtype=np.int64) % mod
        exponent = n
        while exponent:
            if exponent & 1:
                result = (result @ base) % mod
            base = (base @ base) % mod
            exponent >>= 1
        return result

    @classmethod
    def _assert_M_order(cls, claimed: int) -> bool:
        identity = np.eye(2, dtype=np.int64)
        if not np.array_equal(cls._mat_pow_mod(cls.M_COMPANION, claimed, cls.MODULUS), identity):
            return False
        for divisor in range(1, claimed):
            if claimed % divisor == 0 and np.array_equal(
                cls._mat_pow_mod(cls.M_COMPANION, divisor, cls.MODULUS), identity
            ):
                return False
        return True

    def _compute_matrix_order(self, matrix: np.ndarray) -> int:
        identity = np.eye(2, dtype=np.int64)
        current = np.asarray(matrix, dtype=np.int64) % self.MODULUS
        for order in range(1, 1 << 16):
            if np.array_equal(current, identity):
                return order
            current = (current @ matrix) % self.MODULUS
        raise RuntimeError("matrix order not found within search bound")

    @staticmethod
    def _fib_pair(n: int) -> Tuple[int, int]:
        """Return (F_n, F_(n+1)) using fast doubling; n must be nonnegative."""
        if type(n) is not int or n < 0:
            raise ValueError("Fibonacci index must be a non-negative integer")
        if n == 0:
            return 0, 1
        a, b = ProductionLucasTierMiddleware._fib_pair(n >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        return (d, c + d) if n & 1 else (c, d)

    def _cassini_receipt(self, n: int) -> Receipt:
        if n == 0:
            f_nm1, f_n, f_np1 = 1, 0, 1
        else:
            f_nm1, f_n = self._fib_pair(n - 1)
            f_n_check, f_np1 = self._fib_pair(n)
            if f_n_check != f_n:
                raise AssertionError("fast-doubling Fibonacci values disagree")
        det = (f_np1 * f_nm1 - f_n * f_n) % self.MODULUS
        expected = ((-1) ** n) % self.MODULUS
        if det != expected:
            raise ValueError(f"Cassini identity violated at n={n}: {det} != {expected}")
        return make_receipt(Functor.F_EXEC,
            f"F({n+1})*F({n-1}) - F({n})^2 = (-1)^{n} (mod 256)",
            "fast_doubling_fibonacci + modular_eval",
            {"n": n, "F_n_minus_1": f_nm1, "F_n": f_n,
             "F_n_plus_1": f_np1, "det_mod_256": det,
             "expected_mod_256": expected})

    def _normalize_payload(self, payload: np.ndarray, provenance: str) -> Tuple[np.ndarray, str]:
        if not isinstance(payload, np.ndarray) or payload.dtype.hasobject:
            raise ValueError("payload must be a numeric NumPy ndarray (no object dtype)")
        if payload.size > self.max_payload_elements or payload.nbytes > self.max_payload_bytes:
            raise ValueError("payload exceeds configured processing limit")
        if provenance == "exact_integer":
            if payload.dtype.kind not in ("i", "u"):
                raise ValueError("exact_integer provenance requires integer dtype")
            if payload.size and (np.any(payload < 0) or np.any(payload > 255)):
                raise ValueError("exact_integer payload values must be in [0, 255]")
        elif provenance == "float_derived":
            # Complex values cannot use this modular transform. Accept only
            # exactly integral, finite real floats in the residue range.
            if payload.dtype.kind != "f":
                raise ValueError("float_derived provenance requires real floating dtype")
            if payload.size and (not np.all(np.isfinite(payload))
                    or np.any(payload < 0) or np.any(payload > 255)
                    or not np.all(payload == np.floor(payload))):
                raise ValueError("float_derived values must be finite integer residues in [0, 255]")
        else:
            raise ValueError(f"unknown input provenance: {provenance}")
        return np.asarray(payload, dtype=np.int64).copy(), str(payload.dtype)

    def _fold_with_receipt(self, flat_payload: np.ndarray) -> Tuple[np.ndarray, Receipt]:
        identity = np.eye(2, dtype=np.int64)
        product = (self.M15 @ self.M15_INV) % self.MODULUS
        if not np.array_equal(product, identity):
            raise ValueError("M15 inverse check failed")
        flat = np.asarray(flat_payload, dtype=np.int64).reshape(-1)
        folded = flat.copy()
        pairs = flat.size // 2
        if pairs:
            source = flat[:pairs * 2].reshape(-1, 2)
            transformed = (source @ self.M15.T) % self.MODULUS
            restored = (transformed @ self.M15_INV.T) % self.MODULUS
            if not np.array_equal(restored, source):
                raise ValueError("M15 fold round trip failed")
            folded[:pairs * 2] = transformed.reshape(-1)
        receipt = make_receipt(Functor.F_EXEC,
            "unfold(fold(x)) = x for every supplied element",
            "bounded modular M15 transform with full round-trip",
            {"M15_det_mod_256": int((self.M15[0,0]*self.M15[1,1] - self.M15[0,1]*self.M15[1,0]) % 256),
             "payload_size": int(flat.size), "paired_elements": int(pairs * 2),
             "has_trailing_element": bool(flat.size % 2),
             "input_digest": _tensor_digest(flat),
             "folded_digest": _tensor_digest(folded)})
        return folded, receipt

    def _input_scope_receipt(self, provenance: str, source_dtype: str,
                             normalized: np.ndarray) -> Receipt:
        return make_receipt(Functor.F_TENSOR,
            "modular residue scope is explicit and validated",
            "provenance + dtype + range validation",
            {"provenance": provenance, "source_dtype": source_dtype,
             "normalized_dtype": str(normalized.dtype),
             "bit_exact_claimed": provenance == "exact_integer",
             "residue_range": [0, 255], "size": int(normalized.size)})

    def _snap_receipt(self, n: int) -> Tuple[bool, Optional[int], bool, Receipt]:
        active = n >= self.SNAP_THRESHOLD
        phase = n % self.M_ORDER if active else None
        boundary = bool(active and phase == 0)
        return active, phase, boundary, make_receipt(
            Functor.F_EXEC,
            f"snap active iff n >= {self.SNAP_THRESHOLD}; phase is n mod {self.M_ORDER}",
            "threshold_and_modular_phase",
            {"n": n, "threshold": self.SNAP_THRESHOLD, "active": active,
             "phase": phase, "is_period_boundary": boundary, "m_order": self.M_ORDER})

    def _resolve_tier(self, tenant_id: str, requested: str) -> TierPolicy:
        entitled = self._entitlements.get(tenant_id)
        if entitled is None:
            raise PermissionError(f"tenant {tenant_id!r} has no configured entitlement")
        if not isinstance(requested, str) or requested.lower() != entitled:
            raise PermissionError(f"tenant {tenant_id!r} is not entitled to requested tier")
        return COMMERCIAL_TIERS[entitled]

    @staticmethod
    def preflight_content_length(content_length: int, max_payload_bytes: int) -> None:
        """Call before reading/deserializing the body at the transport boundary."""
        if type(content_length) is not int or content_length < 0:
            raise ValueError("Content-Length must be a non-negative integer")
        if content_length > max_payload_bytes:
            raise ValueError("request body exceeds ingress byte limit")

    def _certificate_payload(self, response: ComputeResponse) -> Dict[str, Any]:
        return {
            "schema": "hyba-certificate-v4.3",
            "request_id": response.request_id,
            "tenant_id": response.tenant_id,
            "requested_tier": response.requested_tier,
            "tier_enforced": response.tier_enforced,
            "requested_n": response.requested_n,
            "enforced_n": response.enforced_n,
            "depth_receipt": response.depth_clamp_receipt.digest,
            "cassini_receipt": response.cassini_receipt.digest,
            "fold_receipt": response.fold_bijectivity_receipt.digest,
            "snap_receipt": response.snap_receipt.digest,
            "input_scope_receipt": response.input_scope_receipt.digest,
            "rate_limit_receipt": response.rate_limit_receipt.digest,
            "output_tensor_digest": response.output_tensor_digest,
            "output_tensor_shape": list(response.processed_tensor.shape),
            "output_tensor_dtype": response.processed_tensor.dtype.str,
            "snap_active": response.integer_snap_active,
            "snap_phase": response.integer_snap_phase,
            "snap_boundary": response.integer_snap_is_period_boundary,
            "m_order": response.m_order,
            "precision_class_declared": response.precision_class_declared,
            "precision_bound_declared": response.precision_bound_declared,
            "kellogg_cert_required": response.kellogg_cert_required,
            "input_provenance": response.input_provenance,
            "ops_capacity_declared": response.ops_capacity_declared,
            "ops_capacity_enforced": response.ops_capacity_enforced,
            "parent_certificate_hash": response.parent_certificate_hash,
        }

    def process_workload(self, request: ComputeRequest, *,
                         authenticated_tenant_id: str) -> ComputeResponse:
        start = time.perf_counter()
        if not isinstance(request, ComputeRequest):
            raise TypeError("request must be a ComputeRequest")
        if (not isinstance(authenticated_tenant_id, str)
                or not authenticated_tenant_id.strip()):
            raise PermissionError("trusted authenticated tenant identity is required")
        if request.tenant_id != authenticated_tenant_id:
            raise PermissionError("request tenant_id does not match authenticated identity")
        if not isinstance(request.request_id, str) or not request.request_id.strip():
            raise ValueError("request_id must be non-empty")
        if type(request.requested_depth) is not int or request.requested_depth < 0:
            raise ValueError("requested_depth must be a non-negative integer")
        policy = self._resolve_tier(authenticated_tenant_id, request.client_tier)
        normalized, source_dtype = self._normalize_payload(request.payload_tensor, request.input_provenance)

        ops = max(1, int(normalized.size))
        allowed, remaining = self._rate_limiter.try_consume(
            authenticated_tenant_id, ops, policy.ops_capacity_declared,
            policy.ops_capacity_window_seconds)
        if not allowed:
            raise RuntimeError(f"rate limit exceeded; {remaining:.0f} tokens remain")
        enforced_n = min(request.requested_depth, policy.max_recurrence_n)
        depth_receipt = make_receipt(Functor.F_EXEC,
            "enforced_n = min(requested_n, tier_cap)", "tier_cap_check",
            {"requested_n": request.requested_depth, "tier_cap": policy.max_recurrence_n,
             "enforced_n": enforced_n, "clamped": enforced_n != request.requested_depth,
             "tier": policy.name})
        cassini_receipt = self._cassini_receipt(enforced_n)
        folded_flat, fold_receipt = self._fold_with_receipt(normalized.reshape(-1))
        processed = folded_flat.reshape(normalized.shape)
        output_digest = _tensor_digest(processed)
        snap_active, snap_phase, snap_boundary, snap_receipt = self._snap_receipt(enforced_n)
        input_receipt = self._input_scope_receipt(request.input_provenance, source_dtype, normalized)
        rate_receipt = make_receipt(Functor.F_EXEC,
            "authenticated tenant consumed ops within entitled token bucket",
            "locked_token_bucket",
            {"tenant_id": authenticated_tenant_id, "requested_ops": ops,
             "capacity_declared": policy.ops_capacity_declared,
             "tokens_remaining_after": round(remaining, 4),
             "window_seconds": policy.ops_capacity_window_seconds})
        latency = (time.perf_counter() - start) * 1e6

        with self._chain_lock:
            parent = self.audit_store.head(self._genesis_cert)
            response = ComputeResponse(
                request_id=request.request_id, tenant_id=authenticated_tenant_id,
                requested_tier=request.client_tier.lower(), tier_enforced=policy.name,
                requested_n=request.requested_depth, enforced_n=enforced_n,
                depth_clamp_receipt=depth_receipt, cassini_receipt=cassini_receipt,
                processed_tensor=processed, output_tensor_digest=output_digest,
                fold_bijectivity_receipt=fold_receipt,
                integer_snap_active=snap_active, integer_snap_phase=snap_phase,
                integer_snap_is_period_boundary=snap_boundary, m_order=self.M_ORDER,
                snap_receipt=snap_receipt, precision_class_declared=policy.precision_class,
                precision_bound_declared=policy.precision_bound,
                kellogg_cert_required=policy.kellogg_cert_required,
                input_provenance=request.input_provenance,
                input_scope_receipt=input_receipt,
                ops_capacity_declared=policy.ops_capacity_declared,
                ops_capacity_enforced=True, rate_limit_receipt=rate_receipt,
                parent_certificate_hash=parent, execution_latency_us=latency)
            payload = self._certificate_payload(response)
            payload_json = _canonical_json(payload)
            cert = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            signature = self._signing_key.sign(cert.encode("ascii")).hex()
            response.output_certificate_hash = cert
            response.output_certificate_signature = signature
            response.lineage_receipt = make_receipt(Functor.F_LINEAGE,
                "signed certificate commits to the canonical response claims and parent",
                "canonical_json_sha256_plus_ed25519",
                {"parent_cert": parent, "cert_sha256": cert,
                 "signature_hex": signature, "signer_pubkey_hex": self._public_key_hex(),
                 "request_id": request.request_id})
            self.audit_store.append(parent, cert, signature, payload_json)
            self._prev_cert = cert
            self.audit_trail.append({"request_id": request.request_id,
                                     "parent_certificate": parent,
                                     "output_certificate": cert})
        logger.info("Certified request %s for tenant %s at %s",
                    request.request_id, authenticated_tenant_id, policy.name)
        return response

    def verify_receipts(self, response: ComputeResponse) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        receipts = {
            "depth": response.depth_clamp_receipt,
            "cassini": response.cassini_receipt,
            "fold": response.fold_bijectivity_receipt,
            "snap": response.snap_receipt,
            "input_scope": response.input_scope_receipt,
            "rate_limit": response.rate_limit_receipt,
            "lineage": response.lineage_receipt,
        }
        for name, receipt in receipts.items():
            if receipt is None or not receipt.verify():
                failures.append(f"{name}: missing or digest mismatch")
        return not failures, failures

    @staticmethod
    def _slow_cassini_valid(n: int) -> bool:
        # Deliberately recurrence-based and separate from fast-doubling producer.
        if n == 0:
            f_nm1, f_n, f_np1 = 1, 0, 1
        else:
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            f_n, f_np1 = a, b
            f_nm1 = f_np1 - f_n
        return (f_np1 * f_nm1 - f_n * f_n) % 256 == ((-1) ** n) % 256

    def verify_claims(self, response: ComputeResponse,
                      original_payload: np.ndarray) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        n = response.enforced_n
        if type(n) is not int or n < 0:
            return False, ["enforced_n: invalid"]
        try:
            policy = self._resolve_tier(response.tenant_id, response.requested_tier)
            if response.tier_enforced != policy.name:
                failures.append("tier: response does not match configured entitlement")
            if type(response.requested_n) is not int or response.requested_n < 0:
                failures.append("requested_n: invalid")
            elif n != min(response.requested_n, policy.max_recurrence_n):
                failures.append("depth: enforced_n does not match tier cap")
            if n > policy.max_recurrence_n:
                failures.append("enforced_n: exceeds entitled tier cap")
            if response.precision_class_declared != policy.precision_class:
                failures.append("precision_class: does not match tier policy")
            if response.precision_bound_declared != policy.precision_bound:
                failures.append("precision_bound: does not match tier policy")
            if response.kellogg_cert_required != policy.kellogg_cert_required:
                failures.append("kellogg_cert_required: does not match tier policy")
            if response.ops_capacity_declared != policy.ops_capacity_declared:
                failures.append("ops_capacity: does not match tier policy")
            if response.ops_capacity_enforced is not True:
                failures.append("ops_capacity: not marked enforced")
        except (PermissionError, AttributeError, TypeError):
            policy = None
            failures.append("tier: entitlement could not be verified")
        # Bound verifier work before recurrence or modular-order checks.
        if n > max(p.max_recurrence_n for p in COMMERCIAL_TIERS.values()):
            return False, failures + ["enforced_n: exceeds supported verification bound"]
        if not self._slow_cassini_valid(n):
            failures.append("cassini: identity failed")
        if type(response.m_order) is not int or response.m_order != self.M_ORDER:
            failures.append("m_order: incorrect")
        elif not self._assert_M_order(response.m_order):
            failures.append("m_order: incorrect")
        if not np.array_equal((self.M15 @ self.M15_INV) % 256, np.eye(2, dtype=np.int64)):
            failures.append("m15_inverse: incorrect")
        expected_active = n >= self.SNAP_THRESHOLD
        expected_phase = n % self.M_ORDER if expected_active else None
        expected_boundary = bool(expected_active and expected_phase == 0)
        if (response.integer_snap_active != expected_active
                or response.integer_snap_phase != expected_phase
                or response.integer_snap_is_period_boundary != expected_boundary):
            failures.append("snap: phase or activation mismatch")
        try:
            normalized, _ = self._normalize_payload(original_payload, response.input_provenance)
            processed = response.processed_tensor
            if not isinstance(processed, np.ndarray) or processed.dtype.kind not in ("i", "u"):
                failures.append("fold: processed tensor must be integer residues")
            elif processed.shape != normalized.shape:
                failures.append("fold: shape mismatch")
            elif processed.size != normalized.size:
                failures.append("fold: size mismatch")
            else:
                flat = processed.reshape(-1)
                out_of_range = bool(flat.size and (np.any(flat < 0) or np.any(flat > 255)))
                if out_of_range:
                    failures.append("fold: output outside residue range")
                if not out_of_range:
                    pairs = flat.size // 2
                    if pairs:
                        folded_pairs = flat[:pairs * 2].astype(np.int64, copy=False).reshape(-1, 2)
                        unfolded = (folded_pairs @ self.M15_INV.T) % 256
                        if not np.array_equal(unfolded, normalized.reshape(-1)[:pairs * 2].reshape(-1, 2)):
                            failures.append("fold: paired round trip mismatch")
                    if flat.size % 2 and int(flat[-1]) != int(normalized.reshape(-1)[-1]):
                        failures.append("fold: trailing element mismatch")
        except (ValueError, TypeError, OverflowError):
            failures.append("fold: original payload invalid")
        try:
            if _tensor_digest(response.processed_tensor) != response.output_tensor_digest:
                failures.append("output_digest: mismatch")
        except (TypeError, ValueError):
            failures.append("output_digest: invalid tensor")
        return not failures, failures

    def verify_signature(self, response: ComputeResponse,
                         pubkey: Optional[Ed25519PublicKey] = None) -> bool:
        try:
            # The certificate commits to receipt digests; also verify that
            # each digest still represents the attached receipt contents.
            if not self.verify_receipts(response)[0]:
                return False
            if _tensor_digest(response.processed_tensor) != response.output_tensor_digest:
                return False
            payload_json = _canonical_json(self._certificate_payload(response))
            expected_cert = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            if expected_cert != response.output_certificate_hash:
                return False
            (pubkey or self._public_key).verify(
                bytes.fromhex(response.output_certificate_signature),
                expected_cert.encode("ascii"))
            return True
        except (InvalidSignature, ValueError, TypeError, AttributeError):
            return False

    def verify_signed_response(self, response: ComputeResponse,
                               original_payload: np.ndarray) -> Tuple[bool, List[str]]:
        checks = [self.verify_receipts(response), self.verify_claims(response, original_payload)]
        failures = [message for ok, messages in checks for message in messages]
        if not self.verify_signature(response):
            failures.append("signature: invalid or response is not bound to certificate")
        return not failures, failures

    def verify_certificate_chain(self) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        previous = self._genesis_cert
        for index, entry in enumerate(self.audit_store.entries()):
            try:
                payload = entry["payload"]
                payload_json = _canonical_json(payload)
                cert = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
                if entry["parent_cert"] != previous:
                    failures.append(f"entry {index}: parent mismatch")
                if payload.get("parent_certificate_hash") != previous:
                    failures.append(f"entry {index}: signed parent mismatch")
                if cert != entry["cert"]:
                    failures.append(f"entry {index}: certificate payload mismatch")
                self._public_key.verify(bytes.fromhex(entry["signature_hex"]), cert.encode("ascii"))
            except (InvalidSignature, ValueError, TypeError, KeyError):
                failures.append(f"entry {index}: malformed or invalid signature")
            previous = entry.get("cert", "")
        return not failures, failures

    def verify_genesis(self, genesis_sig_hex: str, genesis_cert: str) -> bool:
        payload = f"HYBA-v4.3-genesis:{self._public_key_hex()}"
        try:
            self._public_key.verify(bytes.fromhex(genesis_sig_hex), payload.encode("utf-8"))
            return hashlib.sha256(payload.encode("utf-8")).hexdigest() == genesis_cert
        except (InvalidSignature, ValueError):
            return False

    def genesis(self) -> Dict[str, str]:
        return {"genesis_cert": self._genesis_cert, "genesis_sig": self._genesis_sig,
                "signer_pubkey_hex": self._public_key_hex(),
                "m_order": str(self.M_ORDER), "m15_order": str(self._m15_order),
                "m15_pow2_order": str(self._m15_pow2_order)}

    def _public_key_hex(self) -> str:
        raw = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        return raw.hex()
