# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""A fleet worker: lends one machine's verified routes to the fleet.

On start the worker detects every backend (probe, then the known-answer
self-test) and times the verified kernels, then selects one backend from the
operator's option (``--backend``, ``--prefer ours|host``; see
``chronus.fleet.backends``). A named backend is the only one offered, or the
worker fails closed before joining; with ``auto`` every verified backend is
offered and ``auto`` work runs where the preference points (``ours``: the
Chronus iGPU, even when the host has a GPU). Each tile record carries
requested_backend, detected_backends, preference, executed_backend and
fallback_reason.

If the fleet is at its tier's entitlement the worker still joins and waits,
heartbeating, until a scale grant admits it.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from chronus.fleet.adapters import AdapterRegistry, PreparedRoutes
from chronus.fleet.errors import AuthenticationError
from chronus.fleet.auth import FleetAuth
from chronus.fleet.backends import BACKEND_AUTO, DEFAULT_PREFERENCE, BackendSelection, check_backend, check_preference
from chronus.fleet.canonical import b64decode, b64encode
from chronus.fleet.capacity import HostCapacity, discover_host
from chronus.fleet.errors import DeviceUnavailableError, FleetError, KernelError, TransportError
from chronus.fleet.kernels import KernelRegistry, default_registry
from chronus.fleet.lattice import DEFAULT_VIRTUAL_UNITS, require_rung
from chronus.fleet.transport import FleetClient

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    coordinator_url: str
    token: str
    label: str = field(default_factory=socket.gethostname)
    owner: str = "hyba"
    resident_units: int = DEFAULT_VIRTUAL_UNITS
    routes: list[str] | None = None
    backend: str = BACKEND_AUTO
    prefer: str = DEFAULT_PREFERENCE
    tls_ca: str | None = None
    measure: bool = True
    measure_budget_ms: int = 200
    poll_interval_ms: int = 150
    retry_interval_ms: int = 1000


