# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""The fleet coordinator: one Chronus iGPU composed from many machines.

Responsibilities:

* admission: workers join with their self-tested, measured routes and their
  backend selection. A join or job within the current tier's entitlement is
  admitted. Demand beyond it records a scale event and is admitted when a
  signed scale grant covers it (the fleet moves to that tier); otherwise the
  machine waits, or the job queues, and status reports "scale available";
* leases: jobs are striped by the scheduling lattice into tiles, grouped and
  leased by capability (``chronus.fleet.scheduler``);
* verification: every result is checked against the pure-Python reference as
  described in ``chronus.fleet.verification``;
* recovery: failed, lost, departed or expired leases are re-run through the
  blind-check channels of ``chronus.fleet.recovery``;
* receipts: each completed job gets an ML-DSA-65 signed, ledger-anchored
  receipt with every device's measured contribution;
* run_fabric: a loop that applies new grants and tier selections, retires
  expired grants, admits waiting work a grant now covers, checks demand
  against the entitlement, snapshots fabric state and anchors the snapshot
  digest in the AL HARAS anchor ledger.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from chronus.fleet.adapters import MODE_A, MODE_B
from chronus.fleet.auth import FleetAuth, tls_server_context
from chronus.fleet.canonical import (
    b64decode,
    b64encode,
    digest_json,
    iso_utc,
    merkle_root,
    monotonic_ns,
    per_second,
    sha256_hex,
    utc_now_ns,
)
from chronus.fleet.crossbar import H4Crossbar, max_h4_diameter
from chronus.fleet.backends import PREFERENCES
from chronus.fleet.errors import FleetError, KernelError, LatticeError, ScaleGrantRejected, TierGateRejected
from chronus.fleet.kernels import ROUTE_CUDA, ROUTE_METAL, ROUTE_OPENCL, Kernel, KernelRegistry, Prepared, default_registry
from chronus.fleet.lattice import LATTICE_LABEL, SchedulingLattice, Tile, require_rung
from chronus.fleet.ledger import AnchorLedger
from chronus.fleet.phase import (
    BYTES_PER_TB,
    CONNECTOR_FLEET_HTTP,
    CONNECTOR_FLEET_TLS,
    SCALE_TIER_NUMBER,
    TIER_1,
    TIERS,
    EntitlementCheck,
    Tier,
    evaluate_entitlement,
    lattice_footprint,
    next_tier_label,
    require_connectors,
    scale_available_message,
    tier_by_number,
)
from chronus.fleet.receipts import HONESTY, RECEIPT_SCHEMA, sign_receipt
from chronus.fleet.scale import (
    GRANT_SCHEMA,
    SELECTION_SCHEMA,
    ScaleEvent,
    ScaleGrant,
    read_documents,
    verify_grant,
    verify_selection,
    write_document,
)
from chronus.fleet.recovery import (
    BaselineChannel,
    FaultedState,
    Incident,
    RecoveryChannel,
    new_incident_id,
    survivors_from,
)
from chronus.fleet.scheduler import (
    DECODE_RATIO,
    PREFILL_RATIO,
    LeaseGroup,
    LeaseScheduler,
    NodeInfo,
    pool_budgets,
)
from chronus.fleet.signing import FleetSigner
from chronus.fleet.transport import DEFAULT_PORT, MAX_BODY_BYTES, FleetHTTPServer
from chronus.fleet.verification import ReferenceVerifier, SamplingPolicy, VerificationOutcome, VerificationTask
from chronus.fleet.workunit import ROUTE_AUTO, WorkUnit

logger = logging.getLogger(__name__)
GPU_ROUTES = (ROUTE_METAL, ROUTE_OPENCL, ROUTE_CUDA)
MAX_SCALE_EVENTS = 200
REFERENCE_NODE = "reference@coordinator"
WRONG_SILICON = "record names the wrong silicon for its route"
RELABEL_SUFFIX = " (relabelling refused)"


@dataclass
class CoordinatorConfig:
    token: str
    state_dir: str | Path
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    tls_cert: str | None = None
    tls_key: str | None = None
    tier: int = 1
    heartbeat_interval_ms: int = 1000
    node_timeout_ms: int = 5000
    lease_ttl_ms: int = 15_000
    max_lease_age_ms: int = 600_000
    max_lease_attempts: int = 4
    sample_rate_ppm: int = 125_000
    recovery_sample_ppm: int = 500_000
    max_recovery_rounds: int = 2
    fabric_tick_ms: int = 2000
    prefill_ratio: Fraction = PREFILL_RATIO
    decode_ratio: Fraction = DECODE_RATIO
    verifier_threads: int = 2
    max_body_bytes: int = MAX_BODY_BYTES
    max_lease_bytes: int = 8 * 1024 * 1024
    max_retained_jobs: int = 256
    kernels: KernelRegistry | None = None


@dataclass
class TileResult:
    output: bytes
    digest: str
    node_id: str
    record: dict[str, Any] | None
    status: str


@dataclass
class Job:
    job_id: str
    unit: WorkUnit
    kernel: Kernel
    version: str
    prepared: Prepared
    lattice: SchedulingLattice
    tiles: list[Tile]
    submitter: str
    gate: EntitlementCheck | None
    submitted_ns: int = field(default_factory=utc_now_ns)
    results: dict[int, TileResult] = field(default_factory=dict)
    pending_checks: set[int] = field(default_factory=set)
    contested: dict[int, list[tuple[str, str]]] = field(default_factory=dict)
    checks: dict[str, int] = field(
        default_factory=lambda: {"sampled": 0, "escalation": 0, "disagreement": 0, "min-per-device": 0}
    )
    matches: int = 0
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    duplicate_agreements: int = 0
    rejected: list[dict[str, Any]] = field(default_factory=list)
    late_results: int = 0
    incidents: list[str] = field(default_factory=list)
    status: str = "running"
    error: str | None = None
    output: bytes | None = None
    receipt: dict[str, Any] | None = None
    completed_ns: int | None = None
    done: threading.Event = field(default_factory=threading.Event)
    tier_at_admission: dict[str, Any] | None = None
    grant_id: str | None = None
    scale: str | None = None

    def progress(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "kernel": self.kernel.name,
            "tiles_total": len(self.tiles),
            "tiles_done": len(self.results),
            "pending_checks": len(self.pending_checks),
            "incidents": list(self.incidents),
            "error": self.error,
            "scale": self.scale,
        }

    def bytes_held(self) -> int:
        return len(self.unit.payload) + sum(len(r.output) for r in self.results.values())


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-")[:40] or "node"


def _expected_silicon(route: str) -> str:
    return "gpu" if route in GPU_ROUTES else "cpu"


def _backend_record(selection: Any, routes: Mapping[str, Any]) -> dict[str, Any]:
    """The worker's backend selection as recorded by the coordinator (strings only, bounded)."""
    selection = selection if isinstance(selection, Mapping) else {}
    detected = [str(b)[:20] for b in selection.get("detected_backends") or [] if isinstance(b, str)][:16]
    executed = selection.get("executed_backend")
    preference = selection.get("preference")
    return {
        "requested_backend": str(selection.get("requested_backend") or "auto")[:20],
        "detected_backends": detected,
        "preference": preference if preference in PREFERENCES else "ours",
        "executed_backend": str(executed)[:20] if executed in routes else None,
        "fallback_reason": str(selection["fallback_reason"])[:300] if selection.get("fallback_reason") else None,
    }


