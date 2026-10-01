"""Audited GPU capability surface for Chronus.

Chronus owns hardware-facing discovery, scheduling, transfer, execution and
evidence. Kellogg remains the canonical owner of tensor mathematics. This
module closes the July GPU surface by composing those owners without copying
Kellogg algorithms or inventing hardware facts that a backend did not expose.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


class GPUCapabilityError(ValueError):
    """A GPU capability, evidence or tensor boundary was violated."""


@dataclass(frozen=True)
class TopologyLink:
    source: str
    target: str
    kind: str
    bandwidth_bytes_per_second: float | None = None
    evidence: str = "unknown"


@dataclass(frozen=True)
class GPUDeviceTopology:
    name: str
    vendor: str
    backend: str
    compute_units: int | None = None
    tensor_cores: int | None = None
    clock_mhz: float | None = None
    global_memory_bytes: int | None = None
    local_memory_bytes: int | None = None
    max_work_group_size: int | None = None
    pcie_bandwidth_bytes_per_second: float | None = None
    nvlink_bandwidth_bytes_per_second: float | None = None
    host_unified_memory: bool | None = None
    links: tuple[TopologyLink, ...] = ()
    truth_class: str = "runtime_probe"
    measured_by_chronus: bool = True
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["links"] = [asdict(link) for link in self.links]
        return result

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def _optional_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def probe_opencl_topology(
    device: Any,
    *,
    platform_name: str = "",
    links: Sequence[TopologyLink] = (),
) -> GPUDeviceTopology:
    """Capture only facts exposed by an OpenCL device object.

    Generic OpenCL does not expose tensor-core count, PCIe bandwidth or NVLink
    bandwidth. Those fields stay ``None`` unless a caller supplies measured
    link evidence; they are never inferred from a product name.
    """
    if device is None:
        raise GPUCapabilityError("an OpenCL device object is required")
    name = str(getattr(device, "name", "") or "").strip()
    vendor = str(getattr(device, "vendor", "") or "").strip()
    if not name:
        raise GPUCapabilityError("OpenCL device name is missing")
    unified = getattr(device, "host_unified_memory", None)
    return GPUDeviceTopology(
        name=name,
        vendor=vendor,
        backend="opencl",
        compute_units=_optional_int(getattr(device, "max_compute_units", None)),
        clock_mhz=_optional_float(getattr(device, "max_clock_frequency", None)),
        global_memory_bytes=_optional_int(getattr(device, "global_mem_size", None)),
        local_memory_bytes=_optional_int(getattr(device, "local_mem_size", None)),
        max_work_group_size=_optional_int(getattr(device, "max_work_group_size", None)),
        host_unified_memory=None if unified is None else bool(unified),
        links=tuple(links),
        notes=(
            f"platform={platform_name}" if platform_name else "platform not supplied",
            "tensor-core and host-link properties unavailable from generic OpenCL",
        ),
    )


def reference_gpu_topology(name: str) -> GPUDeviceTopology:
    """Convert the dated July reference into an explicitly non-measured topology."""
    from .gpu_reference import REFERENCE_DATE, get_gpu_spec

    spec = get_gpu_spec(name)
    links = ()
    if spec.nvlink_bandwidth_tbs > 0:
        links = (
            TopologyLink(
                source=spec.name,
                target="peer_gpu",
                kind="nvlink",
                bandwidth_bytes_per_second=spec.nvlink_bandwidth_tbs * 1e12,
                evidence=f"historical reference {REFERENCE_DATE}",
            ),
        )
    return GPUDeviceTopology(
        name=spec.name,
        vendor=spec.manufacturer,
        backend="reference",
        global_memory_bytes=spec.memory_capacity_gb * 1_000_000_000,
        nvlink_bandwidth_bytes_per_second=spec.nvlink_bandwidth_tbs * 1e12,
        links=links,
        truth_class="historical_public_reference",
        measured_by_chronus=False,
        notes=(
            f"reference_date={REFERENCE_DATE}",
            f"memory_type={spec.memory_type}",
            f"tensor_core_generation={spec.tensor_core_gen}",
            "SM count, tensor-core count, clock and PCIe bandwidth were not in the July table",
        ),
    )


@dataclass(frozen=True)
class GPUMemoryLevel:
    name: str
    scope: str
    capacity_bytes: int | None
    bandwidth_bytes_per_second: float | None = None
    latency_ns: float | None = None
    evidence: str = "unknown"


@dataclass(frozen=True)
class GPUMemoryHierarchyProfile:
    device_fingerprint: str
    levels: tuple[GPUMemoryLevel, ...]
    host_unified_memory: bool | None
    truth_class: str
    measured: bool
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_fingerprint": self.device_fingerprint,
            "levels": [asdict(level) for level in self.levels],
            "host_unified_memory": self.host_unified_memory,
            "truth_class": self.truth_class,
            "measured": self.measured,
            "notes": list(self.notes),
        }


def memory_hierarchy_from_topology(topology: GPUDeviceTopology) -> GPUMemoryHierarchyProfile:
    """Build an evidence-labelled hierarchy without fabricating cache/register data."""
    levels = (
        GPUMemoryLevel(
            "global",
            "device",
            topology.global_memory_bytes,
            evidence=topology.truth_class,
        ),
        GPUMemoryLevel(
            "local_shared",
            "work_group",
            topology.local_memory_bytes,
            evidence=topology.truth_class,
        ),
        GPUMemoryLevel("l2", "device", None, evidence="not exposed by generic probe"),
        GPUMemoryLevel("l1", "compute_unit", None, evidence="not exposed by generic probe"),
        GPUMemoryLevel("registers", "work_item", None, evidence="not exposed by generic probe"),
    )
    return GPUMemoryHierarchyProfile(
        device_fingerprint=topology.fingerprint,
        levels=levels,
        host_unified_memory=topology.host_unified_memory,
        truth_class=topology.truth_class,
        measured=topology.measured_by_chronus,
        notes=("unknown capacities remain null",),
    )


@dataclass(frozen=True)
class BufferAttestation:
    sequence: int
    digest: str
    dtype: str
    shape: tuple[int, ...]
    nbytes: int
    device_fingerprint: str
    hmac_sha256: str | None = None

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "digest": self.digest,
            "dtype": self.dtype,
            "shape": list(self.shape),
            "nbytes": self.nbytes,
            "device_fingerprint": self.device_fingerprint,
        }


class BufferIntegrityGate:
    """Digest and optionally authenticate host/device transfer buffers."""

    def __init__(self, authentication_key: bytes | None = None) -> None:
        if authentication_key is not None and (
            not isinstance(authentication_key, bytes) or not authentication_key
        ):
            raise GPUCapabilityError("authentication_key must be non-empty bytes")
        self._key = authentication_key
        self._next_sequence = 0
        self._last_verified = -1

    @staticmethod
    def _array(buffer: Any) -> np.ndarray:
        array = np.asarray(buffer)
        if array.dtype.hasobject:
            raise GPUCapabilityError("object buffers cannot cross the GPU integrity gate")
        return np.ascontiguousarray(array)

    @staticmethod
    def _digest(array: np.ndarray) -> str:
        metadata = json.dumps(
            {"dtype": array.dtype.str, "shape": list(array.shape)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(metadata + memoryview(array).cast("B")).hexdigest()

    def attest(self, buffer: Any, *, device_fingerprint: str = "") -> BufferAttestation:
        array = self._array(buffer)
        unsigned = BufferAttestation(
            sequence=self._next_sequence,
            digest=self._digest(array),
            dtype=array.dtype.str,
            shape=tuple(int(value) for value in array.shape),
            nbytes=int(array.nbytes),
            device_fingerprint=str(device_fingerprint),
        )
        self._next_sequence += 1
        signature = None
        if self._key is not None:
            payload = json.dumps(
                unsigned.unsigned_dict(), sort_keys=True, separators=(",", ":")
            ).encode()
            signature = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return BufferAttestation(
            sequence=unsigned.sequence,
            digest=unsigned.digest,
            dtype=unsigned.dtype,
            shape=unsigned.shape,
            nbytes=unsigned.nbytes,
            device_fingerprint=unsigned.device_fingerprint,
            hmac_sha256=signature,
        )

    def verify(self, buffer: Any, attestation: BufferAttestation) -> bool:
        if not isinstance(attestation, BufferAttestation):
            raise GPUCapabilityError("verify requires a BufferAttestation")
        if attestation.sequence <= self._last_verified:
            raise GPUCapabilityError("buffer attestation sequence was replayed or reordered")
        array = self._array(buffer)
        expected = self._digest(array)
        if not hmac.compare_digest(expected, attestation.digest):
            raise GPUCapabilityError("buffer digest mismatch")
        if array.dtype.str != attestation.dtype or tuple(array.shape) != attestation.shape:
            raise GPUCapabilityError("buffer dtype or shape mismatch")
        if int(array.nbytes) != attestation.nbytes:
            raise GPUCapabilityError("buffer byte count mismatch")
        if self._key is not None:
            payload = json.dumps(
                attestation.unsigned_dict(), sort_keys=True, separators=(",", ":")
            ).encode()
            expected_hmac = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_hmac, str(attestation.hmac_sha256)):
                raise GPUCapabilityError("buffer attestation authentication failed")
        elif attestation.hmac_sha256 is not None:
            raise GPUCapabilityError("authenticated attestation requires a configured key")
        self._last_verified = attestation.sequence
        return True


@dataclass(frozen=True)
class TensorInvariantReport:
    finite: bool
    bond_dimensions_valid: bool
    normalized: bool
    left_canonical_approx: bool
    norm: float
    max_canonical_residual: float
    entanglement_entropy_bits: float | None
    passed: bool
    checks: tuple[str, ...]


class TensorInvariantVerifier:
    """Verify finite values, TT/MPS bonds, norm, canonicality and entropy."""

    def __init__(self, tolerance: float = 1e-8) -> None:
        if tolerance <= 0 or not math.isfinite(float(tolerance)):
            raise GPUCapabilityError("tolerance must be finite and positive")
        self.tolerance = float(tolerance)

    def verify_cores(
        self,
        cores: Sequence[np.ndarray],
        *,
        require_normalized: bool = False,
    ) -> TensorInvariantReport:
        if not cores:
            raise GPUCapabilityError("at least one tensor-network core is required")
        arrays = [np.asarray(core) for core in cores]
        if any(core.ndim != 3 or core.size == 0 for core in arrays):
            raise GPUCapabilityError("cores must have shape (left, physical, right)")
        finite = all(bool(np.all(np.isfinite(core))) for core in arrays)
        bonds = arrays[0].shape[0] == 1 and arrays[-1].shape[-1] == 1
        bonds = bonds and all(
            left.shape[-1] == right.shape[0] for left, right in zip(arrays, arrays[1:])
        )
        residuals = []
        for core in arrays[:-1]:
            matrix = core.reshape(core.shape[0] * core.shape[1], core.shape[2])
            residuals.append(
                float(np.linalg.norm(matrix.conj().T @ matrix - np.eye(matrix.shape[1])))
            )
        max_residual = max(residuals, default=0.0)
        canonical = max_residual <= self.tolerance
        if bonds:
            vector = self._reconstruct(arrays)
            norm = float(np.linalg.norm(vector))
            normalized = abs(norm - 1.0) <= self.tolerance
            entropy = self._mid_entropy(vector, [core.shape[1] for core in arrays])
        else:
            norm = float("nan")
            normalized = False
            entropy = None
        passed = finite and bonds and canonical and (normalized or not require_normalized)
        return TensorInvariantReport(
            finite=finite,
            bond_dimensions_valid=bonds,
            normalized=normalized,
            left_canonical_approx=canonical,
            norm=norm,
            max_canonical_residual=max_residual,
            entanglement_entropy_bits=entropy,
            passed=passed,
            checks=("finite", "bond_dimensions", "norm", "left_canonical", "mid_entropy"),
        )

    @staticmethod
    def _reconstruct(cores: Sequence[np.ndarray]) -> np.ndarray:
        state = cores[0]
        for core in cores[1:]:
            state = np.tensordot(state, core, axes=([-1], [0]))
        return np.squeeze(state, axis=(0, -1)).reshape(-1)

    @staticmethod
    def _mid_entropy(vector: np.ndarray, physical_dims: Sequence[int]) -> float | None:
        if len(physical_dims) < 2:
            return 0.0
        split = len(physical_dims) // 2
        left = math.prod(physical_dims[:split])
        right = math.prod(physical_dims[split:])
        if left * right != vector.size:
            return None
        singular = np.linalg.svd(vector.reshape(left, right), compute_uv=False)
        probabilities = singular**2
        total = float(probabilities.sum())
        if total <= 0:
            return None
        probabilities = probabilities / total
        probabilities = probabilities[probabilities > 1e-15]
        return max(0.0, float(-np.sum(probabilities * np.log2(probabilities))))


@dataclass(frozen=True)
class TensorExecutionEvidence:
    operation: str
    backend: str
    hardware_executed: bool
    verified_against_kellogg: bool
    max_abs_error: float
    device_id: str = ""


class ChronusTensorPipeline:
    """Hardware-facing adapter over Kellogg tensor-network mathematics."""

    def __init__(
        self,
        *,
        integrity_gate: BufferIntegrityGate | None = None,
        invariant_verifier: TensorInvariantVerifier | None = None,
    ) -> None:
        self.integrity_gate = integrity_gate or BufferIntegrityGate()
        self.invariants = invariant_verifier or TensorInvariantVerifier()

    @staticmethod
    def _kellogg():
        import kellogg

        return kellogg

    def decompose(
        self,
        tensor: np.ndarray,
        method: str,
        *,
        max_rank: int = 32,
        tolerance: float = 0.0,
    ) -> Any:
        k = self._kellogg()
        name = str(method).strip().lower()
        if name == "tt":
            return k.TensorTrain(tensor, max_rank=max_rank, tolerance=tolerance)
        if name == "mps":
            size = int(np.asarray(tensor).size)
            sites = int(math.log2(size)) if size > 0 else -1
            if sites < 0 or 2**sites != size:
                raise GPUCapabilityError("MPS decomposition requires a power-of-two state size")
            return k.mps_decompose(np.asarray(tensor).reshape(-1), sites, max_rank)
        raise GPUCapabilityError("method must be 'tt' or 'mps'; MPO is an operator representation")

    def compress(
        self,
        tensor: np.ndarray,
        *,
        max_rank: int,
        max_rel_error: float,
    ) -> tuple[list[Any], float]:
        return self._kellogg().tt_compress_with_budget(
            tensor, max_rel_error=max_rel_error, max_rank=max_rank
        )

    def apply_mpo(
        self,
        operator: Any,
        vector: np.ndarray,
        *,
        require_device: bool = False,
        tolerance: float = 1e-5,
    ) -> tuple[np.ndarray, TensorExecutionEvidence]:
        expected = np.asarray(operator.apply_to_vector(vector))
        if not require_device:
            return expected, TensorExecutionEvidence(
                operation="mpo_apply",
                backend="kellogg-host",
                hardware_executed=False,
                verified_against_kellogg=True,
                max_abs_error=0.0,
            )
        try:
            from .tensor_compute import get_tensor_runtime

            runtime = get_tensor_runtime()
            matrix = np.asarray(operator.to_full_matrix(), dtype=np.float32)
            column = np.asarray(vector, dtype=np.float32).reshape(-1, 1)
            actual = runtime.execute(
                "matmul",
                [matrix, column],
                [matrix.shape, column.shape],
                (matrix.shape[0], 1),
            ).reshape(-1)
        except Exception as exc:
            raise GPUCapabilityError(f"Chronus device MPO execution unavailable: {exc}") from exc
        error = float(np.max(np.abs(actual.astype(complex) - expected.astype(complex))))
        if error > tolerance:
            raise GPUCapabilityError(
                f"Chronus MPO result differs from Kellogg by {error:.3e} > {tolerance:.3e}"
            )
        return actual, TensorExecutionEvidence(
            operation="mpo_apply",
            backend="chronus-opencl",
            hardware_executed=True,
            verified_against_kellogg=True,
            max_abs_error=error,
            device_id=str(runtime.device_id),
        )

    def serialize(
        self,
        path: str | Path,
        tensor: Any,
        *,
        authentication_key: bytes | None = None,
    ) -> int:
        return self._kellogg().save_pv(path, tensor, authentication_key)

    def deserialize(
        self,
        path: str | Path,
        *,
        authentication_key: bytes | None = None,
    ) -> Any:
        return self._kellogg().load_pv(path, authentication_key)

    def verify_network(
        self,
        network: Any,
        *,
        require_normalized: bool = False,
    ) -> TensorInvariantReport:
        cores = getattr(network, "cores", network)
        return self.invariants.verify_cores(cores, require_normalized=require_normalized)


def gpu_capability_status() -> dict[str, dict[str, str]]:
    """Machine-readable closure matrix for the requested July capabilities."""
    return {
        "geodesic_scheduling": {"status": "present", "owner": "chronus.phi_gpu"},
        "memory_hierarchy": {
            "status": "present_and_evidence_profile_added",
            "owner": "chronus.v33.memory + chronus.gpu_capabilities",
        },
        "gpu_topology_specs": {
            "status": "present_and_runtime_probe_added",
            "owner": "chronus.gpu_reference + chronus.gpu_capabilities",
        },
        "integrity_gates": {"status": "added", "owner": "chronus.gpu_capabilities"},
        "tensor_network_decomposition": {
            "status": "present_and_kellogg_adapter_added",
            "owner": "kellogg; executed by chronus",
        },
        "mps_tt_mpo": {
            "status": "present_and_public_pipeline_added",
            "owner": "kellogg; executed by chronus",
        },
        "compression": {
            "status": "present_and_error_budget_adapter_added",
            "owner": "kellogg + chronus.v33.compression",
        },
        "serialization": {
            "status": "added_safe_adapter",
            "owner": "kellogg persistence; transferred by chronus",
        },
        "invariant_verification": {
            "status": "added",
            "owner": "chronus.gpu_capabilities",
        },
    }


__all__ = [
    "BufferAttestation",
    "BufferIntegrityGate",
    "ChronusTensorPipeline",
    "GPUCapabilityError",
    "GPUDeviceTopology",
    "GPUMemoryHierarchyProfile",
    "GPUMemoryLevel",
    "TensorExecutionEvidence",
    "TensorInvariantReport",
    "TensorInvariantVerifier",
    "TopologyLink",
    "gpu_capability_status",
    "memory_hierarchy_from_topology",
    "probe_opencl_topology",
    "reference_gpu_topology",
]
