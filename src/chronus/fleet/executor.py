# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""FleetExecutor: the Python API for running work on the fleet.

    from chronus.fleet import FleetExecutor, WorkUnit

    with FleetExecutor("https://imac.local:8740", token_file="~/.chronus/fleet/token",
                       tls_ca="~/.chronus/fleet/tls/coordinator-cert.pem") as fleet:
        result = fleet.submit(WorkUnit(kernel="m15_fold", payload=data))
        result.output   # bytes, identical to the reference route's output
        result.receipt  # ML-DSA-65 signed, ledger-anchored receipt (dict)

``submit`` returns only after the receipt has been verified locally: the
signature against the coordinator key pinned when the executor connected, the
result bytes against the signed digest and the work unit against its digest.
Anything else raises. The API is generic: callers bring their own kernels
(registered on every machine through ``CHRONUS_FLEET_KERNELS``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chronus.fleet.auth import FleetAuth, load_token, new_token
from chronus.fleet.canonical import b64decode
from chronus.fleet.errors import JobFailedError, TransportError, VerificationError
from chronus.fleet.receipts import ReceiptCheck, verify_receipt
from chronus.fleet.transport import FleetClient
from chronus.fleet.workunit import WorkUnit


@dataclass
class FleetResult:
    job_id: str
    output: bytes
    receipt: dict[str, Any]
    check: ReceiptCheck

    @property
    def verified(self) -> bool:
        return self.check.valid


@dataclass
class _Embedded:
    coordinator: Any
    workers: list[Any] = field(default_factory=list)


class FleetExecutor:
    def __init__(
        self,
        coordinator_url: str,
        *,
        token: str | None = None,
        token_file: str | Path | None = None,
        tls_ca: str | None = None,
        name: str = "executor",
        public_key: str | bytes | None = None,
        poll_interval: float = 0.05,
    ) -> None:
        self.auth = FleetAuth(load_token(token, token_file))
        self.client = FleetClient(coordinator_url, self.auth, f"client:{name}"[:100], tls_ca)
        self.name = name
        self.poll_interval = poll_interval
        self._embedded: _Embedded | None = None
        if public_key is None:
            public_key = self.client.get("/v1/status")["signer"]["public_key"]
        self.public_key = bytes.fromhex(public_key) if isinstance(public_key, str) else bytes(public_key)

    @classmethod
    def embedded(
        cls,
        state_dir: str | Path,
        *,
        token: str | None = None,
        local_workers: int = 0,
        worker_routes: list[str] | None = None,
        measure: bool = False,
        host: str = "127.0.0.1",
        port: int = 0,
        **coordinator_options: Any,
    ) -> "FleetExecutor":
        """Start a coordinator (and optional in-process workers) and connect to it."""
        from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator
        from chronus.fleet.worker import FleetWorker, WorkerConfig

        token = token or new_token()
        coordinator = FleetCoordinator(
            CoordinatorConfig(token=token, state_dir=state_dir, host=host, port=port, **coordinator_options)
        ).start()
        embedded = _Embedded(coordinator)
        try:
            for i in range(local_workers):
                worker = FleetWorker(
                    WorkerConfig(coordinator.url, token, label=f"local-{i}", routes=worker_routes, measure=measure)
                )
                worker.start_thread()
                embedded.workers.append(worker)
                if not worker.wait_joined(60):
                    raise TransportError(f"in-process worker local-{i} did not join")
            executor = cls(coordinator.url, token=token, name="embedded")
        except Exception:
            for worker in embedded.workers:
                worker.stop()
            coordinator.stop()
            raise
        executor._embedded = embedded
        return executor

    @property
    def coordinator(self) -> Any:
        return self._embedded.coordinator if self._embedded else None

    def submit_async(self, unit: WorkUnit) -> str:
        response = self.client.post("/v1/jobs", {"work_unit": unit.to_wire(), "submitter": self.name})
        return response["job_id"]

    def result(self, job_id: str, unit: WorkUnit | None = None, timeout: float | None = None) -> FleetResult:
        deadline = None if timeout is None else time.monotonic_ns() + int(timeout * 1e9)
        while True:
            view = self.client.get(f"/v1/jobs/{job_id}/result")
            if view["status"] == "completed":
                break
            if view["status"] == "failed":
                raise JobFailedError(f"job {job_id} failed: {view.get('error')}", job_id)
            if deadline is not None and time.monotonic_ns() > deadline:
                raise JobFailedError(f"job {job_id} did not finish within {timeout} s", job_id)
            time.sleep(self.poll_interval)
        output = b64decode(view["output_b64"])
        receipt = view["receipt"]
        check = verify_receipt(
            receipt,
            public_key=self.public_key,
            output=output,
            work_unit_digest=unit.digest() if unit is not None else None,
        )
        if not check.valid:
            raise VerificationError(f"receipt for {job_id} does not verify: {'; '.join(check.reasons)}")
        return FleetResult(job_id, output, receipt, check)

    def submit(self, unit: WorkUnit, timeout: float | None = None) -> FleetResult:
        """Run a work unit across the fleet and return its verified result and receipt."""
        return self.result(self.submit_async(unit), unit, timeout)

    def status(self) -> dict[str, Any]:
        return self.client.get("/v1/status")

    def close(self) -> None:
        if self._embedded is not None:
            for worker in self._embedded.workers:
                worker.stop()
            self._embedded.coordinator.stop()
            self._embedded = None

    def __enter__(self) -> "FleetExecutor":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