class FleetCoordinator:
    def __init__(self, config: CoordinatorConfig) -> None:
        self.config = config
        self.state_dir = Path(config.state_dir).expanduser()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.receipts_dir = self.state_dir / "receipts"
        self.receipts_dir.mkdir(exist_ok=True)
        self.kernels = config.kernels or default_registry()
        self.auth = FleetAuth(config.token)
        self.signer = FleetSigner.from_state_dir(self.state_dir)
        self.ledger = AnchorLedger(self.state_dir / "ledger.jsonl")
        self.fleet_id = self._fleet_identity()
        self.tls = bool(config.tls_cert and config.tls_key)
        if bool(config.tls_cert) != bool(config.tls_key):
            raise FleetError("TLS needs both a certificate and a key")
        self.connectors = {CONNECTOR_FLEET_HTTP} | ({CONNECTOR_FLEET_TLS} if self.tls else set())
        self.tier: Tier = TIER_1
        self.tier_source = "default"
        self.grants: dict[str, ScaleGrant] = {}
        self.retired_grants: dict[str, str] = {}
        self._downgrade_cover: dict[int, ScaleGrant] = {}
        self.scale_events: list[ScaleEvent] = []
        self._tier_documents: set[str] = set()
        self._lock = threading.RLock()
        self.crossbar = H4Crossbar()
        self.scheduler = LeaseScheduler(
            self.crossbar,
            config.lease_ttl_ms * 1_000_000,
            config.max_lease_age_ms * 1_000_000,
            pool_budgets(self.tier.simd_lanes, config.prefill_ratio, config.decode_ratio),
        )
        self.sampling = SamplingPolicy(config.sample_rate_ppm)
        self.recovery = RecoveryChannel()
        self.baseline = BaselineChannel(self._reference_for_tile, config.recovery_sample_ppm)
        self.nodes: dict[str, NodeInfo] = {}
        self.jobs: dict[str, Job] = {}
        self.incidents: dict[str, Incident] = {}
        self._resolve_tier()
        self.gate_status: EntitlementCheck = evaluate_entitlement(self.tier, 0, 0, 0, self.connectors)
        self.started_at = iso_utc()
        self._node_credentials: dict[str, FleetAuth] = {}
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._server: FleetHTTPServer | None = None
        self._last_snapshot: str | None = None
        self._receipt_bytes = sum(p.stat().st_size for p in self.receipts_dir.glob("*.json"))
        self.verifier: ReferenceVerifier | None = None

    # ------------------------------------------------------------------ setup
    def _fleet_identity(self) -> str:
        path = self.state_dir / "fleet.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["fleet_id"]
        identity = {"fleet_id": "fleet-" + secrets.token_hex(6), "created_at": iso_utc(), "signer_key_id": self.signer.key_id}
        path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
        return identity["fleet_id"]

    def _resolve_tier(self) -> None:
        """Start at the configured tier when a grant (or Tier 1) authorises it; apply saved documents."""
        if not TIER_1.number <= self.config.tier <= SCALE_TIER_NUMBER:
            raise TierGateRejected("tier must be 1, 2, 3, 4 or 5 (Scale)")
        self.load_tier_documents()
        if self.config.tier > self.tier.number:
            target = self._authorised_tier(self.config.tier)
            if target is not None and target[0].number == self.config.tier:
                self._set_tier(target[0], f"start --tier {self.config.tier}", target[1])
            else:
                logger.warning("%s; starting at %s", scale_available_message(self.tier), self.tier.label)

    # ------------------------------------------------------------ tiers, scale
    def _valid_grants(self) -> list[ScaleGrant]:
        now = utc_now_ns()
        return [g for g in self.grants.values() if g.valid_at(now)]

    def _authorised_tier(self, number: int) -> tuple[Tier, ScaleGrant | None] | None:
        """The tier with this number if a valid grant (or Tier 1) authorises it and its connectors exist."""
        if number == TIER_1.number:
            return TIER_1, None
        candidates = []
        for grant in self._valid_grants():
            if number == SCALE_TIER_NUMBER and grant.tier_number == SCALE_TIER_NUMBER:
                candidates.append((grant.tier, grant))
            elif number < SCALE_TIER_NUMBER and grant.tier_number >= number:
                candidates.append((tier_by_number(number), grant))
        covering = self._downgrade_cover.get(number)
        if covering is not None and covering.valid_at() and number < SCALE_TIER_NUMBER:
            candidates.append((tier_by_number(number), covering))
        candidates = [c for c in candidates if c[0].connectors <= self.connectors]
        if not candidates:
            return None
        return max(candidates, key=lambda c: (c[0].warps, c[0].storage_tb, c[1].expires_at_ns if c[1] else 0))

    def _covering_tier(self, warps: int, lanes: int, storage: int) -> tuple[Tier, ScaleGrant | None] | None:
        """The lowest authorised tier above the current one whose entitlement covers this demand."""
        for number in range(min(self.tier.number + 1, SCALE_TIER_NUMBER), SCALE_TIER_NUMBER + 1):
            found = self._authorised_tier(number)
            if number == SCALE_TIER_NUMBER:
                covering = [g for g in self._valid_grants() if g.tier_number == number
                            and g.tier.connectors <= self.connectors and g.tier.covers(warps,lanes,storage)]
                if covering:
                    grant = min(covering,key=lambda g:(g.tier.warps,g.tier.storage_tb))
                    found = (grant.tier,grant)
            if found is not None and found[0].covers(warps, lanes, storage):
                return found
        return None

    def _set_tier(self, tier: Tier, why: str, grant: ScaleGrant | None = None) -> None:
        previous = self.tier
        self.tier = tier
        self.tier_source = why
        self.scheduler.pool_lanes = pool_budgets(tier.simd_lanes, self.config.prefill_ratio, self.config.decode_ratio)
        self.ledger.append(
            "tier",
            digest_json(tier.to_dict()),
            {"from": previous.name, "to": tier.name, "why": why[:200], "grant_id": grant.grant_id if grant else None},
        )
        logger.info("tier %s -> %s (%s)", previous.label, tier.label, why)

    def _demand(self, extra_warps: int = 0, extra_lanes: int = 0, extra_bytes: int = 0) -> tuple[int, int, int]:
        warps, lanes = self._footprint()
        return warps + extra_warps, lanes + extra_lanes, self._storage_bytes() + extra_bytes

    def _record_scale(self, event: ScaleEvent) -> None:
        self.scale_events.append(event)
        del self.scale_events[:-MAX_SCALE_EVENTS]
        self.ledger.append("scale", digest_json(event.to_dict()), {
            "event_id": event.event_id, "kind": event.kind, "outcome": event.outcome,
            "demand_warps": event.demand["warps"], "entitlement": event.entitlement["name"],
            "next_tier": event.next_tier, "grant_id": event.grant_id,
        })
        logger.info("scale event %s: %s %s (%s)", event.event_id, event.kind, event.outcome, event.message)

    def _admit(self, kind: str, subject: str, warps: int = 0, lanes: int = 0, extra_bytes: int = 0,
               record_queued: bool = True) -> tuple[bool, EntitlementCheck, ScaleEvent | None]:
        """Admit demand within the entitlement, or under a grant (scaling up); otherwise queue it."""
        demand_warps, demand_lanes, demand_bytes = self._demand(warps, lanes, extra_bytes)
        before = self.tier
        check = evaluate_entitlement(before, demand_warps, demand_lanes, Fraction(demand_bytes, BYTES_PER_TB), self.connectors)
        if check.missing_connectors:
            require_connectors(before, self.connectors, f"{kind} of {subject}")
        if check.within_entitlement:
            return True, check, None
        demand = {"warps": demand_warps, "lanes": demand_lanes, "storage_bytes": demand_bytes}
        entitlement = before.to_dict()
        covering = self._covering_tier(demand_warps, demand_lanes, demand_bytes)
        if covering is not None:
            tier, grant = covering
            self._set_tier(tier, f"scaled for {kind} of {subject}", grant)
            event = ScaleEvent(kind, subject, demand, entitlement, next_tier_label(before), "admitted",
                               f"scaled {before.label} -> {tier.label} under {grant.grant_id if grant else 'Tier 1'}",
                               grant.grant_id if grant else None)
            self._record_scale(event)
            check = evaluate_entitlement(tier, demand_warps, demand_lanes, Fraction(demand_bytes, BYTES_PER_TB), self.connectors)
            return True, check, event
        message = scale_available_message(before)
        nxt = tier_by_number(before.number + 1) if before.number < len(TIERS) else None
        if nxt is not None and not nxt.connectors <= self.connectors:
            message += f" (needs {', '.join(sorted(nxt.connectors - self.connectors))}: start the coordinator with --tls)"
        event = ScaleEvent(kind, subject, demand, entitlement, next_tier_label(before), "queued", message)
        if record_queued:
            self._record_scale(event)
        return False, check, event

    def load_tier_documents(self) -> int:
        """Apply grant and selection files in <state_dir>/tier that are new since the last call."""
        applied = 0
        for name, document in read_documents(self.state_dir):
            if name in self._tier_documents:
                continue
            self._tier_documents.add(name)
            try:
                if document.get("schema") == GRANT_SCHEMA:
                    self.install_grant(document, persist=False)
                elif document.get("schema") == SELECTION_SCHEMA:
                    self.select_tier(document, persist=False)
                else:
                    continue
                applied += 1
            except (ScaleGrantRejected, TierGateRejected) as exc:
                logger.warning("tier document %s not applied: %s", name, exc)
                self.ledger.append("note", digest_json(document), {"event": "tier-document-rejected", "file": name,
                                                                   "reason": str(exc)[:200]})
        return applied

    def install_grant(self, document: Mapping[str, Any], persist: bool = True) -> ScaleGrant:
        """Verify a scale grant against the coordinator owner's key and make it available to admission."""
        with self._lock:
            grant = verify_grant(document, self.signer.public_key, self.fleet_id)
            if grant.grant_id in self.retired_grants:
                raise ScaleGrantRejected(f"{grant.grant_id} was retired: {self.retired_grants[grant.grant_id]}")
            if not grant.valid_at():
                raise ScaleGrantRejected(f"{grant.grant_id} expired at {grant.to_dict()['expires_at']}")
            if persist:
                self._tier_documents.add(write_document(self.state_dir, document).name)
            if grant.grant_id not in self.grants:
                self.grants[grant.grant_id] = grant
                self.ledger.append("tier", digest_json(dict(document)), {
                    "event": "grant-installed", "grant_id": grant.grant_id, "tier": grant.tier.name,
                    "expires_at": grant.to_dict()["expires_at"],
                })
            self._admit_waiting()
            return grant

    def select_tier(self, document: Mapping[str, Any], persist: bool = True) -> Tier:
        """Apply the owner's signed tier selection: down at any time, up as far as a grant authorises."""
        with self._lock:
            body = verify_selection(document, self.signer.public_key, self.fleet_id)
            number = body["tier"]
            if number > self.tier.number or number == self.tier.number == SCALE_TIER_NUMBER:
                found = self._authorised_tier(number)
                if found is None:
                    raise ScaleGrantRejected(
                        f"{scale_available_message(self.tier)}; moving to tier {number} needs a valid grant: "
                        f"chronus-fleet tier grant --tier {'scale' if number == SCALE_TIER_NUMBER else number} --expires 30d"
                    )
                if persist:
                    self._tier_documents.add(write_document(self.state_dir, document).name)
                self._set_tier(found[0], f"tier set {body['selection_id']}", found[1])
            elif number < self.tier.number:
                # The signed selection caps existing authorization at the lower
                # tier, without modifying or reactivating the retired grant.
                covering = self._authorised_tier(number)
                self._downgrade_cover.clear()
                if number > 1 and covering is not None and covering[1] is not None:
                    self._downgrade_cover[number] = covering[1]
                if persist:
                    self._tier_documents.add(write_document(self.state_dir, document).name)
                for grant in list(self.grants.values()):
                    if grant.tier_number > number:
                        self.retired_grants[grant.grant_id] = f"downgrade to tier {number} by {body['selection_id']}"
                        del self.grants[grant.grant_id]
                self._set_tier(TIER_1 if number == 1 else tier_by_number(number), f"downgrade {body['selection_id']}")
                self._rebalance("downgrade")
            self._admit_waiting()
            return self.tier

    def _expire_grants(self) -> None:
        if self.tier.number == TIER_1.number:
            return
        if self._authorised_tier(self.tier.number) is not None and (
            self.tier.number != SCALE_TIER_NUMBER
            or any(g.tier == self.tier for g in self._valid_grants() if g.tier_number == SCALE_TIER_NUMBER)
        ):
            return
        number = self.tier.number - 1
        while number > TIER_1.number and self._authorised_tier(number) is None:
            number -= 1
        found = self._authorised_tier(number)
        tier, grant = found if found is not None else (TIER_1, None)
        self._set_tier(tier, "grant expired", grant)
        self._rebalance("expiry")

    def _rebalance(self, cause: str) -> None:
        """After a downgrade or expiry, newest machines wait until demand is within the entitlement."""
        active = sorted((n for n in self.nodes.values() if n.alive and n.state != "waiting"),
                        key=lambda n: n.joined_at, reverse=True)
        for node in active:
            warps, lanes, storage = self._demand()
            if self.tier.covers(warps, lanes, 0):
                break
            node.state = "waiting"
            self.scheduler.drop_node(node.node_id)
            event = ScaleEvent(cause, node.label, {"warps": warps, "lanes": lanes, "storage_bytes": storage},
                               self.tier.to_dict(), next_tier_label(self.tier), "queued",
                               scale_available_message(self.tier))
            self._record_scale(event)

    def _admit_waiting(self) -> None:
        """Admit waiting machines (oldest first) and queued jobs that the entitlement or a grant now covers."""
        waiting = sorted((n for n in self.nodes.values() if n.alive and n.state == "waiting"), key=lambda n: n.joined_at)
        for node in waiting:
            admitted, _, _ = self._admit("join", node.label, node.warps, node.lanes, record_queued=False)
            if not admitted:
                break
            node.state = "active"
            self.scheduler.add_node(node.node_id)
            logger.info("node %s admitted from the queue at %s", node.node_id, self.tier.label)
        for job in sorted((j for j in self.jobs.values() if j.status == "queued"), key=lambda j: j.submitted_ns):
            admitted, check, event = self._admit("job", job.job_id, extra_bytes=len(job.unit.payload), record_queued=False)
            if not admitted:
                break
            if not self._start_job(job, check, event):
                break

    @property
    def address(self) -> tuple[str, int]:
        if self._server is None:
            raise FleetError("coordinator is not running")
        host, port = self._server.server_address[:2]
        return host, port

    @property
    def url(self) -> str:
        host, port = self.address
        try:
            shown = "127.0.0.1" if not host or ipaddress.ip_address(host).is_unspecified else host
        except ValueError:
            shown = host
        return f"{'https' if self.tls else 'http'}://{shown}:{port}"

    def start(self) -> "FleetCoordinator":
        context = tls_server_context(self.config.tls_cert, self.config.tls_key) if self.tls else None
        self._server = FleetHTTPServer(
            (self.config.host, self.config.port), self.handle, self.auth, context, self.config.max_body_bytes, auth_resolver=self._request_auth
        )
        self.verifier = ReferenceVerifier(self._on_verification, self.config.verifier_threads)
        self.ledger.append("note", sha256_hex(self.fleet_id.encode()), {"event": "coordinator-start", "tier": self.tier.name})
        for target, name in ((self._server.serve_forever, "fleet-http"), (self._monitor_loop, "fleet-monitor"),
                             (self._fabric_loop, "fleet-fabric")):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)
        logger.info("coordinator %s listening on %s (%s)", self.fleet_id, self.url, self.tier.label)
        return self

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            for job in self.jobs.values():
                self._fail(job, "coordinator stopped before completion")
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self.verifier is not None:
            self.verifier.stop()
        for thread in self._threads:
            thread.join(timeout=5)

    def __enter__(self) -> "FleetCoordinator":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    # -------------------------------------------------------------- accounting
    def _footprint(self) -> tuple[int, int]:
        """Logical warps and lanes of admitted machines (waiting machines hold none)."""
        live = [n for n in self.nodes.values() if n.alive and n.state != "waiting"]
        return sum(n.warps for n in live), sum(n.lanes for n in live)

    def _storage_bytes(self) -> int:
        held = sum(job.bytes_held() for job in self.jobs.values() if job.status != "queued")
        ledger = self.ledger.path.stat().st_size if self.ledger.path.exists() else 0
        return held + self._receipt_bytes + ledger

    # ---------------------------------------------------------------- routing
    def handle(self, method: str, path: str, node_id: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        try:
            if self._stop.is_set() and method == "POST":
                return 503, {"error": "coordinator is stopping"}
            if method == "POST" and path == "/v1/join":
                return self._join(node_id, payload)
            if method == "POST" and path == "/v1/heartbeat":
                return self._heartbeat(node_id, payload)
            if method == "POST" and path == "/v1/leave":
                return self._leave(node_id, payload)
            if method == "POST" and path == "/v1/lease":
                return self._lease(node_id, payload)
            if method == "POST" and path == "/v1/result":
                return self._result(node_id, payload)
            if method == "POST" and path == "/v1/jobs":
                return self._submit(node_id, payload)
            if method == "GET" and path == "/v1/status":
                return 200, self.status()
            match = re.fullmatch(r"/v1/jobs/(job-[0-9a-f]{16})(/result)?", path)
            if method == "GET" and match:
                return self._job_view(match.group(1), bool(match.group(2)))
            return 404, {"error": f"no route {method} {path}"}
        except TierGateRejected as exc:
            return 409, {"error": str(exc), "failures": list(exc.failures)}
        except (KernelError, LatticeError) as exc:
            return 400, {"error": str(exc)}
        except FleetError as exc:
            return 409, {"error": str(exc)}

    def _request_auth(self, path, node_id):
        if path in {"/v1/heartbeat", "/v1/leave", "/v1/lease", "/v1/result"}:
            with self._lock:
                return self._node_credentials.get(node_id)
        return self.auth

    def _node(self, header_node: str, payload: Mapping[str, Any]) -> NodeInfo | None:
        node_id = payload.get("node_id")
        if node_id != header_node:
            return None
        node = self.nodes.get(node_id)
        return node if node is not None and node.alive else None

    # ------------------------------------------------------------------- join
    def _join(self, header_node: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        label = str(payload.get("label") or "node")[:100]
        owner = str(payload.get("owner") or "hyba")[:100]
        resident = require_rung(payload.get("resident_units"))
        kernels = payload.get("kernels") or {}
        if not isinstance(kernels, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in kernels.items()):
            return 400, {"error": "kernels must map names to versions"}
        routes: dict[str, dict[str, Any]] = {}
        for route, info in (payload.get("routes") or {}).items():
            if not isinstance(info, dict) or not info.get("self_test_passed"):
                continue
            silicon = info.get("silicon")
            if silicon != _expected_silicon(route):
                return 400, {"error": f"route {route} reported silicon {silicon!r}; it runs on {_expected_silicon(route)}"}
            mode = MODE_B if silicon == "gpu" else MODE_A
            verified = [k for k in info.get("verified_kernels", []) if k in kernels]
            routes[route] = {
                "silicon": silicon,
                "mode": mode,
                "device": info.get("device", {}),
                "verified_kernels": sorted(verified),
                "self_test": info.get("self_test", {}),
            }
        if not routes:
            return 400, {"error": "no self-tested route offered; nothing to join with"}
        backend = _backend_record(payload.get("backend"), routes)
        warps, lanes = lattice_footprint(resident)
        with self._lock:
            admitted, _, event = self._admit("join", f"{label} ({resident} virtual units)", warps, lanes)
            node_id = f"{_slug(label)}-{secrets.token_hex(3)}"
            vertex = self.crossbar.place(node_id)
            node = NodeInfo(
                node_id=node_id,
                label=label,
                owner=owner,
                resident_units=resident,
                warps=warps,
                lanes=lanes,
                routes=routes,
                kernels=dict(kernels),
                vertex=vertex,
                joined_at=iso_utc(),
                last_seen_ns=monotonic_ns(),
                state="active" if admitted else "waiting",
                backend=backend,
            )
            for measurement in payload.get("measurements") or []:
                if (
                    isinstance(measurement, dict)
                    and measurement.get("measured") is True
                    and measurement.get("route") in routes
                    and isinstance(measurement.get("items_per_second"), int)
                ):
                    node.throughput[(measurement["kernel"], measurement["route"])] = measurement["items_per_second"]
            self.nodes[node_id] = node
            credential = secrets.token_urlsafe(32)
            self._node_credentials[node_id] = FleetAuth(credential)
            if admitted:
                self.scheduler.add_node(node_id)
            self.ledger.append("note", digest_json({"node_id": node_id, "backend": backend}), {
                "event": "node-joined", "node_id": node_id, "label": label, "state": node.state, **backend,
            })
        logger.info("node %s joined (%s, routes %s, %s)", node_id, label, sorted(routes), node.state)
        return 200, {
            "node_id": node_id,
            "node_credential": credential,
            "fleet_id": self.fleet_id,
            "state": node.state,
            "scale": event.message if event is not None else None,
            "tier": self.tier.label,
            "crossbar_vertex": vertex,
            "heartbeat_interval_ms": self.config.heartbeat_interval_ms,
            "lease_ttl_ms": self.config.lease_ttl_ms,
            "signer_key_id": self.signer.key_id,
        }

    def _heartbeat(self, header_node: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        with self._lock:
            node = self._node(header_node, payload)
            if node is None:
                return 404, {"error": "unknown node; rejoin"}
            node.last_seen_ns = monotonic_ns()
            leases = [str(i) for i in payload.get("leases") or []]
            renewed = self.scheduler.renew(node.node_id, leases, node.last_seen_ns)
            return 200, {"renewed": renewed, "quarantined": node.quarantined}

    def _leave(self, header_node: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        with self._lock:
            node = self._node(header_node, payload)
            if node is None:
                return 404, {"error": "unknown node"}
            self._retire(node, "left", "node-left")
            return 200, {"left": node.node_id}

    # ----------------------------------------------------------------- leases
    def _lease(self, header_node: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        with self._lock:
            node = self._node(header_node, payload)
            if node is None:
                return 404, {"error": "unknown node; rejoin"}
            node.last_seen_ns = monotonic_ns()
            if node.quarantined:
                return 200, {"lease": None, "quarantined": node.quarantined, "retry_after_ms": 1000}
            if node.state == "waiting":
                return 200, {"lease": None, "state": "waiting", "scale": scale_available_message(self.tier),
                             "retry_after_ms": 1000}

            def usable(group: LeaseGroup) -> bool:
                job = self.jobs.get(group.job_id)
                return (
                    job is not None
                    and job.status == "running"
                    and node.node_id not in group.excluded
                    and node.eligible(job.kernel.name, job.version, job.unit.route)
                )

            acquired = self.scheduler.acquire(node.node_id, usable, monotonic_ns())
            if acquired is None:
                return 200, {"lease": None, "retry_after_ms": 150}
            lease, source = acquired
            job = self.jobs[lease.group.job_id]
            tiles = []
            for index in lease.group.tiles():
                tile = job.tiles[index]
                data = job.kernel.tile_input(job.prepared, tile.start, tile.stop)
                tiles.append({"index": index, "start": tile.start, "stop": tile.stop, "input_b64": b64encode(data)})
            return 200, {
                "lease": {
                    "lease_id": lease.lease_id,
                    "job_id": job.job_id,
                    "kernel": job.kernel.name,
                    "kernel_version": job.version,
                    "params": dict(job.prepared.params),
                    "route": job.unit.route,
                    "prefer": job.unit.prefer,
                    "tiles": tiles,
                    "ttl_ms": self.config.lease_ttl_ms,
                    "source": source,
                }
            }

    def _result(self, header_node: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        with self._lock:
            node = self.nodes.get(payload.get("node_id")) if payload.get("node_id") == header_node else None
            if node is None:
                return 404, {"error": "unknown node"}
            node.last_seen_ns = monotonic_ns()
            lease = self.scheduler.inflight.get(str(payload.get("lease_id")))
            if lease is None or lease.node_id != node.node_id:
                return self._late_result(node, payload)
            tiles = payload.get("tiles")
            if not isinstance(tiles, list) or any(not isinstance(item, dict) for item in tiles):
                return 400, {"error": "tiles must be an array of result objects"}
            if any(type(item.get("index")) is not int or not isinstance(item.get("record"), dict)
                   or not isinstance(item["record"].get("executed_route"), str) for item in tiles):
                return 400, {"error": "result indices and route records are malformed"}
            self.scheduler.release(lease.lease_id)
            job = self.jobs.get(lease.group.job_id)
            if job is None or job.status != "running":
                return 200, {"accepted": 0, "note": "job no longer running"}
            accepted, rejected = 0, []
            received: set[int] = set()
            for item in payload.get("tiles") or []:
                problem = self._take_tile(job, node, lease.group, item)
                if problem:
                    rejected.append(problem)
                else:
                    accepted += 1
                    received.add(int(item["index"]))
            missing = [t for t in lease.group.tiles() if t not in received]
            failure = payload.get("failure")
            if missing:
                cause = "lease-failed: " + (str(failure.get("reason"))[:300] if isinstance(failure, dict) else "incomplete")
                exclude = isinstance(failure, dict) and failure.get("kind") in ("device", "kernel")
                self._open_incident(job, _runs(lease.group, missing), node.node_id, cause, exclude_failed=exclude)
            self._maybe_finish(job)
            return 200, {"accepted": accepted, "rejected": rejected}

    def _late_result(self, node: NodeInfo, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        """A result for a lease that expired or moved: compared, never silently accepted."""
        compared = 0
        for item in payload.get("tiles") or []:
            job = self.jobs.get(str(payload.get("job_id"))) if payload.get("job_id") else None
            if job is None:
                continue
            job.late_results += 1
            try:
                index = int(item["index"])
                output = b64decode(item["output_b64"])
            except (KeyError, TypeError, ValueError):
                continue
            existing = job.results.get(index)
            if existing is not None and existing.status not in ("recovered-pending",):
                self._compare_duplicate(job, index, node.node_id, sha256_hex(output))
                compared += 1
        return 200, {"accepted": 0, "late": True, "compared": compared}

    def _take_tile(self, job: Job, node: NodeInfo, group: LeaseGroup, item: Mapping[str, Any]) -> dict[str, Any] | None:
        try:
            index = int(item["index"])
            output = b64decode(item["output_b64"])
            record = dict(item["record"])
        except (KeyError, TypeError, ValueError) as exc:
            return {"index": item.get("index") if isinstance(item, dict) else None, "reason": f"malformed tile: {exc}"}
        if index not in group.tiles():
            return {"index": index, "reason": "tile is not part of this lease"}
        if node.quarantined:
            return {"index": index, "reason": "node is quarantined"}
        digest = sha256_hex(output)
        problem = self._check_record(job, node, index, digest, item.get("output_sha256"), record)
        if problem:
            job.rejected.append({"index": index, "node_id": node.node_id, "reason": problem})
            if problem == WRONG_SILICON or problem.endswith(RELABEL_SUFFIX):
                self._quarantine(node, f"honesty rule broken on {job.job_id} tile {index}: {problem}")
            return {"index": index, "reason": problem}
        self._learn_throughput(node, job.kernel.name, record)
        if group.incident is not None:
            incident = self.incidents.get(group.incident)
            if incident is not None and incident.status == "recovering" and (job.job_id, index) in incident.expected:
                incident.recovered[(job.job_id, index)] = (node.node_id, output)
                job.results[index] = TileResult(output, digest, node.node_id, record, "recovered-pending")
                if incident.complete:
                    self._close_incident(incident)
                return None
        existing = job.results.get(index)
        if existing is None:
            job.results[index] = TileResult(output, digest, node.node_id, record, "accepted")
            if self.sampling.sampled(job.job_id, index):
                self._schedule_check(job, index, "sampled")
        else:
            self._compare_duplicate(job, index, node.node_id, digest)
        return None

    def _check_record(
        self, job: Job, node: NodeInfo, index: int, digest: str, claimed: Any, record: Mapping[str, Any]
    ) -> str | None:
        tile = job.tiles[index]
        executed = record.get("executed_route")
        if not isinstance(executed, str):
            return "record executed_route is invalid"
        if claimed != digest or record.get("output_sha256") != digest:
            return "output bytes do not match the reported digest"
        if executed not in node.routes or job.kernel.name not in node.routes[executed]["verified_kernels"]:
            return f"route {executed!r} was not self-tested for {job.kernel.name} at join"
        if record.get("silicon") != _expected_silicon(executed):
            return WRONG_SILICON
        if job.unit.route != ROUTE_AUTO and executed != job.unit.route:
            return f"requested route {job.unit.route} but executed {executed}{RELABEL_SUFFIX}"
        if record.get("executed_backend") != executed:
            return f"executed_backend {record.get('executed_backend')!r} but executed route {executed}{RELABEL_SUFFIX}"
        if record.get("requested_route") != job.unit.route or record.get("kernel") != job.kernel.name:
            return "record does not match the lease"
        if record.get("requested_backend") != job.unit.route or record.get("preference") not in PREFERENCES:
            return "record backend fields do not match the lease"
        if job.unit.prefer is not None and record.get("preference") != job.unit.prefer:
            return "record preference does not match the work unit"
        if not isinstance(record.get("detected_backends"), list) or executed not in record["detected_backends"]:
            return "record does not list the executed backend among the detected backends"
        if (type(record.get("items")) is not int or record["items"] != tile.items
                or type(record.get("duration_ns")) is not int or record["duration_ns"] < 0):
            return "record items or duration are invalid"
        for name in ("bytes_in", "bytes_out"):
            if type(record.get(name)) is not int or record[name] < 0:
                return f"record {name} is invalid"
        for name in ("started_at", "finished_at", "mode"):
            if not isinstance(record.get(name), str):
                return f"record {name} is invalid"
        if not all(isinstance(name, str) for name in record["detected_backends"]):
            return "record detected_backends must be strings"
        return None

    def _learn_throughput(self, node: NodeInfo, kernel: str, record: Mapping[str, Any]) -> None:
        rate = per_second(record["items"], record["duration_ns"])
        if rate <= 0:
            return
        key = (kernel, record["executed_route"])
        previous = node.throughput.get(key)
        node.throughput[key] = rate if previous is None else (3 * previous + rate) // 4

    # ----------------------------------------------------------- verification
    def _schedule_check(self, job: Job, index: int, reason: str) -> None:
        if index in job.pending_checks or self.verifier is None:
            return
        result = job.results[index]
        tile = job.tiles[index]
        job.pending_checks.add(index)
        job.checks[reason] = job.checks.get(reason, 0) + 1
        self.verifier.submit(
            VerificationTask(
                job_id=job.job_id,
                tile_index=index,
                node_id=result.node_id,
                kernel=job.kernel,
                params=job.prepared.params,
                tile_input=job.kernel.tile_input(job.prepared, tile.start, tile.stop),
                start=tile.start,
                stop=tile.stop,
                claimed_sha256=result.digest,
                reason=reason,
            )
        )

    def _compare_duplicate(self, job: Job, index: int, node_id: str, digest: str) -> None:
        existing = job.results[index]
        if digest == existing.digest:
            job.duplicate_agreements += 1
            return
        job.contested.setdefault(index, []).append((node_id, digest))
        self._schedule_check(job, index, "disagreement")

    def _on_verification(self, outcome: VerificationOutcome) -> None:
        task = outcome.task
        with self._lock:
            job = self.jobs.get(task.job_id)
            if job is None or job.status != "running":
                return
            job.pending_checks.discard(task.tile_index)
            if outcome.error:
                self._fail(job, f"reference route raised while verifying tile {task.tile_index}: {outcome.error}")
                return
            current = job.results[task.tile_index]
            offenders = {current.node_id} if current.digest != outcome.reference_sha256 else set()
            offenders |= {n for n, d in job.contested.pop(task.tile_index, []) if d != outcome.reference_sha256}
            if not offenders:
                job.matches += 1
                current.status = "verified-reference"
            else:
                for node_id in sorted(offenders):
                    job.mismatches.append(
                        {"tile": task.tile_index, "node_id": node_id, "reason": task.reason, "detected_at": iso_utc()}
                    )
                    node = self.nodes.get(node_id)
                    if node is not None and not node.quarantined:
                        self._quarantine(node, f"tile {task.tile_index} of {job.job_id} differed from the reference")
                if current.node_id in offenders:
                    job.results[task.tile_index] = TileResult(
                        outcome.reference_output, outcome.reference_sha256, REFERENCE_NODE, None, "reference-corrected"
                    )
                else:
                    current.status = "verified-reference"
                    job.matches += 1
                for other_index, other in job.results.items():
                    if other.node_id in offenders and other.status == "accepted":
                        self._schedule_check(job, other_index, "escalation")
            self._maybe_finish(job)

    def _quarantine(self, node: NodeInfo, reason: str) -> None:
        node.quarantined = reason
        node.state = "quarantined"
        logger.warning("quarantined %s: %s", node.node_id, reason)
        self.scheduler.drop_node(node.node_id)
        self.scheduler.add_node(node.node_id)
        self._orphan_leases(node, "quarantined")

    # --------------------------------------------------------------- recovery
    def _reference_for_tile(self, job_id: str, index: int) -> bytes:
        job = self.jobs[job_id]
        tile = job.tiles[index]
        data = job.kernel.tile_input(job.prepared, tile.start, tile.stop)
        return job.kernel.run_reference(None, job.prepared.params, data, tile.start, tile.stop)

    def _orphan_leases(self, node: NodeInfo, cause: str) -> None:
        by_job: dict[str, list[LeaseGroup]] = {}
        for lease in self.scheduler.leases_of(node.node_id):
            self.scheduler.release(lease.lease_id)
            by_job.setdefault(lease.group.job_id, []).append(lease.group)
        for job_id, groups in by_job.items():
            job = self.jobs.get(job_id)
            if job is not None and job.status == "running":
                self._open_incident(job, groups, node.node_id, cause, exclude_failed=True)

    def _retire(self, node: NodeInfo, state: str, cause: str) -> None:
        node.alive = False
        node.state = state
        self._orphan_leases(node, cause)
        self.scheduler.drop_node(node.node_id)
        self.crossbar.release(node.node_id)
        log = logger.info if state == "left" else logger.warning
        log("node %s %s (%s)", node.node_id, state, cause)

    def _open_incident(
        self,
        job: Job,
        groups: list[LeaseGroup],
        failed_node: str,
        cause: str,
        exclude_failed: bool = True,
        round_number: int = 1,
        retry_of: str | None = None,
    ) -> None:
        if not groups:
            return
        if any(g.attempt + 1 > self.config.max_lease_attempts for g in groups):
            self._fail(job, f"tiles failed {self.config.max_lease_attempts} times; last cause: {cause}")
            return
        self._transfer_from_open_incidents(groups)
        incident_id = new_incident_id()
        clean = tuple(
            LeaseGroup(g.job_id, g.first_tile, g.stop_tile, g.pool, None, g.attempt,
                       g.excluded | ({failed_node} if exclude_failed else frozenset()))
            for g in groups
        )
        faulted = FaultedState(incident_id, failed_node, cause, clean, iso_utc())
        survivors = {
            n: w
            for n, w in survivors_from(self.nodes.values(), job.kernel.name, job.version, job.unit.route, failed_node).items()
            if all(n not in g.excluded for g in clean)
        }
        incident = Incident(faulted, round=round_number, retry_of=retry_of, expected=set(faulted.tiles()))
        if survivors:
            incident.path = self.recovery.construct_recovery_path(faulted, survivors)
            self.recovery.apply(incident.path, lambda g, n: self.scheduler.requeue(g, n, front=True))
        else:
            for group in clean:
                self.scheduler.requeue(
                    LeaseGroup(group.job_id, group.first_tile, group.stop_tile, group.pool, incident_id,
                               group.attempt + 1, group.excluded),
                    None,
                )
        for _, index in faulted.tiles():
            job.results.pop(index, None)
        self.incidents[incident_id] = incident
        job.incidents.append(incident_id)
        self.ledger.append(
            "incident", digest_json(faulted.describe()), {"incident_id": incident_id, "job_id": job.job_id, "cause": cause[:200]}
        )
        logger.warning("incident %s: %s on %s (%d tiles)", incident_id, cause, failed_node, len(incident.expected))

    def _transfer_from_open_incidents(self, groups: list[LeaseGroup]) -> None:
        """Tiles of an earlier incident that fault again move to the new incident."""
        for group in groups:
            earlier = self.incidents.get(group.incident) if group.incident else None
            if earlier is None or earlier.status != "recovering":
                continue
            earlier.expected -= {(group.job_id, t) for t in group.tiles()}
            if not earlier.expected:
                earlier.status = "superseded"
                earlier.closed_at = iso_utc()
            elif earlier.complete:
                self._close_incident(earlier)

    def _close_incident(self, incident: Incident) -> None:
        incident.status = "checking"
        incident.commitment = self.recovery.commit(incident.recovered)
        recovered = dict(incident.recovered)
        thread = threading.Thread(
            target=self._blind_check, args=(incident.faulted.incident_id, incident.commitment, recovered),
            name="fleet-blind-check", daemon=True,
        )
        thread.start()

    def _blind_check(self, incident_id: str, commitment: str, recovered: dict) -> None:
        try:
            result = self.baseline.evaluate(commitment, recovered)
            error = None
        except Exception as exc:
            result, error = None, f"{type(exc).__name__}: {exc}"
        with self._lock:
            incident = self.incidents[incident_id]
            jobs = [self.jobs[j] for j in incident.jobs() if j in self.jobs]
            incident.closed_at = iso_utc()
            if result is None:
                incident.status = "failed"
                for job in jobs:
                    self._fail(job, f"blind check {incident_id} could not run: {error}")
                return
            incident.result = result
            if result.passed:
                incident.status = "verified"
                for job_id, index in recovered:
                    job = self.jobs.get(job_id)
                    if job is not None and index in job.results:
                        job.results[index].status = "recovered-blind-checked"
            else:
                incident.status = "failed-blind-check"
                for node_id in result.failed_nodes:
                    node = self.nodes.get(node_id)
                    if node is not None and not node.quarantined:
                        self._quarantine(node, f"blind check {incident_id} failed")
            self.ledger.append(
                "incident", digest_json(incident.describe()), {"incident_id": incident_id, "status": incident.status}
            )
            for job in jobs:
                if job.status != "running":
                    continue
                if not result.passed:
                    if incident.round >= self.config.max_recovery_rounds:
                        self._fail(job, f"blind check failed in {incident.round} recovery rounds")
                        continue
                    groups = [g for g in incident.faulted.groups if g.job_id == job.job_id]
                    retry = [LeaseGroup(g.job_id, g.first_tile, g.stop_tile, g.pool, None, g.attempt + 1,
                                        g.excluded | frozenset(result.failed_nodes)) for g in groups]
                    self._open_incident(job, retry, ",".join(result.failed_nodes) or "unknown",
                                        f"blind-check failure in {incident_id}", round_number=incident.round + 1,
                                        retry_of=incident_id)
                self._maybe_finish(job)

    # -------------------------------------------------------------- finishing
    def _maybe_finish(self, job: Job) -> None:
        if job.status != "running" or len(job.results) < len(job.tiles) or job.pending_checks:
            return
        if any(self.incidents[i].status in ("recovering", "checking") for i in job.incidents):
            return
        checked = {r.node_id for r in job.results.values() if r.status.startswith("verified")}
        checked |= {m["node_id"] for m in job.mismatches}
        waiting = False
        for node_id in sorted({r.node_id for r in job.results.values() if r.status == "accepted"} - checked):
            index = min(i for i, r in job.results.items() if r.node_id == node_id and r.status == "accepted")
            self._schedule_check(job, index, "min-per-device")
            waiting = True
        if waiting:
            return
        try:
            self._finalise(job)
        except Exception as exc:
            logger.exception("finalising %s failed", job.job_id)
            self._fail(job, f"could not finalise: {type(exc).__name__}: {exc}")

    def _finalise(self, job: Job) -> None:
        outputs = [job.results[i].output for i in range(len(job.tiles))]
        output = job.kernel.merge(job.prepared.params, outputs)
        job.completed_ns = utc_now_ns()
        receipt = sign_receipt(self._receipt_body(job, output), self.signer, self.ledger)
        path = self.receipts_dir / f"{receipt['receipt_id']}.json"
        text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        self._receipt_bytes += len(text.encode("utf-8"))
        job.output = output
        job.receipt = receipt
        job.status = "completed"
        job.done.set()
        self._prune()
        logger.info("job %s completed: %s", job.job_id, receipt["receipt_id"])

    def _fail(self, job: Job, reason: str) -> None:
        if job.status not in ("running", "queued"):
            return
        job.status = "failed"
        job.error = reason
        job.completed_ns = utc_now_ns()
        self.scheduler.discard_job(job.job_id)
        job.done.set()
        logger.error("job %s failed: %s", job.job_id, reason)

    def _prune(self) -> None:
        finished = sorted(
            (j for j in self.jobs.values() if j.status in ("completed", "failed")), key=lambda j: j.completed_ns or 0
        )
        for job in finished[: max(0, len(finished) - self.config.max_retained_jobs)]:
            del self.jobs[job.job_id]

    def _receipt_body(self, job: Job, output: bytes) -> dict[str, Any]:
        devices: dict[str, dict[str, Any]] = {}
        reasons: set[str] = set()
        status_counts: dict[str, int] = {}
        for index in range(len(job.tiles)):
            result = job.results[index]
            status_counts[result.status] = status_counts.get(result.status, 0) + 1
            if result.record is None:
                continue
            record = result.record
            node = self.nodes.get(result.node_id)
            entry = devices.setdefault(
                result.node_id,
                {
                    "node_id": result.node_id,
                    "label": node.label if node else result.node_id,
                    "owner": node.owner if node else None,
                    "routes_executed": {},
                    "silicon": [],
                    "modes": [],
                    "devices": {},
                    "tiles": 0,
                    "items": 0,
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "exec_ns": 0,
                    "verified_tiles": 0,
                    "verified_items": 0,
                    "first_started_at": record["started_at"],
                    "last_finished_at": record["finished_at"],
                    "fallback_reasons": 0,
                    "measured": True,
                    "backend": dict(node.backend) if node else {},
                    "executed_backends": {},
                    "preferences": [],
                    "detected_backends": [],
                },
            )
            route = record["executed_route"]
            entry["routes_executed"][route] = entry["routes_executed"].get(route, 0) + 1
            if record["silicon"] not in entry["silicon"]:
                entry["silicon"].append(record["silicon"])
            if record["mode"] not in entry["modes"]:
                entry["modes"].append(record["mode"])
            if node is not None and route in node.routes:
                entry["devices"][route] = node.routes[route].get("device", {})
            entry["tiles"] += 1
            entry["items"] += record["items"]
            entry["bytes_in"] += record["bytes_in"]
            entry["bytes_out"] += record["bytes_out"]
            entry["exec_ns"] += record["duration_ns"]
            if result.status.startswith(("verified", "recovered-blind")):
                entry["verified_tiles"] += 1
                entry["verified_items"] += record["items"]
            entry["first_started_at"] = min(entry["first_started_at"], record["started_at"])
            entry["last_finished_at"] = max(entry["last_finished_at"], record["finished_at"])
            entry["fallback_reasons"] += 1 if record.get("fallback_reason") else 0
            backend_name = record.get("executed_backend") or route
            entry["executed_backends"][backend_name] = entry["executed_backends"].get(backend_name, 0) + 1
            if record.get("preference") not in entry["preferences"]:
                entry["preferences"].append(record.get("preference"))
            for name in record.get("detected_backends") or []:
                if name not in entry["detected_backends"]:
                    entry["detected_backends"].append(name)
            if record.get("fallback_reason"):
                reasons.add(str(record["fallback_reason"])[:300])
        total_items = sum(d["items"] for d in devices.values()) or 1
        for entry in devices.values():
            entry["items_per_second"] = per_second(entry["items"], entry["exec_ns"])
            entry["share_of_items_ppm"] = entry["items"] * 1_000_000 // total_items
            entry["silicon"].sort()
            entry["modes"].sort()
            entry["detected_backends"].sort()
        executed: dict[str, int] = {}
        for entry in devices.values():
            for route, count in entry["routes_executed"].items():
                executed[route] = executed.get(route, 0) + count
        tile_digests = [job.results[i].digest for i in range(len(job.tiles))]
        lattice = job.lattice.describe()
        lattice.update({"tiles": len(job.tiles), "tile_merkle_root": merkle_root(tile_digests)})
        checked = job.matches + len({m["tile"] for m in job.mismatches})
        return {
            "schema": RECEIPT_SCHEMA,
            "fleet_id": self.fleet_id,
            "job_id": job.job_id,
            "submitter": job.submitter,
            "work_unit": {
                "digest": job.unit.digest(),
                "kernel": job.kernel.name,
                "kernel_version": job.version,
                "params": dict(job.prepared.params),
                "payload_sha256": job.unit.payload_sha256,
                "payload_bytes": len(job.unit.payload),
                "route_requested": job.unit.route,
                "pool": job.unit.pool,
                "label": job.unit.label,
            },
            "result": {"sha256": sha256_hex(output), "bytes": len(output)},
            "lattice": lattice,
            "tier": {
                "entitlement": job.tier_at_admission,
                "check_at_admission": job.gate.to_dict() if job.gate else None,
                "grant_id": job.grant_id,
            },
            "routes": {"requested": job.unit.route, "executed_tiles": executed},
            "backend": {
                "requested_backend": job.unit.route,
                "preference": job.unit.prefer or "each worker's --prefer",
                "executed_backends": executed,
                "detected_backends": {k: devices[k]["detected_backends"] for k in sorted(devices)},
                "fallback_reasons": sorted(reasons)[:20],
            },
            "devices": [devices[k] for k in sorted(devices)],
            "verification": {
                "policy": self.sampling.describe(),
                "summary": {
                    "tiles": len(job.tiles),
                    "tiles_checked_against_reference": checked,
                    "matches": job.matches,
                    "mismatches": len(job.mismatches),
                    "checks_by_reason": dict(sorted(job.checks.items())),
                    "duplicate_agreements": job.duplicate_agreements,
                    "rejected_results": len(job.rejected),
                    "late_results": job.late_results,
                    "tile_status": dict(sorted(status_counts.items())),
                },
                "mismatches": job.mismatches,
                "rejected": job.rejected[:100],
            },
            "recovery": [self.incidents[i].describe() for i in job.incidents],
            "timing": {
                "submitted_at": iso_utc(job.submitted_ns),
                "completed_at": iso_utc(job.completed_ns),
                "wall_ns": (job.completed_ns or 0) - job.submitted_ns,
            },
            "honesty": dict(HONESTY),
        }

    # -------------------------------------------------------------- jobs API
    def _submit(self, header_node: str, payload: Mapping[str, Any]) -> tuple[int, Mapping[str, Any]]:
        unit = WorkUnit.from_wire(payload.get("work_unit") or {})
        job = self.submit(unit, submitter=str(payload.get("submitter") or header_node)[:100])
        return 202, {"job_id": job.job_id, "tiles": len(job.tiles), "lattice": job.lattice.describe()}

    def submit(self, unit: WorkUnit, submitter: str = "local") -> Job:
        if self._stop.is_set():
            raise FleetError("coordinator is stopping")
        """Admit a job (scaling under a grant when needed) or queue it until a grant covers it."""
        kernel = self.kernels.get(unit.kernel, unit.kernel_version)
        prepared = kernel.prepare(unit.params, unit.payload)
        lattice = SchedulingLattice(unit.virtual_units)
        tiles = lattice.plan(prepared.items)
        with self._lock:
            if self._stop.is_set():
                raise FleetError("coordinator is stopping")
            offering = [n for n in self.nodes.values() if n.offers(kernel.name, kernel.version, unit.route)]
            if not offering:
                what = f"route {unit.route}" if unit.route != ROUTE_AUTO else "a verified route"
                raise FleetError(
                    f"no live node offers {what} for kernel {kernel.name} v{kernel.version}; failing closed"
                )
            if self.scheduler.pool_lanes.get(unit.pool, 0) < 1:
                raise TierGateRejected(f"pool {unit.pool} has no lanes under {self.tier.label} (P3 ratios)")
            job_id = "job-" + secrets.token_hex(8)
            job = Job(job_id, unit, kernel, kernel.version, prepared, lattice, tiles, submitter, None, status="queued")
            self.jobs[job_id] = job
            queued_before = any(j.status == "queued" and j is not job for j in self.jobs.values())
            if queued_before:
                job.scale = scale_available_message(self.tier)
                return job
            admitted, check, event = self._admit("job", job_id, extra_bytes=len(unit.payload))
            if not admitted:
                job.scale = event.message if event else scale_available_message(self.tier)
                return job
            if not self._start_job(job, check, event):
                job.scale = f"waiting for an admitted machine; {scale_available_message(self.tier)}"
        return job

    def _start_job(self, job: Job, check: EntitlementCheck, event: ScaleEvent | None) -> bool:
        """Plan an admitted job onto the admitted machines; False while only waiting machines offer it."""
        unit, kernel = job.unit, job.kernel
        eligible = [n for n in self.nodes.values() if n.eligible(kernel.name, kernel.version, unit.route)]
        if not eligible:
            return False
        pool_lanes = self.scheduler.pool_lanes.get(unit.pool, 0)
        job.gate = check
        job.tier_at_admission = self.tier.to_dict()
        job.grant_id = event.grant_id if event is not None else None
        job.scale = event.message if event is not None else None
        job.status = "running"
        weights = {n.node_id: n.weight(kernel.name, unit.route)[0] for n in eligible}
        min_groups = max(
            -(-len(unit.payload) // self.config.max_lease_bytes),
            -(-len(job.tiles) // pool_lanes),
        )
        self.scheduler.plan(job.job_id, len(job.tiles), unit.pool, weights, min_groups=min_groups)
        return True

    def _job_view(self, job_id: str, with_result: bool) -> tuple[int, Mapping[str, Any]]:
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None:
                return 404, {"error": "unknown job"}
            view = job.progress()
            if with_result and job.status == "completed":
                view["output_b64"] = b64encode(job.output or b"")
                view["receipt"] = job.receipt
            return 200, view

    def wait(self, job_id: str, timeout: float | None = None) -> Job:
        job = self.jobs[job_id]
        job.done.wait(timeout)
        return job

    # ---------------------------------------------------------- fabric loops
    def _monitor_loop(self) -> None:
        timeout = self.config.node_timeout_ms * 1_000_000
        while not self._stop.wait(0.2):
            with self._lock:
                now = monotonic_ns()
                for node in list(self.nodes.values()):
                    if node.alive and now - node.last_seen_ns > timeout:
                        self._retire(node, "lost", "node-lost: heartbeat timeout")
                for lease in self.scheduler.expired(now):
                    job = self.jobs.get(lease.group.job_id)
                    if job is not None and job.status == "running":
                        self._open_incident(job, [lease.group], lease.node_id, "lease-expired", exclude_failed=False)

    def snapshot(self) -> dict[str, Any]:
        """Fabric state without timestamps, so its digest changes only when the state does."""
        warps, lanes = self._footprint()
        return {
            "fleet_id": self.fleet_id,
            "tier": self.tier.name,
            "active_warps": warps,
            "simd_lanes": lanes,
            "connectors": sorted(self.connectors),
            "within_entitlement": self.gate_status.within_entitlement,
            "nodes": sorted(
                [n.node_id, n.state, n.resident_units, sorted(n.routes), n.quarantined or ""] for n in self.nodes.values()
            ),
            "jobs": sorted([j.job_id, j.status, len(j.results), len(j.tiles)] for j in self.jobs.values()),
            "queues": self.scheduler.queue_lengths(),
            "inflight": sorted(self.scheduler.inflight),
            "incidents": sorted([i, inc.status] for i, inc in self.incidents.items()),
        }

    def run_fabric_tick(self) -> EntitlementCheck:
        """One pass of the spec's run_fabric loop: grants, expiry, queue, entitlement, snapshot, anchor."""
        with self._lock:
            self.load_tier_documents()
            self._expire_grants()
            self._admit_waiting()
            warps, lanes = self._footprint()
            evaluation = evaluate_entitlement(
                self.tier, warps, lanes, Fraction(self._storage_bytes(), BYTES_PER_TB), self.connectors
            )
            self.gate_status = evaluation
            if not evaluation.within_entitlement:
                self._rebalance("fabric")
            digest = digest_json(self.snapshot())
            if digest != self._last_snapshot:
                self.ledger.append(
                    "fabric_snapshot",
                    digest,
                    {"tier": self.tier.name, "within_entitlement": evaluation.within_entitlement,
                     "live_nodes": sum(n.alive for n in self.nodes.values())},
                )
                self._last_snapshot = digest
            return evaluation

    def tier_status(self) -> dict[str, Any]:
        """Current tier, entitlement, demand and whether (and how) the fleet can scale."""
        with self._lock:
            warps, lanes = self._footprint()
            waiting = [n for n in self.nodes.values() if n.alive and n.state == "waiting"]
            queued = [j for j in self.jobs.values() if j.status == "queued"]
            demand_warps = warps + sum(n.warps for n in waiting)
            demand_lanes = lanes + sum(n.lanes for n in waiting)
            storage = self._storage_bytes() + sum(len(j.unit.payload) for j in queued)
            within = self.tier.covers(demand_warps, demand_lanes, storage)
            nxt = next_tier_label(self.tier)
            authorised = self._covering_tier(demand_warps, demand_lanes, storage) if not within else None
            now = utc_now_ns()
            return {
                "current": self.tier.to_dict(),
                "selected_by": self.tier_source,
                "entitlement": {"logical_warps": self.tier.warps, "logical_lanes": self.tier.simd_lanes,
                                "storage_tb": self.tier.storage_tb, "kind": self.tier.to_dict()["kind"]},
                "demand": {
                    "logical_warps": demand_warps,
                    "logical_lanes": demand_lanes,
                    "admitted_logical_warps": warps,
                    "storage_bytes": storage,
                    "waiting_machines": len(waiting),
                    "queued_jobs": len(queued),
                },
                "within_entitlement": within,
                "scale_available": True,
                "next_tier": nxt,
                "scale": scale_available_message(self.tier),
                "scale_authorised": authorised[1].grant_id if authorised and authorised[1] else None,
                "grants": [g.to_dict(now) for g in sorted(self.grants.values(), key=lambda g: g.issued_at_ns)],
                "retired_grants": dict(self.retired_grants),
                "scale_events": [e.to_dict() for e in self.scale_events[-20:]],
            }

    def _fabric_loop(self) -> None:
        interval = self.config.fabric_tick_ms / 1000
        while not self._stop.is_set():
            try:
                self.run_fabric_tick()
            except Exception:
                logger.exception("fabric tick failed")
            self._stop.wait(interval)

    # ----------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        with self._lock:
            warps, lanes = self._footprint()
            seq, head = self.ledger.head
            return {
                "fleet_id": self.fleet_id,
                "started_at": self.started_at,
                "tier": self.tier_status(),
                "entitlement_check": self.gate_status.to_dict(),
                "composed_lattice": {
                    "logical_warps": warps,
                    "logical_lanes": lanes,
                    "label": LATTICE_LABEL,
                },
                "pools": {
                    "lanes": dict(self.scheduler.pool_lanes),
                    "in_flight": dict(self.scheduler.pool_inflight),
                    "prefill_ratio": str(self.config.prefill_ratio),
                    "decode_ratio": str(self.config.decode_ratio),
                },
                "crossbar": {"graph": "H4 600-cell", "diameter": max_h4_diameter()},
                "connectors": sorted(self.connectors),
                "tls": self.tls,
                "signer": self.signer.describe(),
                "nodes": [n.public() for n in sorted(self.nodes.values(), key=lambda n: n.node_id)],
                "jobs": [j.progress() for j in sorted(self.jobs.values(), key=lambda j: j.submitted_ns)][-50:],
                "queues": self.scheduler.queue_lengths(),
                "leases_in_flight": len(self.scheduler.inflight),
                "incidents": [inc.describe() for inc in list(self.incidents.values())[-20:]],
                "ledger": {"path": str(self.ledger.path), "entries": seq, "head": head},
                "verification": self.sampling.describe(),
                "pid": os.getpid(),
            }


def _runs(group: LeaseGroup, tiles: list[int]) -> list[LeaseGroup]:
    """Contiguous runs of the given tiles, as groups inheriting group's pool and attempts."""
    runs: list[LeaseGroup] = []
    for index in sorted(tiles):
        if runs and runs[-1].stop_tile == index:
            runs[-1] = LeaseGroup(group.job_id, runs[-1].first_tile, index + 1, group.pool, group.incident,
                                  group.attempt, group.excluded)
        else:
            runs.append(LeaseGroup(group.job_id, index, index + 1, group.pool, group.incident, group.attempt,
                                   group.excluded))
    return runs
