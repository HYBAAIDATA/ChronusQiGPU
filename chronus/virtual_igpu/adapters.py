"""Execution adapters. Unavailable backends fail closed; none emulate success."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import base64
import hashlib
import math
import struct
from time import perf_counter_ns
from typing import Any, Iterable

import numpy as np

from aethel.encoding import ZeckendorfVector, fold, unfold
from aethel.fibonacci import fibonacci

from .abi import (
    AdapterAttestation, AdapterKind, Capability, Workload, WorkloadKind,
    WorkloadResult, digest_json,
)
from .attestation import extend_chain
from .capabilities import CapabilityManifest
from .operators import ExecutionClass


class AdapterUnavailable(RuntimeError):
    pass


class ExecutionAdapter(ABC):
    id: str
    kind: AdapterKind
    capabilities: frozenset[Capability]
    priority: int = 0
    fail_closed: bool = True

    @abstractmethod
    def health(self) -> dict[str, Any]: ...

    @abstractmethod
    def execute(self, workload: Workload) -> WorkloadResult: ...

    def attest(self) -> AdapterAttestation:
        record = {
            "adapter_id": self.id,
            "kind": self.kind.value,
            "capabilities": sorted(c.value for c in self.capabilities),
            "health": self.health(),
        }
        fingerprint = digest_json(record)
        chain = extend_chain((), record)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind,
            capabilities=tuple(sorted(c.value for c in self.capabilities)),
            fingerprint=fingerprint,
            firmware_hash=None,
            chain=chain,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def supports(self, kind: WorkloadKind) -> bool:
        return Capability(kind.value) in self.capabilities

    def capability_manifest(self) -> CapabilityManifest:
        health = self.health()
        available = bool(health.get("available"))
        return CapabilityManifest(
            adapter_id=self.id,
            adapter_kind=self.kind.value,
            operations=tuple(sorted(c.value for c in self.capabilities)) if available else (),
            dtypes=("float32", "bytes", "int"),
            execution_classes=(ExecutionClass.DENSE_NATIVE.value,),
            memory_model={"kind": "host", "unified": True},
            execution_model={"priority": self.priority, "fail_closed": self.fail_closed},
            limits={"legal_work_group_sizes": [1], "max_batch_size": 1 << 20, "max_queue_depth": 1},
            profiling={"wall_time": True, "device_time": False},
            verified={"available": available, "truth_class": health.get("truth_class", "runtime_probe")},
            evidence={"attestation": True, "content_addressed": True},
        )

    def execute_planned(self, workload: Workload, plan: Any) -> WorkloadResult:
        if getattr(plan, "adapter_id", self.id) != self.id:
            raise AdapterUnavailable("execution plan targets another adapter")
        return self.execute(workload)

    def _result(
        self, workload: Workload, output: dict[str, Any], started_ns: int,
        *, device_time_ns: int | None = None,
    ) -> WorkloadResult:
        digest = digest_json(output)
        record = {
            "workload_id": workload.id,
            "adapter": self.id,
            "output_digest": digest,
        }
        chain = extend_chain(workload.attestation, record)
        return WorkloadResult(
            workload_id=workload.id,
            status="ok",
            output=output,
            digest=digest,
            attestation=chain,
            executed_on=self.id,
            wall_time_ns=perf_counter_ns() - started_ns,
            device_time_ns=device_time_ns,
        )


class CPUEmulatorAdapter(ExecutionAdapter):
    id = "cpu-emulator"
    kind = AdapterKind.CPU_EMULATOR
    priority = -100
    capabilities = frozenset(Capability)

    def health(self) -> dict[str, Any]:
        return {"available": True, "truth_class": "software_emulator"}

    @staticmethod
    def _payload(value: dict[str, Any]) -> bytes:
        if "payload_b64" in value:
            return base64.b64decode(value["payload_b64"], validate=True)
        if "payload_utf8" in value:
            return str(value["payload_utf8"]).encode()
        raise ValueError("payload_b64 or payload_utf8 is required")

    def execute(self, workload: Workload) -> WorkloadResult:
        started = perf_counter_ns()
        value = dict(workload.input)
        kind = workload.kind
        if kind == WorkloadKind.FOLD:
            vector = fold(self._payload(value))
            output = {"blocks": [list(v) for v in vector.blocks], "total_bytes": vector.total_bytes}
        elif kind == WorkloadKind.UNFOLD:
            vector = ZeckendorfVector(
                blocks=tuple((int(a), int(b)) for a, b in value["blocks"]),
                total_bytes=int(value["total_bytes"]),
            )
            output = {"payload_b64": base64.b64encode(unfold(vector)).decode()}
        elif kind == WorkloadKind.TENSOR_CONTRACT:
            a = np.asarray(value["a"], dtype=np.float32)
            b = np.asarray(value["b"], dtype=np.float32)
            if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[0]:
                raise ValueError("tensor_contract requires compatible rank-2 matrices")
            output = {"result": (a @ b).tolist(), "dtype": "float32"}
        elif kind == WorkloadKind.TENSOR_SVD:
            a = np.asarray(value["a"], dtype=np.float64)
            u, s, vh = np.linalg.svd(a, full_matrices=False)
            output = {"u": u.tolist(), "s": s.tolist(), "vh": vh.tolist(), "dtype": "float64"}
        elif kind == WorkloadKind.PHI_TRANSFORM:
            phi = (1 + math.sqrt(5)) / 2
            output = {"result": [float(x) * phi for x in value["vector"]], "phi": phi}
        elif kind == WorkloadKind.LUCAS_TRANSFORM:
            indices = [int(n) for n in value["indices"]]
            def lucas(n: int) -> int:
                if n < 0:
                    raise ValueError("Lucas indices must be non-negative")
                a, b = 2, 1
                for _ in range(n):
                    a, b = b, a + b
                return a
            output = {"result": [lucas(n) for n in indices]}
        elif kind == WorkloadKind.SHA256D_VERIFY:
            blob = bytes.fromhex(value["header_hex"])
            digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
            output = {"digest_hex": digest.hex(), "verified": digest.hex() == value["digest_hex"]}
        elif kind == WorkloadKind.SHA256D_SCAN:
            prefix = bytes.fromhex(value["header_prefix_hex"])
            if len(prefix) != 76:
                raise ValueError("header prefix must be 76 bytes")
            start, count, target = int(value["start_nonce"]), int(value["count"]), int(value["target"])
            found = None
            digest = None
            for offset in range(count):
                nonce = (start + offset) & 0xFFFFFFFF
                candidate = hashlib.sha256(hashlib.sha256(prefix + struct.pack("<I", nonce)).digest()).digest()
                if int.from_bytes(candidate, "little") <= target:
                    found, digest = nonce, candidate.hex()
                    break
            output = {"nonce": found, "digest_hex": digest, "hashes": count if found is None else offset + 1}
        elif kind in {WorkloadKind.STORE, WorkloadKind.RETRIEVE}:
            output = {"memory_plane_operation": kind.value, "request": value}
        else:
            raise ValueError(f"unsupported workload {kind.value}")
        return self._result(workload, output, started)


class OpenCLIntelUHDAdapter(ExecutionAdapter):
    id = "opencl-intel-uhd"
    kind = AdapterKind.OPENCL_INTEL_UHD
    priority = 100
    capabilities = frozenset({Capability.TENSOR_CONTRACT, Capability.SHA256D_SCAN})

    def __init__(self) -> None:
        self._reason = ""
        self._runtime = None
        try:
            from chronus.tensor_compute import get_runtime
            runtime = get_runtime()
            identity = f"{runtime.probe.vendor} {runtime.probe.device_name}".lower()
            if "intel" not in identity or "uhd" not in identity:
                raise AdapterUnavailable("selected OpenCL device is not Intel UHD")
            self._runtime = runtime
        except Exception as exc:
            self._reason = f"{type(exc).__name__}: {exc}"

    def health(self) -> dict[str, Any]:
        return {
            "available": self._runtime is not None,
            "reason": self._reason or None,
            "device": None if self._runtime is None else self._runtime.device_id,
        }

    def capability_manifest(self) -> CapabilityManifest:
        base = super().capability_manifest()
        if self._runtime is None:
            return base
        probe = self._runtime.probe
        max_wg = int(probe.max_work_group_size or 1)
        legal = tuple(v for v in (8, 16, 32, 64, 128, 256) if v <= max_wg) or (1,)
        return CapabilityManifest(
            adapter_id=self.id, adapter_kind=self.kind.value,
            operations=tuple(sorted(c.value for c in self.capabilities)), dtypes=("float32", "bytes"),
            execution_classes=(ExecutionClass.DENSE_NATIVE.value, ExecutionClass.PARTIAL_UNFOLD.value, ExecutionClass.HYBRID.value),
            memory_model={"kind": "opencl", "unified": probe.host_unified_memory, "local_memory_bytes": probe.local_memory_bytes},
            execution_model={"priority": self.priority, "fail_closed": True},
            limits={"legal_work_group_sizes": legal, "max_batch_size": max(1, int((probe.global_memory_bytes or 4) // 16)), "max_queue_depth": 8},
            profiling={"wall_time": True, "device_time": True},
            verified={"available": True, "device_id": probe.device_id},
            evidence={"attestation": True, "content_addressed": True},
        )

    def execute(self, workload: Workload) -> WorkloadResult:
        if self._runtime is None:
            raise AdapterUnavailable(self._reason)
        started = perf_counter_ns()
        if workload.kind == WorkloadKind.TENSOR_CONTRACT:
            a = np.asarray(workload.input["a"], dtype=np.float32)
            b = np.asarray(workload.input["b"], dtype=np.float32)
            result, evidence = self._runtime.execute_with_evidence(
                "matmul", (a, b), (a.shape, b.shape), (a.shape[0], b.shape[1])
            )
            expected = a @ b
            if not np.allclose(result, expected, rtol=1e-4, atol=1e-4):
                raise RuntimeError("Intel OpenCL tensor result failed reference verification")
            output = {"result": result.tolist(), "dtype": "float32"}
            return self._result(
                workload, output, started, device_time_ns=evidence.device_time_ns
            )
        if workload.kind == WorkloadKind.SHA256D_SCAN:
            from mining.bitcoin_hasher import BitcoinHasher
            value = workload.input
            prefix = bytes.fromhex(value["header_prefix_hex"])
            target_int = int(value["target"])
            target = target_int.to_bytes(32, "big")
            nonce, digest, hashes = BitcoinHasher(backend="opencl").grind_target_range(
                prefix + b"\0\0\0\0", target, int(value["start_nonce"]), int(value["count"])
            )
            output = {
                "nonce": nonce, "digest_hex": None if digest is None else digest.hex(), "hashes": hashes
            }
            return self._result(workload, output, started)
        raise ValueError(f"unsupported Intel adapter workload {workload.kind.value}")


class UnavailableAdapter(ExecutionAdapter):
    capabilities = frozenset()

    def __init__(self, adapter_id: str, kind: AdapterKind, reason: str) -> None:
        self.id, self.kind, self.reason = adapter_id, kind, reason

    def health(self) -> dict[str, Any]:
        return {"available": False, "reason": self.reason}

    def execute(self, workload: Workload) -> WorkloadResult:
        raise AdapterUnavailable(f"{self.id}: {self.reason}")


def default_adapters(include_emulator: bool = True) -> list[ExecutionAdapter]:
    adapters: list[ExecutionAdapter] = [OpenCLIntelUHDAdapter()]
    probes = (
        ("cuda", AdapterKind.CUDA),
        ("rocm", AdapterKind.ROCM),
        ("oneapi", AdapterKind.ONEAPI),
        ("metal", AdapterKind.METAL),
        ("opencl-intel-iris", AdapterKind.OPENCL_INTEL_IRIS),
        ("opencl-amd", AdapterKind.OPENCL_AMD),
        ("opencl-nvidia", AdapterKind.OPENCL_NVIDIA),
        ("azure", AdapterKind.AZURE),
        ("google-cloud", AdapterKind.GOOGLE_CLOUD),
    )
    adapters.extend(
        UnavailableAdapter(name, kind, "adapter not configured on this host")
        for name, kind in probes
    )
    if include_emulator:
        adapters.append(CPUEmulatorAdapter())
    return adapters