class FleetWorker:
    def __init__(
        self,
        config: WorkerConfig,
        kernels: KernelRegistry | None = None,
        adapters: AdapterRegistry | None = None,
        host: HostCapacity | None = None,
    ) -> None:
        require_rung(config.resident_units)
        check_backend(config.backend)
        check_preference(config.prefer)
        self.config = config
        self.kernels = kernels or default_registry()
        self.adapters = adapters or AdapterRegistry(config.routes)
        self.host = host or discover_host()
        self.auth = FleetAuth(config.token)
        self._node_auth = None
        self.node_id: str | None = None
        self.state: str | None = None
        self.prepared: PreparedRoutes | None = None
        self.selection: BackendSelection | None = None
        self.heartbeat_interval = 1.0
        self.stats = {"leases": 0, "tiles": 0, "failures": 0, "rejoins": 0}
        self._stop = threading.Event()
        self._active: set[str] = set()
        self._active_lock = threading.Lock()
        self._heartbeat_thread: threading.Thread | None = None
        self._rejoin = threading.Event()

    # ------------------------------------------------------------ preparation
    def prepare(self) -> PreparedRoutes:
        self.prepared = self.adapters.prepare(
            self.kernels, measure=self.config.measure, budget_ns=self.config.measure_budget_ms * 1_000_000
        )
        self.selection = self.adapters.selection(self.config.backend, self.config.prefer)
        if self.selection.ok and self.config.backend != BACKEND_AUTO:
            self.adapters.restrict([self.selection.executed_backend])
        return self.prepared

    def offered_routes(self) -> set[str]:
        return set(self.adapters.routes())

    def join_payload(self) -> dict[str, Any]:
        prepared = self.prepared or self.prepare()
        tests = {record.route: record for record in prepared.self_tests}
        routes: dict[str, Any] = {}
        unavailable: dict[str, str] = {}
        offered = self.offered_routes()
        for capability in prepared.capabilities:
            test = tests.get(capability.route)
            if capability.route not in offered:
                unavailable[capability.route] = f"not selected (--backend {self.config.backend})"
                continue
            if not capability.available:
                unavailable[capability.route] = capability.reason or "unavailable"
                continue
            if test is None or not test.passed:
                unavailable[capability.route] = f"self-test failed: {test.error if test else 'not run'}"
                continue
            routes[capability.route] = {
                "silicon": capability.silicon,
                "mode": capability.mode,
                "device": capability.device,
                "verified_kernels": test.verified_kernels,
                "self_test_passed": True,
                "self_test": {
                    "known_answers_matched": sum(1 for r in test.results if r.get("match")),
                    "started_at": test.started_at,
                    "finished_at": test.finished_at,
                },
            }
        return {
            "label": self.config.label,
            "owner": self.config.owner,
            "resident_units": self.config.resident_units,
            "host_capacity": self.host.as_dict(),
            "kernels": {k.name: k.version for k in self.kernels},
            "routes": routes,
            "unavailable_routes": unavailable,
            "measurements": [m.to_dict() for m in prepared.measurements if m.route in routes],
            "backend": self.selection.to_dict() if self.selection else None,
        }

    def _client(self, node_id: str) -> FleetClient:
        auth = self.auth if node_id.startswith("join:") else self._node_auth
        if auth is None:
            raise AuthenticationError("worker has no node credential; rejoin required")
        return FleetClient(self.config.coordinator_url, auth, node_id, self.config.tls_ca)

    def join(self) -> dict[str, Any]:
        payload = self.join_payload()
        if self.selection is not None and not self.selection.ok:
            raise DeviceUnavailableError(
                f"backend {self.config.backend} (prefer={self.config.prefer}): {self.selection.fallback_reason}"
            )
        if not payload["routes"]:
            raise DeviceUnavailableError(f"no route passed its self-test: {payload['unavailable_routes']}")
        response = self._client("join:" + self.config.label[:60]).post("/v1/join", payload)
        self._node_auth = FleetAuth(response["node_credential"])
        self.node_id = response["node_id"]
        self.state = response.get("state", "active")
        if self.state == "waiting":
            logger.warning("joined and waiting: %s", response.get("scale"))
        self.heartbeat_interval = max(0.1, response.get("heartbeat_interval_ms", 1000) / 1000)
        self._rejoin.clear()
        logger.info("joined %s as %s (routes %s)", response.get("fleet_id"), self.node_id, sorted(payload["routes"]))
        return response

    # -------------------------------------------------------------- main loop
    def run(self) -> None:
        if self.prepared is None:
            self.prepare()
        while not self._stop.is_set():
            try:
                self.join()
                break
            except TransportError as exc:
                logger.warning("join refused or coordinator unreachable: %s; retrying", exc)
                self._stop.wait(self.config.retry_interval_ms / 1000)
        if self._stop.is_set():
            return
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="fleet-heartbeat", daemon=True)
        self._heartbeat_thread.start()
        try:
            while not self._stop.is_set():
                if self._rejoin.is_set():
                    self._try_rejoin()
                    continue
                try:
                    response = self._client(self.node_id).post("/v1/lease", {"node_id": self.node_id})
                except AuthenticationError:
                    self._rejoin.set()
                    continue
                except TransportError as exc:
                    self._on_transport_error(exc)
                    continue
                lease = response.get("lease")
                self.state = response.get("state", self.state)
                if not lease:
                    self._stop.wait(response.get("retry_after_ms", self.config.poll_interval_ms) / 1000)
                    continue
                self._work(lease)
        finally:
            self._stop.set()

    def _on_transport_error(self, exc: TransportError) -> None:
        if exc.status == 404:
            self._rejoin.set()
        else:
            logger.warning("coordinator unreachable: %s", exc)
            self._stop.wait(self.config.retry_interval_ms / 1000)

    def _try_rejoin(self) -> None:
        try:
            self.join()
            self.stats["rejoins"] += 1
        except (TransportError, FleetError) as exc:
            logger.warning("rejoin failed: %s", exc)
            self._stop.wait(self.config.retry_interval_ms / 1000)

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self.heartbeat_interval):
            if self._rejoin.is_set() or self.node_id is None:
                continue
            with self._active_lock:
                leases = sorted(self._active)
            try:
                self._client(self.node_id).post("/v1/heartbeat", {"node_id": self.node_id, "leases": leases})
            except AuthenticationError:
                self._rejoin.set()
            except TransportError as exc:
                if exc.status == 404:
                    self._rejoin.set()
            except FleetError as exc:
                logger.warning("heartbeat failed: %s", exc)

    # -------------------------------------------------------------- execution
    def _work(self, lease: dict[str, Any]) -> None:
        lease_id = lease["lease_id"]
        with self._active_lock:
            self._active.add(lease_id)
        try:
            payload = self.execute_lease(lease)
            try:
                self._client(self.node_id).post("/v1/result", payload)
            except AuthenticationError:
                self._rejoin.set()
            except TransportError as exc:
                self._on_transport_error(exc)
        finally:
            with self._active_lock:
                self._active.discard(lease_id)

    def execute_lease(self, lease: dict[str, Any]) -> dict[str, Any]:
        """Run every tile of a lease; on the first refusal stop and report the rest as failed."""
        results: list[dict[str, Any]] = []
        failure = None
        self.stats["leases"] += 1
        try:
            kernel = self.kernels.get(lease["kernel"], lease["kernel_version"])
        except KernelError as exc:
            kernel, failure = None, {"kind": "kernel", "reason": str(exc)}
        if kernel is not None:
            params = lease["params"]
            for tile in lease["tiles"]:
                if self._stop.is_set():
                    failure = {"kind": "stopped", "reason": "worker stopping"}
                    break
                try:
                    data = b64decode(tile["input_b64"])
                    prefer = lease.get("prefer") or self.config.prefer
                    adapter, fallback = self.adapters.select(
                        lease["route"], kernel, params, data, tile["start"], tile["stop"], prefer=prefer
                    )
                    output, record = adapter.execute(
                        kernel, params, data, tile["start"], tile["stop"],
                        requested_route=lease["route"], tile_index=tile["index"], fallback_reason=fallback,
                        preference=prefer,
                        detected_backends=self.selection.detected_backends if self.selection else (),
                    )
                except DeviceUnavailableError as exc:
                    failure = {"kind": "device", "reason": str(exc)}
                    break
                except (KernelError, ValueError) as exc:
                    failure = {"kind": "kernel", "reason": f"{type(exc).__name__}: {exc}"}
                    break
                except Exception as exc:
                    logger.exception("tile %s failed", tile.get("index"))
                    failure = {"kind": "error", "reason": f"{type(exc).__name__}: {exc}"}
                    break
                results.append(
                    {
                        "index": tile["index"],
                        "output_b64": b64encode(output),
                        "output_sha256": record.output_sha256,
                        "record": record.to_dict(),
                    }
                )
                self.stats["tiles"] += 1
        if failure:
            self.stats["failures"] += 1
        return {
            "node_id": self.node_id,
            "lease_id": lease["lease_id"],
            "job_id": lease["job_id"],
            "tiles": results,
            "failure": failure,
        }

    # -------------------------------------------------------------- shutdown
    def stop(self, leave: bool = True) -> None:
        self._stop.set()
        if leave and self.node_id and not self._rejoin.is_set():
            try:
                self._client(self.node_id).post("/v1/leave", {"node_id": self.node_id})
            except FleetError as exc:
                logger.info("leave not acknowledged: %s", exc)

    def start_thread(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, name=f"fleet-worker-{self.config.label}", daemon=True)
        thread.start()
        return thread

    def wait_joined(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic_ns() + int(timeout * 1e9)
        while self.node_id is None and time.monotonic_ns() < deadline and not self._stop.is_set():
            self._stop.wait(0.05)
        return self.node_id is not None
