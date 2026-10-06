"""Production-shaped Chronus control plane and evidence-bound transaction loop.

Lifecycle: attach → probe → negotiate → ready → (submit/poll/cancel) → draining
→ detached. Failures move to failed/recovering with bounded transitions.

Policies:
  * standalone_software — CPU/software adapter only
  * preferred_accelerator — physical if available, else software with reason
  * required_adapter / required_device — fail closed when target missing

Trust:
  * runtime_signed — content-addressed / optional HMAC chain (default)
  * device_observed — adapter completed events
  * hardware_rooted — never claimed without a verified mechanism
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from .abi import (
    ABI_VERSION,
    AdmissionRecord,
    DeliveryMode,
    ExecutionPolicy,
    ExecutionReceipt,
    PortablePackage,
    RuntimeState,
    TrustClass,
    Workload,
    WorkloadKind,
    WorkloadResult,
    canonical_json,
    digest_json,
)
from .adapters import Adapter, AdapterUnavailable, default_adapters
from .evidence import EvidenceLedger
from .memory import VirtualMemoryPlane
from .verifier import verify_workload_result


class RuntimeInvariantError(RuntimeError):
    """Control-plane or policy invariant violated."""


@dataclass
class Quota:
    """Per-tenant admission quota.

    ``submitted`` counts admitted workloads; ``submitted_bytes`` counts their
    declared input bytes (canonical JSON of the workload input). Both are
    enforced at admission — a quota field that is never checked would be a
    claim, not a control.
    """

    max_workloads: int = 32
    max_bytes: int = 256 * 1024 * 1024
    submitted: int = 0
    submitted_bytes: int = 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeConfig:
    """Lightweight config object accepted by RuntimeDaemon(config=...) or positional."""

    def __init__(
        self,
        store_dir: str | Path | None = None,
        store_root: str | Path | None = None,
        preferred_adapter_id: str | None = None,
        hmac_key: bytes | str | None = None,
        **kwargs: Any,
    ) -> None:
        self.store_dir = store_dir or store_root
        self.store_root = self.store_dir
        self.preferred_adapter_id = preferred_adapter_id
        self.hmac_key = hmac_key
        for k, v in kwargs.items():
            setattr(self, k, v)


class RuntimeDaemon:
    """In-process Virtual iGPU control plane."""

    def __init__(
        self,
        root: str | Path | RuntimeConfig | None = None,
        adapters: list[Adapter] | None = None,
        *,
        store_dir: str | Path | None = None,
        max_per_tenant: int = 32,
        hmac_key: bytes | str | None = None,
        delivery_mode: str = DeliveryMode.EMBEDDED.value,
        runtime_identity: str | None = None,
        build_identity: str | None = None,
        preferred_adapter_id: str | None = None,
        hardware_attestation_verifier: Callable[[Mapping[str, Any]], bool] | None = None,
        config: Any = None,
    ) -> None:
        # Support: RuntimeDaemon(RuntimeConfig(...), adapters=[...])
        if isinstance(root, RuntimeConfig):
            config = root
            root = None
        root_path = root or store_dir
        if config is not None:
            root_path = (
                getattr(config, "store_dir", None)
                or getattr(config, "store_root", None)
                or root_path
            )
            preferred_adapter_id = preferred_adapter_id or getattr(
                config, "preferred_adapter_id", None
            )
            hmac_key = hmac_key or getattr(config, "hmac_key", None)
        self.root = Path(root_path or os.getenv("CHRONUS_VIGPU_STORE", ".chronus-virtual-igpu"))
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "evidence").mkdir(parents=True, exist_ok=True)
        if adapters is not None and len(adapters) == 0:
            raise RuntimeInvariantError("no execution adapter configured")
        self.adapters = list(adapters) if adapters is not None else default_adapters()
        if not self.adapters:
            raise RuntimeInvariantError("no execution adapter configured")
        self.memory = VirtualMemoryPlane(self.root)
        self.ledger = EvidenceLedger(self.root, hmac_key=hmac_key)
        self.state = RuntimeState.DETACHED
        self.delivery_mode = delivery_mode
        self.runtime_identity = runtime_identity or f"chronus.virtual_igpu:{ABI_VERSION}"
        self.build_identity = build_identity or os.getenv("CHRONUS_VIGPU_BUILD", "source-tree")
        self.preferred_adapter_id = preferred_adapter_id
        self.hardware_attestation_verifier = hardware_attestation_verifier
        self._lock = threading.RLock()
        self._max_per_tenant = int(max_per_tenant)
        self.in_flight: dict[str, int] = {}
        self._pending: set[str] = set()
        self._cancelled: set[str] = set()
        self._results: dict[str, WorkloadResult] = {}
        self._idempotency: dict[str, WorkloadResult] = {}
        self._idempotency_packages: dict[str, str] = {}
        self._attached_at: str | None = None
        self._last_error: str | None = None
        self.quotas: dict[str, Quota] = {}
        self._recoveries = 0
        self._max_recoveries = 3
        # Legacy attribute names used by older tests
        self.store_dir = self.root
        self.store_root = self.root
        # Auto-attach for unit-test convenience when constructed with adapters
        try:
            self.attach()
        except Exception:
            pass

    # --- lifecycle ---------------------------------------------------------

    def attach(self) -> RuntimeState:
        with self._lock:
            if self.state in {RuntimeState.READY, RuntimeState.NEGOTIATING, RuntimeState.PROBING}:
                return self.state
            self.state = RuntimeState.ATTACHING
            try:
                self.state = RuntimeState.PROBING
                self._probe_all()
                self.state = RuntimeState.NEGOTIATING
                # Negotiation: capabilities already on adapters
                self.state = RuntimeState.READY
                self._attached_at = _utc_now()
                self._last_error = None
            except Exception as exc:
                self.state = RuntimeState.FAILED
                self._last_error = str(exc)
                raise
            return self.state

    def detach(self) -> RuntimeState:
        with self._lock:
            self.state = RuntimeState.DRAINING
            # wait briefly for in-flight to drop
            deadline = time.time() + 2.0
            while sum(self.in_flight.values()) > 0 and time.time() < deadline:
                self._lock.release()
                try:
                    time.sleep(0.01)
                finally:
                    self._lock.acquire()
            self.state = RuntimeState.DETACHED
            return self.state

    def stop(self) -> None:
        self.detach()

    def _probe_all(self) -> None:
        for adapter in self.adapters:
            try:
                adapter.probe()
            except Exception:
                pass

    def recover(self) -> RuntimeState:
        """Bounded recovery: re-probe adapters and return to READY.

        Legal from FAILED/RECOVERING/DETACHED; from READY it performs a plain
        re-probe refresh (the device-loss path — an adapter whose device
        vanished fails its probe and is excluded from later selection).
        Recovery attempts are bounded; exhausting the budget fails closed.
        """
        with self._lock:
            if self.state == RuntimeState.READY:
                self._probe_all()
                return self.state
            if self._recoveries >= self._max_recoveries:
                self.state = RuntimeState.FAILED
                self._last_error = "recovery budget exhausted"
                raise RuntimeInvariantError(self._last_error)
            self._recoveries += 1
            self.state = RuntimeState.RECOVERING
            try:
                self._probe_all()
                if not any(getattr(a, "available", False) for a in self.adapters):
                    raise RuntimeInvariantError("no adapter available after recovery re-probe")
                self.state = RuntimeState.READY
                self._last_error = None
            except Exception as exc:
                self.state = RuntimeState.FAILED
                self._last_error = str(exc)
                raise
            return self.state

    def health(self) -> dict[str, Any]:
        with self._lock:
            running = self.state in {
                RuntimeState.READY,
                RuntimeState.PROBING,
                RuntimeState.NEGOTIATING,
                RuntimeState.DRAINING,
            }
            return {
                "state": self.state.value,
                "running": running,
                "abi_version": ABI_VERSION,
                "delivery_mode": self.delivery_mode,
                "runtime_identity": self.runtime_identity,
                "build_identity": self.build_identity,
                "adapters": [a.health() for a in self.adapters],
                "in_flight": dict(self.in_flight),
                "memory": self.memory.stats(),
                "attached_at": self._attached_at,
                "last_error": self._last_error,
            }

    # --- trust corroboration -------------------------------------------------

    def _hardware_root_corroborated(self, adapter: Adapter) -> bool:
        """Fail-closed check for a ``hardware_rooted`` claim.

        The claim is honoured only when a caller-supplied
        ``hardware_attestation_verifier`` accepts the adapter's probe
        attestation (which must itself assert ``hardware_rooted`` trust).
        Without that external mechanism nothing here corroborates device
        grounding — self-assertion is refused, so a lying adapter cannot
        promote itself to hardware-rooted provenance.
        """
        verifier = self.hardware_attestation_verifier
        if verifier is None:
            return False
        try:
            att = adapter.probe()
        except Exception:
            return False
        if not getattr(att, "hardware_rooted", False):
            return False
        if getattr(att, "trust_class", None) != TrustClass.HARDWARE_ROOTED.value:
            return False

        try:
            return bool(verifier(att.as_dict()))
        except Exception:
            return False

    # --- admission / selection --------------------------------------------

    def _policy(self, w: Workload) -> str:
        return ExecutionPolicy(
            str(
                getattr(w, "execution_policy", None)
                or ExecutionPolicy.PREFERRED_ACCELERATOR.value
            )
        ).value

    def _select_adapter(self, w: Workload) -> tuple[Adapter, str, AdmissionRecord]:
        policy = self._policy(w)
        available = [a for a in self.adapters if getattr(a, "available", False)]
        software = [
            a
            for a in available
            if "software" in a.id or "cpu" in a.id or a.kind.value in {"software", "cpu_reference"}
        ]
        physical = [a for a in available if a not in software]

        def _pick(candidates: list[Adapter], reason: str) -> tuple[Adapter, str, AdmissionRecord]:
            if not candidates:
                raise AdapterUnavailable(f"no adapter for policy={policy}")
            supporting = [a for a in candidates if a.supports(w.kind)]
            if not supporting:
                raise AdapterUnavailable(
                    f"no {policy} adapter supports workload kind={w.kind.value}"
                )
            chosen = sorted(
                supporting,
                key=lambda a: int(getattr(a, "priority", 0)),
                reverse=True,
            )[0]
            rec = AdmissionRecord(
                admitted=True,
                adapter_id=chosen.id,
                reason=reason,
                queue_depth=self.in_flight.get(w.tenant, 0),
            )
            return chosen, reason, rec

        req_adapter = getattr(w, "required_adapter_id", None)
        req_device = getattr(w, "required_device_id", None)

        if policy == ExecutionPolicy.STANDALONE_SOFTWARE.value:
            return _pick(software, "policy:standalone_software")

        if policy == ExecutionPolicy.REQUIRED_ADAPTER.value or req_adapter:
            target = req_adapter
            if not target:
                raise AdapterUnavailable("required_adapter policy without required_adapter_id")
            matched = [a for a in self.adapters if a.id == target]
            if not matched or not matched[0].available:
                raise AdapterUnavailable(f"required adapter unavailable: {target}")
            return _pick(matched, f"policy:required_adapter:{target}")

        if policy == ExecutionPolicy.REQUIRED_DEVICE.value or req_device:
            req = req_device
            if not req:
                raise AdapterUnavailable("required_device policy without required_device_id")
            matched = [
                a
                for a in available
                if req in a.id or req in getattr(a.capabilities(), "device_ids", ())
            ]
            if not matched:
                raise AdapterUnavailable(f"required device unavailable: {req}")
            return _pick(matched, f"policy:required_device:{req}")

        # preferred_adapter_id on daemon or workload constraints
        pref = self.preferred_adapter_id or (w.constraints or {}).get("preferred_adapter_id")
        if pref:
            matched = [a for a in available if a.id == pref]
            if matched:
                return _pick(matched, f"policy:preferred_adapter_id:{pref}")

        # preferred_accelerator (default)
        if physical:
            return _pick(physical, "policy:preferred_accelerator:physical")
        if not w.allow_software_fallback:
            raise AdapterUnavailable(
                "preferred accelerator unavailable and software fallback is disabled"
            )
        return _pick(software or available, "policy:preferred_accelerator:software_fallback")

    # --- submit / poll / cancel -------------------------------------------

    def submit(self, workload: Workload | dict[str, Any]) -> WorkloadResult:
        w = workload if isinstance(workload, Workload) else Workload.from_dict(workload)
        with self._lock:
            if self.state != RuntimeState.READY:
                # auto-attach for embedded convenience
                if self.state == RuntimeState.DETACHED:
                    self._lock.release()
                    try:
                        self.attach()
                    finally:
                        self._lock.acquire()
                if self.state != RuntimeState.READY:
                    raise RuntimeInvariantError(f"runtime not ready: {self.state}")

            # Idempotency
            key = getattr(w, "idempotency_key", None)
            if key:
                if key in self._idempotency:
                    prev = self._idempotency[key]
                    prev_hash = self._idempotency_packages.get(key)
                    if prev_hash and prev_hash != w.content_hash:
                        raise RuntimeInvariantError(
                            "idempotency key reused with a different workload package"
                        )
                    return prev

            if self.in_flight.get(w.tenant, 0) >= self._max_per_tenant:
                raise RuntimeInvariantError(f"tenant oversubscribed: {w.tenant}")

            q = self.quotas.get(w.tenant)
            declared_bytes = len(canonical_json(w.input or {}).encode("utf-8"))
            if q is not None:
                if q.submitted >= q.max_workloads:
                    raise RuntimeInvariantError(f"quota exceeded for tenant {w.tenant}")
                if q.submitted_bytes + declared_bytes > q.max_bytes:
                    raise RuntimeInvariantError(
                        f"byte quota exceeded for tenant {w.tenant}: "
                        f"{q.submitted_bytes}+{declared_bytes}>{q.max_bytes}"
                    )

            deadline_ms = getattr(w, "deadline_ms", None)
            if deadline_ms is not None and int(deadline_ms) <= 0:
                raise RuntimeInvariantError("deadline_ms must be positive when declared")

            try:
                adapter, reason, admission = self._select_adapter(w)
            except AdapterUnavailable:
                raise

            self.in_flight[w.tenant] = self.in_flight.get(w.tenant, 0) + 1
            self._pending.add(w.id)
            self._cancelled.discard(w.id)
            attempt_id = str(uuid.uuid4())

        started = time.time_ns()
        try:
            # Memory-plane ops handled here for STORE/RETRIEVE
            # A cancel() that landed while the adapter was running marks the
            # result honestly — the work may have executed, but the receipt
            # must not claim an unqualified success for a cancelled request.
            def _finalise(result: WorkloadResult) -> WorkloadResult:
                if w.id in self._cancelled:
                    return replace(
                        result,
                        status="cancelled",
                        error="cancelled before completion was reported",
                    )
                return result

            if w.kind == WorkloadKind.STORE:
                stored = self.memory.store(
                    w.input,
                    tenant=w.tenant,
                    adapter_id=adapter.id,
                    metadata={"workload_id": w.id, "kind": w.kind.value},
                )
                oid = getattr(stored, "object_id", stored)
                result = self._execute_with_deadline(adapter, w, deadline_ms)
                result = replace(result, object_id=str(oid), output={**result.output, "object_id": str(oid)})
            elif w.kind == WorkloadKind.RETRIEVE:
                oid = str((w.input or {}).get("object_id") or (w.input or {}).get("id") or "")
                payload = self.memory.retrieve(oid, tenant=w.tenant)
                result = self._execute_with_deadline(adapter, w, deadline_ms)
                result = replace(result, object_id=oid, output={**result.output, "payload": payload, "object_id": oid})
            else:
                result = self._execute_with_deadline(adapter, w, deadline_ms)
                # Persist fold/unfold (and any output with payload bytes) for object handles
                if w.kind in {WorkloadKind.FOLD, WorkloadKind.UNFOLD}:
                    stored = self.memory.store(
                        result.output,
                        tenant=w.tenant,
                        adapter_id=adapter.id,
                        residency=adapter.id,
                    )
                    result = replace(result, object_id=str(getattr(stored, "object_id", stored)))
            result = _finalise(result)

            # Independent result verification: the receipt must bind more
            # than the fact that an adapter returned bytes. For workload
            # kinds with a deterministic oracle the control plane recomputes
            # the output and compares; a mismatch demotes the result to
            # ``verification_failed`` — the dishonest attempt is still
            # ledgered below as forensic evidence, never as success.
            verify_report = (
                verify_workload_result(w, result)
                if result.status == "ok"
                else {
                    "recomputed": False,
                    "verifier": "none",
                    "verdict": "skipped_not_ok",
                }
            )
            if verify_report["verdict"] == "mismatch":
                result = replace(
                    result,
                    status="verification_failed",
                    error=(
                        "independent recompute mismatch: "
                        f"{verify_report.get('detail', 'unspecified')}"
                    ),
                )

            # Build portable package + receipt
            pkg = PortablePackage(
                package_id=w.content_hash or w.id,
                operation=w.kind.value if isinstance(w.kind, WorkloadKind) else str(w.kind),
                input_refs=tuple(str(k) for k in (w.input or {}).keys()),
                content_hash=w.content_hash or digest_json(w.as_dict()),
                constraints=dict(w.constraints or {}),
            )
            trust = result.trust_class or TrustClass.RUNTIME_SIGNED.value
            hardware_rooted = bool(result.hardware_rooted)
            # Software never hardware-rooted
            if "software" in adapter.id or "cpu" in adapter.id:
                hardware_rooted = False
                if trust == TrustClass.HARDWARE_ROOTED.value:
                    trust = TrustClass.RUNTIME_SIGNED.value
            # hardware_rooted is a claim, never a fact: it survives only when a
            # verified attestation mechanism corroborates it. An adapter that
            # self-asserts hardware rooting without a replayable chain is
            # downgraded to runtime_signed (never silently believed).
            if hardware_rooted and not self._hardware_root_corroborated(adapter):
                hardware_rooted = False
                if trust == TrustClass.HARDWARE_ROOTED.value:
                    trust = TrustClass.RUNTIME_SIGNED.value

            receipt = ExecutionReceipt(
                receipt_id=digest_json({"attempt": attempt_id, "wid": w.id})[:32],
                workload_id=w.id,
                attempt_id=attempt_id,
                package_version=pkg.package_id,
                protocol_version=ABI_VERSION,
                delivery_mode=str(getattr(w, "delivery_mode", None) or self.delivery_mode),
                requested_policy=self._policy(w),
                actual_backend=adapter.id,
                actual_device=result.actual_device_id or adapter.id,
                runtime_identity=self.runtime_identity,
                build_identity=self.build_identity,
                kernel_identity=str((result.output or {}).get("engine") or adapter.kind.value),
                input_digest=w.content_hash or "",
                output_digest=result.evidence_digest or result.digest or digest_json(result.output),
                verified_work_count=int((result.output or {}).get("checked") or 0),
                seed=(w.input or {}).get("seed"),
                timing={
                    "wall_time_ns": result.wall_time_ns,
                    "device_time_ns": result.device_time_ns,
                    "total_ns": int(time.time_ns() - started),
                },
                verification={
                    "status": result.status,
                    "admission": admission.as_dict(),
                    **verify_report,
                },
                trust_class=trust,
                hardware_rooted=hardware_rooted,
                content_hash="",  # filled below
                metadata={"route_reason": reason},
            )
            rcpt_dict = receipt.as_dict()
            rcpt_hash = digest_json({k: v for k, v in rcpt_dict.items() if k != "content_hash"})
            receipt = replace(receipt, content_hash=rcpt_hash)
            rcpt_dict = receipt.as_dict()

            result = replace(
                result,
                trust_class=trust,
                hardware_rooted=hardware_rooted,
                requested_policy=self._policy(w),
                actual_adapter_id=adapter.id,
                actual_device_id=result.actual_device_id or adapter.id,
                route_reason=reason,
                delivery_mode=str(getattr(w, "delivery_mode", None) or self.delivery_mode),
                receipt=rcpt_dict,
                metrics={
                    "admission": admission.as_dict(),
                    "package": pkg.as_dict(),
                },
            )

            self.ledger.append(
                workload_id=w.id,
                adapter_id=adapter.id,
                kind=w.kind.value if isinstance(w.kind, WorkloadKind) else str(w.kind),
                result_dict=result.as_dict(),
                receipt_dict=rcpt_dict,
                trust_class=trust,
                hardware_rooted=hardware_rooted,
                wall_time_ns=result.wall_time_ns,
                device_time_ns=result.device_time_ns,
            )

            # Content-addressed evidence file (unit-test contract):
            # sha256(file_bytes) == evidence_digest == filename stem.
            import hashlib as _hashlib
            import json as _json

            body_for_hash = {
                "workload_id": w.id,
                "tenant": w.tenant,
                "adapter_id": result.adapter_id,
                "kind": result.kind,
                "status": result.status,
                "output": result.output,
                "wall_time_ns": result.wall_time_ns,
                "device_time_ns": result.device_time_ns,
                "object_id": result.object_id,
                "receipt": {k: v for k, v in rcpt_dict.items() if k != "content_hash"},
                "abi_version": ABI_VERSION,
            }
            evidence_bytes = _json.dumps(
                body_for_hash, sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
            evidence_digest = _hashlib.sha256(evidence_bytes).hexdigest()
            result = replace(result, evidence_digest=evidence_digest, digest=evidence_digest)
            evidence_path = self.root / "evidence" / f"{evidence_digest}.json"
            evidence_path.write_bytes(evidence_bytes)

            # Artifact under tenant/workload for memory.retrieve(tenant, wid)
            self.memory.store_artifact(
                tenant=w.tenant,
                workload_id=w.id,
                artifact={"result": result.as_dict(), "receipt": rcpt_dict},
            )

            with self._lock:
                self._results[w.id] = result
                if key:
                    self._idempotency[key] = result
                    self._idempotency_packages[key] = w.content_hash or ""
                self._pending.discard(w.id)
                if q is not None:
                    q.submitted += 1
                    q.submitted_bytes += declared_bytes
            return result
        except Exception:
            with self._lock:
                self._pending.discard(w.id)
                self._last_error = "submit failed"
            raise
        finally:
            with self._lock:
                self.in_flight[w.tenant] = max(0, self.in_flight.get(w.tenant, 1) - 1)

    def _execute_with_deadline(
        self, adapter: Adapter, w: Workload, deadline_ms: int | None
    ) -> WorkloadResult:
        """Run ``adapter.execute`` under an optional deadline.

        On expiry the attempt is recorded as ``status="timeout"`` — a real
        timeout outcome, never rewritten to success. The late-finishing
        worker is a daemon thread whose result is discarded; in-flight
        accounting is released by the caller's ``finally``.
        """
        if deadline_ms is None:
            return adapter.execute(w)
        outcome: dict[str, Any] = {}

        def _call() -> None:
            try:
                outcome["result"] = adapter.execute(w)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = exc

        worker = threading.Thread(target=_call, name=f"vigpu-exec-{w.id}", daemon=True)
        worker.start()
        worker.join(max(int(deadline_ms), 1) / 1000.0)
        if worker.is_alive():
            return adapter._result(
                w,
                {"timed_out": True, "deadline_ms": int(deadline_ms)},
                time.time_ns() - int(deadline_ms) * 1_000_000,
                status="timeout",
                error=f"deadline_ms={int(deadline_ms)} exceeded",
            )
        if "error" in outcome:
            raise outcome["error"]
        return outcome["result"]

    def poll(self, workload_id: str) -> WorkloadResult | None:
        with self._lock:
            return self._results.get(workload_id)

    def cancel(self, workload_id: str) -> bool:
        """Cancel a pending workload. The completion is then reported as
        ``status="cancelled"`` rather than success — the runtime cannot
        retract an in-flight device call, so it records the truth instead."""
        with self._lock:
            if workload_id in self._pending:
                self._pending.discard(workload_id)
                self._cancelled.add(workload_id)
                return True
            return False

    def wait(self, workload_id: str, timeout_s: float = 30.0) -> WorkloadResult:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = self.poll(workload_id)
            if r is not None:
                return r
            time.sleep(0.01)
        raise TimeoutError(f"workload not complete: {workload_id}")


# Module-level embedded daemon (lazy)
_DAEMON: RuntimeDaemon | None = None
_DAEMON_LOCK = threading.Lock()


def get_embedded_daemon(**kwargs: Any) -> RuntimeDaemon:
    global _DAEMON
    with _DAEMON_LOCK:
        if _DAEMON is None:
            _DAEMON = RuntimeDaemon(**kwargs)
            _DAEMON.attach()
        return _DAEMON


# Back-compat alias
get_runtime = get_embedded_daemon
