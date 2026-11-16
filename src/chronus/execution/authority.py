"""Synchronous bounded CPU execution with durable THESEUS custody.

Process limits are not a security sandbox or hardware attestation. Only the
explicitly listed stateless workloads run here; storage/remote backends cannot.
"""
from __future__ import annotations

import hashlib
import base64
import json
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile
import time
from uuid import uuid4

from chronus.storage.durable import DurableTheseusService

SUPPORTED_WORKLOADS = frozenset({
    "EXACT_Q5_ALGEBRAIC", "LUCAS_PV_SCALING", "METALLIC_SCALE",
    "SHA256D_NONCE_SEARCH",
})
MAX_RESULT_BYTES = 512 * 1024


class ExecutionBusyError(RuntimeError):
    """All execution slots are occupied."""


def _encode(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _seal(record: dict, key: bytes | None, tenant: str) -> bytes:
    payload = _encode(record)
    if key is None:
        return payload
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    aad = _encode({"tenant_id": tenant, "schema": "chronus-execution-aesgcm-v1"})
    ciphertext = AESGCM(key).encrypt(nonce, payload, aad)
    return _encode({"encryption": "AES-256-GCM", "nonce": base64.b64encode(nonce).decode(),
                    "ciphertext": base64.b64encode(ciphertext).decode()})


def _unseal(payload: bytes, key: bytes | None, tenant: str) -> dict:
    record = json.loads(payload)
    if record.get("encryption") == "AES-256-GCM":
        if key is None:
            raise ValueError("customer custody key is unavailable")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aad = _encode({"tenant_id": tenant, "schema": "chronus-execution-aesgcm-v1"})
        raw = AESGCM(key).decrypt(base64.b64decode(record["nonce"], validate=True),
                                 base64.b64decode(record["ciphertext"], validate=True), aad)
        return json.loads(raw)
    if key is not None:
        raise ValueError("unencrypted execution record in encrypted custody")
    return record


def _worker(payload: bytes, workload_type: str, output: str,
            memory_bytes: int, cpu_seconds: int, custody_key: bytes | None, tenant_id: str) -> None:
    os.setsid()
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * MAX_RESULT_BYTES, 2 * MAX_RESULT_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        from chronus.execution.reference import ExecutionRouter
        if workload_type == "SHA256D_NONCE_SEARCH":
            request = json.loads(payload)
            if (type(request.get("workers", 1)) is not int or request.get("workers", 1) != 1
                    or "store" in request):
                raise ValueError("bounded epochs require one worker and parent-owned custody")
        result = ExecutionRouter().execute(payload, workload_type, "python-math-reference")
        encoded = _encode({"status": "COMPLETED", "result": result.to_dict()})
        if len(encoded) > MAX_RESULT_BYTES:
            raise ValueError("execution output exceeds result budget")
    except Exception:
        # Exception text can contain customer data.
        encoded = _encode({"status": "FAILED", "error": "execution_rejected_or_failed"})
    Path(output).write_bytes(_seal(json.loads(encoded), custody_key, tenant_id))


def _stop(process) -> None:
    if process.pid is None:
        return
    try:
        # Never signal the API's group if the worker has not called setsid yet.
        if os.getpgid(process.pid) == process.pid:
            os.killpg(process.pid, signal.SIGKILL)
        elif process.is_alive():
            process.kill()
    except ProcessLookupError:
        pass
    process.join(timeout=2)
    if process.is_alive():
        raise RuntimeError("execution worker could not be reaped")


class ExecutionAuthority:
    """Local-host authority; file locks share slots across API processes."""

    def __init__(self, state_path: str, *, max_concurrent: int = 2,
                 max_wall_seconds: float = 30, memory_bytes: int = 2 * 1024**3,
                 custody_key: bytes | None = None):
        # This implementation requires POSIX process groups and resource limits.
        import fcntl
        if (isinstance(max_concurrent, bool) or not isinstance(max_concurrent, int)
                or not 1 <= max_concurrent <= 128):
            raise ValueError("max_concurrent must be between 1 and 128")
        if (isinstance(max_wall_seconds, bool) or not isinstance(max_wall_seconds, (int, float))
                or not 0 < max_wall_seconds <= 3600):
            raise ValueError("max_wall_seconds must be finite and between 0 and 3600")
        if isinstance(memory_bytes, bool) or not isinstance(memory_bytes, int) or memory_bytes < 128 * 1024**2:
            raise ValueError("memory_bytes must be an integer of at least 128 MiB")
        if custody_key is not None and (not isinstance(custody_key, bytes) or len(custody_key) != 32):
            raise ValueError("custody_key must be a customer-supplied 32-byte AES-256 key")
        self._custody_key = custody_key
        self.custody = DurableTheseusService(state_path)
        self.root = Path(state_path + ".execution")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.max_concurrent = max_concurrent
        self.max_wall_seconds = max_wall_seconds
        self.memory_bytes = memory_bytes
        with (self.root / "policy.json").open("a+b") as policy:
            fcntl.flock(policy, fcntl.LOCK_EX)
            policy.seek(0)
            expected = _encode({"max_concurrent": max_concurrent,
                                "max_wall_seconds": max_wall_seconds,
                                "memory_bytes": memory_bytes,
                                "key_sha256": hashlib.sha256(custody_key).hexdigest() if custody_key else None})
            current = policy.read()
            if current and json.loads(current) != json.loads(expected):
                raise ValueError("execution policy differs from persisted local policy")
            if not current:
                policy.write(expected)
                policy.flush()
                os.fsync(policy.fileno())

    def _persist_event(self, tenant_id: str, event: str, record: dict):
        return self.custody.append_journal_event(tenant_id, event, _seal(record, self._custody_key, tenant_id))

    def _read_record(self, tenant_id: str, object_id: str) -> dict:
        return _unseal(self.custody.reconstruct(tenant_id, object_id), self._custody_key, tenant_id)

    def _slot(self):
        import fcntl
        for index in range(self.max_concurrent):
            slot = (self.root / f"slot-{index}").open("a+b")
            try:
                fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return slot
            except BlockingIOError:
                slot.close()
        raise ExecutionBusyError("concurrent execution limit reached")

    def execute(self, tenant_id: str, payload: bytes, workload_type: str,
                wall_seconds: float | None = None) -> dict:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("authenticated tenant is required")
        if workload_type not in SUPPORTED_WORKLOADS:
            raise ValueError("workload is not admitted to bounded CPU execution")
        if not isinstance(payload, bytes) or not 1 <= len(payload) <= 1024 * 1024:
            raise ValueError("payload must be 1 to 1048576 bytes")
        budget = self.max_wall_seconds if wall_seconds is None else wall_seconds
        if (isinstance(budget, bool) or not isinstance(budget, (float, int))
                or not 0 < budget <= self.max_wall_seconds):
            raise ValueError("wall budget exceeds configured bounds")
        with self._slot():
            manifest = {
                "schema_version": 1, "producer": "CHRONUS", "producer_version": "37.0.0.dev0",
                "run_id": str(uuid4()), "tenant_id": tenant_id, "workload_type": workload_type,
                "input_sha256": hashlib.sha256(payload).hexdigest(),
                "backend": "python-math-reference", "execution_mode": "NATIVE_CPU_REFERENCE",
                "wall_seconds": budget, "memory_bytes": self.memory_bytes,
                "timestamp_ns": time.time_ns(), "evidence_state": "SOFTWARE_EXECUTION",
                "security_boundary": "process_limits_not_a_security_sandbox",
            }
            admission = self._persist_event(tenant_id, "EXECUTION_ADMITTED", manifest)
            started = time.perf_counter_ns()
            outcome = {"status": "FAILED", "error": "worker_exited_without_result"}
            with tempfile.TemporaryDirectory(dir=self.root) as directory:
                output = str(Path(directory) / "result.json")
                process = multiprocessing.get_context("spawn").Process(
                    target=_worker, args=(payload, workload_type, output, self.memory_bytes, max(1, int(-(-budget // 1))), self._custody_key, tenant_id),
                )
                try:
                    process.start()
                    process.join(timeout=max(0, budget - (time.perf_counter_ns() - started) / 1_000_000_000))
                    if process.is_alive():
                        outcome = {"status": "TIMED_OUT", "error": "wall_time_budget_exceeded"}
                    elif process.exitcode == 0 and Path(output).is_file():
                        if Path(output).stat().st_size <= 2 * MAX_RESULT_BYTES:
                            outcome = _unseal(Path(output).read_bytes(), self._custody_key, tenant_id)
                except Exception:
                    outcome = {"status": "FAILED", "error": "worker_supervision_failed"}
                finally:
                    _stop(process)
                    process.close()
            receipt = {
                **manifest, **outcome, "completed_at_ns": time.time_ns(),
                "elapsed_seconds": (time.perf_counter_ns() - started) / 1_000_000_000,
                "admission_object_id": admission.object_id,
                "admission_entry_hash": admission.entry_hash,
            }
            terminal = self._persist_event(tenant_id, "EXECUTION_" + outcome["status"], receipt)
            return {**receipt, "receipt_object_id": terminal.object_id,
                    "journal_entry_hash": terminal.entry_hash}

    def status(self, tenant_id: str, receipt_object_id: str) -> dict:
        receipt = self._read_record(tenant_id, receipt_object_id)
        if receipt.get("producer") != "CHRONUS" or "completed_at_ns" not in receipt:
            raise KeyError(receipt_object_id)
        admission = self._read_record(tenant_id, receipt["admission_object_id"])
        if any(receipt.get(key) != value for key, value in admission.items()):
            raise ValueError("execution admission lineage mismatch")
        if not self.custody.verify_journal_continuity(tenant_id):
            raise ValueError("execution journal continuity verification failed")
        entries = self.custody.get_journal(tenant_id)
        if not any(entry.object_id == receipt["admission_object_id"]
                   and entry.entry_hash == receipt["admission_entry_hash"] for entry in entries):
            raise ValueError("execution admission journal reference is missing")
        if not any(entry.object_id == receipt_object_id
                   and entry.event_type == "EXECUTION_" + receipt["status"] for entry in entries):
            raise ValueError("execution terminal journal reference is missing")
        return {**receipt, "receipt_object_id": receipt_object_id}

    def replay(self, tenant_id: str, receipt_object_id: str) -> dict:
        receipt = self.status(tenant_id, receipt_object_id)
        return {"run_id": receipt["run_id"], "receipt_object_id": receipt_object_id,
                "integrity_verified": True, "mutation_allowed": False,
                "scope": "custody_and_admission_lineage_not_reexecution"}
