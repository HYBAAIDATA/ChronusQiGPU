"""HYBA operator contracts. No pool, wallet, or hardware authority is created here.

Transport adapters must retain the canonical guardian, runtime configuration,
worker lifecycle, and signer boundaries. Unknown evidence is never a PASS.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import io
import json
import math
import os
import random
import secrets
import sqlite3
import threading
import time
import zipfile
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Any

COOKIE = "__Host-hyba_session"
ROLES = {"founder_ceo", "approver", "operator"}
CLAIM_BOUNDARY = (
    "Exact integer reference checks are computational evidence only. "
    "Search heuristics and healing telemetry are not proof of yield. "
    "No mining certificate without hardware, fresh pool acceptance, and readiness."
)


class Refusal(Exception):
    def __init__(self, status: int, reason: str):
        self.status, self.reason = status, reason
        super().__init__(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def number(value: Any, default: Any = None) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        return value if math.isfinite(value) else default
    except OverflowError:
        return default


def qualify_status(observed: dict, *, now: float | None = None) -> dict:
    """One predicate drives both status and /ready-to-mine (no circular HTTP call)."""
    out = copy.deepcopy(observed)
    now = time.time() if now is None else now
    gpu, stratum = out.get("gpu") or {}, out.get("stratum") or {}
    workers = out.get("workers") or {}
    physical = gpu.get("physical_gpu_available") is True
    live = any(w.get("liveness") is True and w.get("readiness") is True
               for w in workers.values() if isinstance(w, dict))
    armed = ((out.get("runtime") or {}).get("live_submit") or {}).get("enabled") is True
    primary, submission = stratum.get("primary") or {}, stratum.get("submission") or {}
    ack_at = number(submission.get("last_response_at"))
    fresh = ack_at is not None and 0 <= now - ack_at < 300
    accepted = (stratum.get("counters") or {}).get("accepted", 0)
    if type(accepted) is not int or accepted < 0:
        accepted = 0
    pool_ack = (stratum.get("evidence_available") is True
                and primary.get("transport") == "CONNECTED"
                and primary.get("authorized") is True
                and submission.get("last_result") == "ACCEPTED" and fresh)
    ready_before = (out.get("ready_to_mine") or {}).get("ready") is True
    receipt = out.get("execution_receipt") or {}
    backend = str(receipt.get("execution_backend") or "").lower()
    measured_execution = (receipt.get("evidence_available") is True and receipt.get("worker_live") is True
                          and receipt.get("emulated") is False
                          and backend.startswith(("opencl:", "cuda:", "metal:", "asic:"))
                          and "cpu" not in backend
                          and receipt.get("status") in {"PASS", "VERIFIED", "MEASURED"})
    active = physical and live and armed and pool_ack and accepted > 0 and ready_before and measured_execution
    gates = {"hardware_present": physical, "worker_live": live, "armed": armed,
             "fresh_pool_ack": pool_ack, "shares_accepted_positive": accepted > 0,
             "canonical_ready": ready_before, "measured_device_execution": measured_execution}
    ready = dict(out.get("ready_to_mine") or {})
    ready.update(ready=bool(active), certificate="ACTIVE" if active else "WITHHELD",
                 certificate_gates=gates)
    if not active:
        ready["reason"] = next(k for k, v in gates.items() if not v) + "_required"
    out.update(
        ready_to_mine=ready, ready_to_mine_certificate=ready["certificate"],
        release_posture=("VERIFIED_MINING_ACTIVE" if active
                         else "HARDENING_VERIFIED_MINING_WITHHELD"),
        release_scope_label="Chronus computational execution; mining yield requires pool evidence.",
        status=("MINING ACTIVE" if active else "DAEMON OFFLINE — VERIFY BACKEND SERVICE"),
        armed=armed, shares_accepted=accepted, speedup_claimed=False,
        hashrate=number((ready.get("details") or {}).get("hashrate_hs")),
        igpu_present=physical, igpu_status="PRESENT" if physical else "NOT_PRESENT",
        emulated=not physical, device=gpu.get("detected_device") or "not_observed",
    )
    return out


def envelope(payload: Any, path: str, status: int) -> dict:
    out = dict(payload) if isinstance(payload, dict) else {"items": payload}
    out.setdefault("Route", {"requested": path,
                             "executed": "canonical_python_control_api" if status < 400 else None,
                             "fallback_reason": None if status < 400 else out.get("error", "refused")})
    for key, value in {"hashrate": None, "igpu_present": None, "igpu_status": "NOT_PROBED",
                       "speedup_claimed": False, "emulated": None,
                       "device": "not_observed"}.items():
        out.setdefault(key, value)
    def provenance(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                if isinstance(value, dict) and any(s in key.lower() for s in ("quantum", "vqc")):
                    value.setdefault("emulated", None)
                    value.setdefault("device", "not_observed")
                provenance(value)
        elif isinstance(obj, list):
            for value in obj:
                provenance(value)
    out = copy.deepcopy(out)
    provenance(out)
    return out


class SealedAudit:
    """Durable HMAC-SHA256 chain, serialised across processes by SQLite.

    A retained external head anchor is still required to detect whole-file
    rollback. No claim of WORM, HSM custody, or external anchoring is made.
    """
    def __init__(self, path: Path, key: bytes):
        if len(key) < 32:
            raise Refusal(503, "AUDIT_KEY_UNAVAILABLE")
        self.path, self.key = Path(path), key
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # The directory is deployment-owned; never write into an untrusted shared root.
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, mac TEXT NOT NULL)")
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def _verify(self, db) -> tuple[list[dict], str]:
        previous, records = "0" * 64, []
        for expected, (seq, body, mac) in enumerate(db.execute("SELECT seq, body, mac FROM audit ORDER BY seq"), 1):
            try:
                record = json.loads(body)
                calculated = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
                valid = (seq == expected and record["seq"] == seq
                         and record["previous_hash"] == previous
                         and hmac.compare_digest(mac, calculated))
            except (ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                raise Refusal(503, "AUDIT_INTEGRITY_FAILURE")
            records.append({**record, "audit_hash": mac})
            previous = mac
        return records, previous

    def records(self) -> list[dict]:
        with self.connect() as db:
            return self._verify(db)[0]

    def append(self, event: str, **fields) -> str:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            records, previous = self._verify(db)
            record = {"seq": len(records) + 1, "previous_hash": previous,
                      "at": time.time(), "event": event, **fields}
            body = canonical(record).decode()
            mac = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            db.execute("INSERT INTO audit VALUES (?, ?, ?)", (record["seq"], body, mac))
            return mac


class ElevationCache:
    """An immutable boot snapshot; failed refresh retains the last good document."""
    def __init__(self, producer):
        self._lock = threading.Lock()
        self._document = {"schema_version": "hyba.chronus.elevation/1", "package": "chronus",
                          "status": "UNVERIFIED", "order_of_truth": "Computational",
                          "mode_a": {"status": "NOT_RUN", "seeds": [1337, 42, 2026]},
                          "mode_b": {"status": "NOT_RUN", "gated": True},
                          "claim_boundary": CLAIM_BOUNDARY}
        self.refresh(producer)

    def refresh(self, producer) -> bool:
        try:
            document = producer()
            canonical(document)
            if document.get("mode_a", {}).get("status") != "PASS":
                return False
        except Exception:
            return False
        with self._lock:
            self._document = copy.deepcopy(document)
        return True

    def get(self) -> dict:
        with self._lock:
            document = copy.deepcopy(self._document)
        return {"status": document["status"], "document": document, "sha256": sha256(document)}


def measure_elevation(physical_opencl: bool = False) -> dict:
    """Execute canonical exact-integer primitives. Not a Chronus GPU benchmark."""
    from lucas.core import fibonacci, lucas
    from lucas.ladder import FULL_LADDER
    from aethel.zeckendorf import HardenedZeckendorfCodec as Codec
    # Public reference vectors validate SHA-256 plumbing, not nonce savings.
    vectors = ((b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
               (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"))
    for data, expected in vectors:
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("SHA-256 reference vector failed")
    genesis = bytes.fromhex("01000000" + "00" * 32 +
        "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a" +
        "29ab5f49ffff001d1dac2b7c")
    if len(genesis) != 80 or hashlib.sha256(hashlib.sha256(genesis).digest()).digest()[::-1].hex() != (
            "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"):
        raise ValueError("Genesis #0 80-byte vector failed")
    rows = []
    for seed in (1337, 42, 2026):
        rng, started = random.Random(seed), time.perf_counter_ns()
        checks = 0
        for _ in range(1000):
            n = rng.getrandbits(64)
            mask = Codec.encode(n)
            if Codec.decode(mask) != n or not Codec.verify_non_adjacent(mask):
                raise ValueError("Zeckendorf invariant failed")
            checks += 1
        for n in FULL_LADDER:
            if lucas(n) ** 2 - 5 * fibonacci(n) ** 2 != 4 * (-1) ** n:
                raise ValueError("Cassini invariant failed")
        rows.append({"seed": seed, "bijection_points": checks, "cassini_rungs": len(FULL_LADDER),
                     "elapsed_ns": time.perf_counter_ns() - started, "status": "PASS"})
    return {"schema_version": "hyba.chronus.elevation/1", "package": "chronus",
            "status": "VERIFIED_SUBSTRATE_AGNOSTIC", "order_of_truth": "Computational",
            "mode_a": {"status": "PASS", "scope": "exact_integer_reference_invariants",
                       "executor": "cpu_reference", "measurements": rows, "device": "cpu",
                       "emulated": False, "speedup_claimed": False},
            "mode_b": {"status": "NOT_RUN" if physical_opencl else "OPENCL_UNAVAILABLE",
                       "gated": True, "device": "not_qualified", "emulated": None},
            "sha256_vectors": {"nist_reference_points": 2, "genesis_80_byte": "PASS", "scope": "cpu_reference_not_device_qualification"},
            "lucas_rungs": list(FULL_LADDER),
            "stride": {"value": "0x9E3779B9", "saves_hashes": False, "scope": "ordering_only"},
            "heuristics": {k: "search heuristic / telemetry, not proof" for k in
                           ("best_split", "negaFib", "dictionary_rank", "KAM", "Pearl")},
            "postgres": "DESIGN ONLY", "zero_alloc_tensor_manifest": "NOT_RUN",
            "claim_boundary": CLAIM_BOUNDARY}


def economics(baseline: Any, folded: Any) -> dict:
    try:
        b, f = Decimal(str(baseline)), Decimal(str(folded))
    except InvalidOperation as exc:
        raise Refusal(400, "INVALID_ECONOMICS") from exc
    if not b.is_finite() or not f.is_finite() or b < 0 or f < 0:
        raise Refusal(400, "INVALID_ECONOMICS")
    gain = max(Decimal(0), b - f)
    return {"baseline_cost": str(b), "folded_cost": str(f), "verified_gain": str(gain),
            "gain_share_rate": "0.25", "fee": str(gain * Decimal("0.25")),
            "zero_fee_gate": gain == 0, "scope": "cost_accounting_not_mining_yield"}


def evidence_zip(root: Path, day: str) -> tuple[bytes, str]:
    """Export only manifest-listed files after hashing the exact bytes to be zipped."""
    try:
        if datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d") != day:
            raise ValueError()
    except (ValueError, TypeError):
        raise Refusal(503, "EVIDENCE_PATH_REFUSED") from None
    folder = Path(root) / day
    if folder.is_symlink() or not folder.is_dir():
        raise Refusal(503, "EVIDENCE_NOT_AVAILABLE")
    root_resolved = Path(root).resolve()
    if not folder.resolve().is_relative_to(root_resolved):
        raise Refusal(503, "EVIDENCE_PATH_REFUSED")
    manifest_path = folder / "DIGESTS.json"
    if manifest_path.is_symlink():
        raise Refusal(503, "EVIDENCE_PATH_REFUSED")
    try:
        if manifest_path.stat().st_size > 1024 * 1024:
            raise Refusal(503, "EVIDENCE_TOO_LARGE")
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        entries = manifest["files"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refusal(503, "EVIDENCE_MANIFEST_INVALID") from exc
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 256:
        raise Refusal(503, "EVIDENCE_MANIFEST_INVALID")
    blobs, size = {}, len(manifest_bytes)
    for name, digest in entries.items():
        if not isinstance(name, str) or not name or not isinstance(digest, str):
            raise Refusal(503, "EVIDENCE_MANIFEST_INVALID")
        p = Path(name)
        if not p.parts or p.is_absolute() or ".." in p.parts or name == "DIGESTS.json" or "\\" in name:
            raise Refusal(503, "EVIDENCE_PATH_REFUSED")
        path = folder / p
        if any(part.is_symlink() for part in (path, *path.parents)) or not path.resolve().is_relative_to(folder.resolve()):
            raise Refusal(503, "EVIDENCE_PATH_REFUSED")
        try:
            if not path.is_file():
                raise OSError("not a file")
            if path.stat().st_size > 32 * 1024 * 1024:
                raise Refusal(503, "EVIDENCE_TOO_LARGE")
            blob = path.read_bytes()
        except OSError as exc:
            raise Refusal(503, "EVIDENCE_NOT_AVAILABLE") from exc
        size += len(blob)
        if size > 32 * 1024 * 1024 or hashlib.sha256(blob).hexdigest() != digest:
            raise Refusal(503, "EVIDENCE_DIGEST_MISMATCH")
        blobs[name] = blob
    blobs["DIGESTS.json"] = manifest_bytes
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, blob in sorted(blobs.items()):
            info = zipfile.ZipInfo(f"{day}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, blob)
    data = stream.getvalue()
    return data, hashlib.sha256(data).hexdigest()


class OperatorSecurity:
    """Secrets-seeded identities, expiring opaque sessions, independent approvals."""
    def __init__(self, audit: SealedAudit):
        self.audit, self.lock = audit, threading.RLock()
        self.sessions: dict[str, tuple] = {}
        self.approvals: dict[str, tuple] = {}
        self.attempts: OrderedDict[str, list[float]] = OrderedDict()

    def principals(self) -> dict:
        try:
            mapping = json.loads(os.environ["HYBA_AUTH_PRINCIPALS_JSON"])
            if not isinstance(mapping, dict) or not mapping or len(mapping) > 128:
                raise ValueError()
            for name, spec in mapping.items():
                if (not isinstance(name, str) or not 1 <= len(name) <= 128
                    or not isinstance(spec, dict) or spec["role"] not in ROLES
                    or not isinstance(spec["token_sha256"], str) or len(spec["token_sha256"]) != 64):
                    raise ValueError()
                bytes.fromhex(spec["token_sha256"])
            return mapping
        except (KeyError, TypeError, ValueError):
            raise Refusal(503, "AUTH_SECRETS_NOT_CONFIGURED") from None

    def origin(self, headers: Any) -> None:
        origin = os.getenv("HYBA_PUBLIC_ORIGIN", "").rstrip("/")
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise Refusal(503, "PUBLIC_ORIGIN_NOT_CONFIGURED")
        if headers.get("Origin") != origin:
            raise Refusal(403, "ORIGIN_REQUIRED")

    def login(self, body: dict, remote: str) -> tuple[dict, str]:
        now = time.time()
        with self.lock:
            recent = [t for t in self.attempts.pop(remote, []) if now - t < 60]
            self.attempts[remote] = recent + [now]
            while len(self.attempts) > 1024:
                self.attempts.popitem(last=False)
            if len(recent) >= 10:
                raise Refusal(429, "LOGIN_RATE_LIMITED")
            mapping = self.principals()
            name, credential = body.get("principal_id"), body.get("credential")
            if not isinstance(name, str) or not isinstance(credential, str) or len(credential) > 4096:
                raise Refusal(401, "INVALID_CREDENTIAL")
            candidate = hashlib.sha256(credential.encode()).hexdigest()
            spec = mapping.get(name, {})
            if not hmac.compare_digest(candidate, spec.get("token_sha256", "0" * 64)) or not spec:
                raise Refusal(401, "INVALID_CREDENTIAL")
            self.sessions = {k: v for k, v in self.sessions.items() if v[2] > now}
            if len(self.sessions) >= 512:
                raise Refusal(503, "SESSION_CAPACITY_REACHED")
            token = secrets.token_urlsafe(32)
            audit_hash = self.audit.append("AUTH_LOGIN", principal_id=name, role=spec["role"])
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = (name, spec["role"], now + 3600, sha256(spec))
            return {"principal_id": name, "role": spec["role"], "audit_hash": audit_hash}, token

    def session_key(self, headers: Any) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get("Cookie", ""))
            token = cookie[COOKIE].value
        except (KeyError, ValueError, CookieError):
            raise Refusal(401, "SESSION_REQUIRED") from None
        return hashlib.sha256(token.encode()).hexdigest()

    def principal(self, headers: Any, roles: set[str]) -> tuple[str, str]:
        with self.lock:
            key = self.session_key(headers)
            value = self.sessions.get(key)
            if value is None or value[2] <= time.time():
                self.sessions.pop(key, None)
                raise Refusal(401, "SESSION_EXPIRED")
            mapping = self.principals()
            if value[0] not in mapping or sha256(mapping[value[0]]) != value[3]:
                self.sessions.pop(key, None)
                raise Refusal(401, "SESSION_REVOKED")
            if value[1] not in roles:
                raise Refusal(403, "ROLE_REQUIRED")
            return value[0], value[1]

    def logout(self, headers: Any) -> str:
        with self.lock:
            name, _ = self.principal(headers, ROLES)
            receipt = self.audit.append("AUTH_LOGOUT", principal_id=name)
            self.sessions.pop(self.session_key(headers), None)
            return receipt

    def approve(self, principal: str, action: str, digest: str) -> dict:
        if action not in {"mining.start", "treasury.withdraw"} or not isinstance(digest, str) or len(digest) != 64:
            raise Refusal(400, "INVALID_APPROVAL")
        try:
            bytes.fromhex(digest)
        except ValueError:
            raise Refusal(400, "INVALID_APPROVAL") from None
        with self.lock:
            self.approvals = {k: v for k, v in self.approvals.items() if v[3] > time.time()}
            if len(self.approvals) >= 512:
                raise Refusal(503, "APPROVAL_CAPACITY_REACHED")
            token = secrets.token_urlsafe(24)
            receipt = self.audit.append("INDEPENDENT_APPROVAL", principal_id=principal, action=action, request_digest=digest)
            self.approvals[token] = (principal, action, digest, time.time() + 300)
            return {"approval_id": token, "request_digest": digest, "expires_in": 300, "audit_hash": receipt}

    def consume(self, token: str, founder: str, action: str, digest: str) -> str:
        with self.lock:
            value = self.approvals.get(token)
            if (value is None or value[0] == founder or value[1] != action
                or value[2] != digest or value[3] <= time.time()
                or self.principals().get(value[0], {}).get("role") != "approver"):
                raise Refusal(403, "SECOND_APPROVAL_REQUIRED")
            receipt = self.audit.append("DUAL_AUTHORITY_CONSUMED", founder=founder, second_approver=value[0],
                                        action=action, request_digest=digest)
            del self.approvals[token]
            return receipt
