"""Enterprise HTTP compatibility surface over the canonical Python backend.

There is deliberately no treasury signer, external ledger, or GPU emulator in
this module. Missing adapters fail closed. Legacy guardian mediation is retained.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from enterprise_contract import (
    COOKIE, ROLES, ElevationCache, OperatorSecurity, Refusal, SealedAudit,
    economics, evidence_zip, measure_elevation, sha256,
)

GET_PATHS = frozenset({"/api/mining/status", "/api/mining/pools", "/api/chronus/elevation",
    "/api/chronus/digest", "/api/auth/me", "/api/treasury/overview", "/api/beta/customers",
    "/api/landing/summary", "/api/evidence/pack"})
POST_PATHS = frozenset({"/api/auth/login", "/api/auth/logout", "/api/mining/configure",
    "/api/mining/start", "/api/mining/stop", "/api/mining/disarm", "/api/v1/mining/start",
    "/api/v1/mining/stop", "/api/v1/mining/disarm", "/api/approvals", "/api/treasury/withdraw"})


@dataclass
class Response:
    status: int
    payload: object
    headers: dict = field(default_factory=dict)
    binary: bool = False


class AlreadyAnswered(Exception):
    pass


class CanonicalBackend:
    def __init__(self, api):
        self.api = api

    def status(self):
        return self.api.status_payload()

    def config(self):
        return self.api.runtime_config.load()

    def pools(self):
        from pool_catalog import POOL_CATALOG, pool_names
        return [{"poolId": k, "label": k.title(), "region": "operator-configured",
                 "feeNote": "See the pool's current terms; no fee or yield guarantee."}
                for k in pool_names() if k in POOL_CATALOG]

    def config_digest(self):
        config = dict(self.config())
        config.pop("updated_at", None)
        return sha256(config)

    def configure(self, body, hardware):
        self.stop()
        config = self.config()
        config["live_submit"] = {"enabled": False, "approval_id": ""}
        config["hashrate"]["target_hs"] = body["hashrate_hps"] if hardware else 0
        config["mining_policy"] = {"poolId": body["poolId"], "shares_target": body["shares_target"]}
        if hardware:
            from pool_catalog import POOL_CATALOG, pool_settings
            pool = pool_settings(body["poolId"], primary=True)
            host = urlparse("//" + (pool.endpoint or "").split("://")[-1]).hostname
            domains = POOL_CATALOG[body["poolId"]]["domains"]
            if not host or not any(host == d or host.endswith("." + d) for d in domains):
                raise Refusal(503, "POOL_ENDPOINT_NOT_ALLOWLISTED")
            if not pool.user or not pool.password:
                raise Refusal(503, "POOL_SECRETS_NOT_CONFIGURED")
            config["pools"] = [{"endpoint": pool.endpoint, "worker": pool.user,
                                "password": pool.password, "enabled": True}]
        else:
            for p in config.get("pools", []):
                p["enabled"] = False
        self.api.runtime_config.save(config)
        return self.config_digest()

    def start(self):
        # Legacy configuration APIs cannot smuggle an arbitrary endpoint into
        # an approved run. Approvals bind the full current configuration too.
        from pool_catalog import POOL_CATALOG
        config = self.config()
        policy = config.get("mining_policy") or {}
        entry = POOL_CATALOG.get(policy.get("poolId"))
        enabled = [p for p in config.get("pools", []) if p.get("enabled")]
        if entry is None or len(enabled) != 1:
            raise Refusal(503, "ALLOWLISTED_POOL_CONFIGURATION_REQUIRED")
        host = urlparse("//" + enabled[0].get("endpoint", "").split("://")[-1]).hostname
        if not host or not any(host == d or host.endswith("." + d) for d in entry["domains"]):
            raise Refusal(503, "POOL_ENDPOINT_NOT_ALLOWLISTED")
        code, result = self.api._config_put({"live_submit": {"enabled": True}}, dual_authority=True)
        if int(code) >= 400 or result.get("ok") is False:
            raise Refusal(int(code) if int(code) >= 400 else 503, "CANONICAL_ARM_REFUSED")
        code, result = self.api._mining_start({})
        if int(code) >= 400 or result.get("ok") is not True:
            self.stop()
            raise Refusal(503, "CANONICAL_START_REFUSED")
        return {"state": "START_REQUESTED", "ready_to_mine_certificate": "WITHHELD"}

    def stop(self):
        # Revoke submission first; stopping a worker alone must not leave live intent.
        try:
            config = self.config()
            config["live_submit"] = {"enabled": False, "approval_id": ""}
            self.api.runtime_config.save(config)
        finally:
            self.api._control_plane().stop_workers()
        return {"state": "DISARMED", "ready_to_mine_certificate": "WITHHELD"}

    def accepted(self):
        return sum(r.shares_accepted for r in self.api._control_plane().records())

    def treasury(self):
        return None  # No canonical wallet observer is installed in this Git backend.

    def customers(self):
        return None  # Never manufacture a beta ledger from UI constants.

    def withdraw(self, body):
        raise Refusal(503, "HSM_TPM_SIGNER_UNAVAILABLE")


class EnterpriseService:
    def __init__(self, backend, state_dir: Path, evidence_root: Path, producer=None):
        self.backend, self.state_dir, self.evidence_root = backend, state_dir, evidence_root
        self.lock = threading.RLock()
        self._security = None
        self.elevation = ElevationCache(producer or self._measure)
        self.stop_event = threading.Event()
        self.thread = None
        self._last_seen, self._session_accepted = 0, 0

    def _measure(self):
        return measure_elevation(int(self.backend.status().get("gpu", {}).get("opencl_device_count", 0) or 0) > 0)

    def security(self):
        with self.lock:
            if self._security is None:
                try:
                    key = bytes.fromhex(os.getenv("HYBA_AUDIT_HMAC_KEY", ""))
                except ValueError:
                    raise Refusal(503, "AUDIT_KEY_UNAVAILABLE") from None
                self._security = OperatorSecurity(SealedAudit(self.state_dir / "audit.sqlite3", key))
            return self._security

    def boot(self):
        # Approval/session grants never survive a restart. Revoke persisted live intent.
        config = self.backend.config()
        if config.get("mining_policy") is not None or config.get("live_submit", {}).get("enabled"):
            self.backend.stop()
        self.thread = threading.Thread(target=self._monitor, name="hyba-shares-target", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=10)

    def _monitor(self):
        while not self.stop_event.wait(0.5):
            try:
                self.observe_target()
            except Exception as exc:
                # Loss of the safety observer revokes submission, never silently continues.
                try:
                    self.backend.stop()
                except Exception as stop_exc:
                    print(f"[hyba] shutdown requires intervention: {type(stop_exc).__name__}")
                print(f"[hyba] shares-target observer failed closed: {type(exc).__name__}")

    def observe_target(self):
        with self.lock:
            config = self.backend.config()
            policy = config.get("mining_policy")
            if policy is None or not config.get("live_submit", {}).get("enabled"):
                return
            accepted = self.backend.accepted()
            if type(accepted) is not int or accepted < 0:
                raise Refusal(503, "INVALID_SHARE_COUNTER")
            # Accumulate across a worker counter reset; target is per authorized run.
            self._session_accepted += accepted - self._last_seen if accepted >= self._last_seen else accepted
            self._last_seen = accepted
            if self._session_accepted >= policy["shares_target"]:
                self.backend.stop()
                self.security().audit.append("MINING_AUTO_DISARM", shares_accepted=self._session_accepted,
                                             shares_target=policy["shares_target"], state="DISARMED")

    def _guard(self, guard, operation, body):
        if guard is None:
            raise Refusal(503, "GUARDIAN_DEPENDENCY_UNAVAILABLE")
        if not guard("/api/v1/" + operation.replace(".", "/"), body):
            raise AlreadyAnswered()

    def dispatch(self, method, path, headers, body=None, remote="", guard=None):
        body = {} if body is None else body
        if not isinstance(body, dict):
            return self.dispatch_refusal(method, path, "OBJECT_REQUIRED")
        try:
            return self._dispatch(method, path, headers, body, remote, guard)
        except AlreadyAnswered:
            return None
        except Refusal as exc:
            payload = {"ok": False, "error": exc.reason}
            if method == "POST":
                try:
                    payload["audit_hash"] = self.security().audit.append("REQUEST_REFUSED", path=path, reason=exc.reason)
                except Exception:
                    payload.update(audit_hash=None, audit_status="UNAVAILABLE")
            return Response(exc.status, payload)
        except (ValueError, TypeError, OverflowError):
            return self.dispatch_refusal(method, path, "INVALID_REQUEST")

    def dispatch_refusal(self, method, path, reason):
        payload = {"ok": False, "error": reason}
        if method == "POST":
            try:
                payload["audit_hash"] = self.security().audit.append("REQUEST_REFUSED", path=path, reason=reason)
            except Exception:
                payload.update(audit_hash=None, audit_status="UNAVAILABLE")
        return Response(400, payload)

    def _dispatch(self, method, path, headers, body, remote, guard):
        if method == "GET" and path == "/api/mining/status":
            status = self.backend.status()
            # Public contract excludes hostnames, worker IDs, runtime config and pool jobs.
            public = {k: status[k] for k in (
                "release_posture", "release_scope_label", "ready_to_mine_certificate", "status",
                "armed", "shares_accepted", "hashrate", "igpu_present", "igpu_status", "speedup_claimed",
                "emulated", "device", "ready_to_mine")}
            public["ready_to_mine"] = {k: v for k, v in public["ready_to_mine"].items() if k != "details"}
            return Response(200, public)
        if method == "GET" and path == "/api/mining/pools":
            return Response(200, {"pools": self.backend.pools()})
        if method == "GET" and path in {"/api/chronus/elevation", "/api/chronus/digest"}:
            snapshot = self.elevation.get()
            return Response(200, snapshot if path.endswith("elevation") else {"sha256": snapshot["sha256"]})
        if method == "GET" and path == "/api/landing/summary":
            customers = self.backend.customers()
            verified = [] if customers is None else [row for row in customers
                        if row.get("cost_evidence_status") == "VERIFIED" and row.get("receipt_sha256")]
            from decimal import Decimal
            accounting = None if not verified else economics(
                sum((Decimal(str(row["baseline_cost"])) for row in verified), Decimal(0)),
                sum((Decimal(str(row["folded_cost"])) for row in verified), Decimal(0)))
            return Response(200, {"status": "OFFLINE" if customers is None else "OBSERVED",
                "verified_cost_records": len(verified), "economics": accounting,
                "gain_share_rate": "0.25", "zero_fee_gate": accounting is None or accounting["zero_fee_gate"],
                "claim_boundary": "Only verified cost receipts enter accounting; not mining yield."})
        security = self.security()
        if method == "POST":
            security.origin(headers)
        if method == "POST" and path == "/api/auth/login":
            identity, token = security.login(body, remote)
            return Response(200, identity, {"Set-Cookie": f"{COOKIE}={token}; Path=/; Max-Age=3600; Secure; HttpOnly; SameSite=Strict"})
        if method == "GET" and path == "/api/auth/me":
            name, role = security.principal(headers, ROLES)
            return Response(200, {"principal_id": name, "role": role})
        if method == "POST" and path == "/api/auth/logout":
            receipt = security.logout(headers)
            return Response(200, {"state": "SIGNED_OUT", "audit_hash": receipt},
                            {"Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict"})
        if method == "POST" and path == "/api/approvals":
            name, _ = security.principal(headers, {"approver"})
            return Response(201, security.approve(name, body.get("action"), body.get("request_digest")))
        founder, _ = security.principal(headers, {"founder_ceo"})
        if method == "GET" and path == "/api/treasury/overview":
            data = self.backend.treasury()
            return Response(200, data if data is not None else {
                "status": "OFFLINE", "balance": None, "height": None, "price": None, "rigs": [],
                "reason": "BACKEND_TREASURY_OBSERVER_UNAVAILABLE"})
        if method == "GET" and path == "/api/beta/customers":
            customers = self.backend.customers()
            return Response(200, {"status": "OFFLINE" if customers is None else "OBSERVED",
                                  "customers": [] if customers is None else [{**row,
                    "economics": economics(row["baseline_cost"], row["folded_cost"])
                    if row.get("cost_evidence_status") == "VERIFIED" and row.get("receipt_sha256") else None}
                    for row in customers]})
        if method == "GET" and path == "/api/evidence/pack":
            data, digest = evidence_zip(self.evidence_root, datetime.now(timezone.utc).date().isoformat())
            return Response(200, data, {"X-Content-SHA256": digest,
                            "Content-Disposition": 'attachment; filename="HYBA-evidence.zip"'}, True)
        if method == "POST" and path in {"/api/mining/configure", "/api/mining/start", "/api/v1/mining/start",
            "/api/mining/stop", "/api/mining/disarm", "/api/v1/mining/stop", "/api/v1/mining/disarm"}:
            with self.lock:
                body = dict(body)
                observation = body.pop("observation", None)
                guarded_body = {**body, **({"observation": observation} if observation is not None else {})}
                self._guard(guard, "mining." + path.rsplit("/", 1)[1], guarded_body)
                receipt = security.audit.append("MINING_INTENT", principal_id=founder, path=path,
                                                 request_digest=sha256(body))
                if path.endswith("configure"):
                    if set(body) != {"poolId", "hashrate_hps", "shares_target"}:
                        raise Refusal(400, "INVALID_CONFIG_FIELDS")
                    if body["poolId"] not in {p["poolId"] for p in self.backend.pools()}:
                        raise Refusal(400, "POOL_NOT_ALLOWLISTED")
                    rate, target = body["hashrate_hps"], body["shares_target"]
                    if (isinstance(rate, bool) or not isinstance(rate, (int, float))
                        or not 0 <= rate <= self.backend.config()["hashrate"]["ceiling_hs"]
                        or type(target) is not int or not 1 <= target <= 10000):
                        raise Refusal(400, "CONFIG_OUT_OF_BOUNDS")
                    hardware = self.backend.status()["igpu_present"] is True
                    digest = self.backend.configure(body, hardware)
                    receipt = security.audit.append("MINING_CONFIGURED", principal_id=founder,
                        config_digest=digest, poolId=body["poolId"], shares_target=target, state="DISARMED")
                    return Response(200 if hardware else 503, {"state": "DISARMED", "config_digest": digest,
                        "hashrate_hps": rate if hardware else 0, "shares_target": target,
                        "error": None if hardware else "NO_ATTACHED_MINING_HARDWARE", "audit_hash": receipt})
                if path.endswith("start"):
                    config = self.backend.config()
                    if config.get("live_submit", {}).get("enabled"):
                        raise Refusal(409, "ALREADY_ARMED")
                    if config.get("mining_policy") is None:
                        raise Refusal(409, "CONFIGURE_REQUIRED")
                    if self.backend.status()["igpu_present"] is not True:
                        raise Refusal(503, "NO_ATTACHED_MINING_HARDWARE")
                    from lucas.ladder import require_release_rung
                    index = config.get("intelligence", {}).get("lucas_index")
                    if index is not None:
                        require_release_rung(index)
                    digest = self.backend.config_digest()
                    security.consume(body.get("approval_id"), founder, "mining.start", digest)
                    self._session_accepted, self._last_seen = 0, 0
                    try:
                        result = self.backend.start()
                        receipt = security.audit.append("MINING_START_REQUESTED", principal_id=founder, config_digest=digest)
                    except Exception:
                        self.backend.stop()
                        raise
                    return Response(202, {**result, "audit_hash": receipt})
                result = self.backend.stop()
                receipt = security.audit.append("MINING_DISARM", principal_id=founder, state="DISARMED")
                return Response(200, {**result, "audit_hash": receipt})
        if method == "POST" and path == "/api/treasury/withdraw":
            # The API does not invent a signing adapter. No client key/signature accepted.
            if set(body) != {"amount", "destination", "network", "approval_id"}:
                raise Refusal(400, "INVALID_WITHDRAW_FIELDS")
            request = {k: body[k] for k in ("amount", "destination", "network")}
            from decimal import Decimal
            amount = Decimal(str(request["amount"]))
            if (not amount.is_finite() or amount <= 0 or
                any(not isinstance(request[k], str) or not 1 <= len(request[k]) <= 256
                    for k in ("destination", "network"))):
                raise Refusal(400, "INVALID_WITHDRAWAL")
            security.consume(body["approval_id"], founder, "treasury.withdraw", sha256(request))
            security.audit.append("WITHDRAW_INTENT", principal_id=founder, request_digest=sha256(request))
            result = self.backend.withdraw(request)
            receipt = security.audit.append("WITHDRAW_RECEIPT", principal_id=founder, receipt_digest=sha256(result))
            return Response(200, {**result, "audit_hash": receipt})
        raise Refusal(404, "NOT_FOUND")
