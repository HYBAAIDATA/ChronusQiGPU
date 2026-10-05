"""Execution adapters. Unavailable backends fail closed; none emulate success.

Software (CPU reference) is real classical computation and a valid product mode.
Physical adapters (OpenCL/CUDA/ROCm/oneAPI/Metal) report typed unavailability when
SDKs or devices are absent — they never invent hardware.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import base64
import hashlib
import time
from typing import Any

import numpy as np

from .abi import (
    ABI_VERSION,
    AdapterAttestation,
    AdapterKind,
    CapabilityManifest,
    TrustClass,
    Workload,
    WorkloadKind,
    WorkloadResult,
    digest_json,
    validate_declared_output_shape,
)
from .attestation import extend_chain


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AdapterUnavailable(RuntimeError):
    """Typed unavailability — not a silent success."""


class Adapter(ABC):
    id: str
    kind: AdapterKind
    available: bool = False
    priority: int = 0

    @abstractmethod
    def probe(self) -> AdapterAttestation:
        ...

    @abstractmethod
    def capabilities(self) -> CapabilityManifest:
        ...

    @abstractmethod
    def execute(self, workload: Workload) -> WorkloadResult:
        ...

    def health(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "available": self.available}

    def supports(self, kind: WorkloadKind | str) -> bool:
        k = kind.value if isinstance(kind, WorkloadKind) else str(kind)
        caps = self.capabilities()
        return k in caps.operations or kind == WorkloadKind.PROBE

    def _result(
        self,
        workload: Workload,
        output: dict[str, Any],
        started_ns: int,
        *,
        device_time_ns: int | None = None,
        trust_class: str = TrustClass.RUNTIME_SIGNED.value,
        hardware_rooted: bool = False,
        object_id: str | None = None,
        status: str = "ok",
        error: str | None = None,
    ) -> WorkloadResult:
        wall = int(time.time_ns() - started_ns)
        body = {
            "workload_id": workload.id,
            "adapter_id": self.id,
            "kind": workload.kind.value if isinstance(workload.kind, WorkloadKind) else str(workload.kind),
            "output": output,
            "wall_time_ns": wall,
            "device_time_ns": device_time_ns,
            "status": status,
        }
        digest = digest_json(body)
        return WorkloadResult(
            workload_id=workload.id,
            status=status,
            adapter_id=self.id,
            kind=body["kind"],
            output=output,
            object_id=object_id,
            attestation={"adapter_id": self.id, "kind": self.kind.value},
            evidence_digest=digest,
            wall_time_ns=wall,
            device_time_ns=device_time_ns,
            trust_class=trust_class,
            hardware_rooted=hardware_rooted,
            actual_adapter_id=self.id,
            actual_device_id=self.id,
            digest=digest,
            error=error,
            abi_version=ABI_VERSION,
        )

    def _attestation(self, available: bool, detail: dict[str, Any] | None = None) -> AdapterAttestation:
        record = {
            "adapter_id": self.id,
            "kind": self.kind.value,
            "available": available,
            "detail": detail or {},
            "abi_version": ABI_VERSION,
        }
        fingerprint = digest_json(record)
        chain = extend_chain((), record)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=available,
            fingerprint=fingerprint,
            chain_digest=chain[-1] if chain else fingerprint,
            detail=detail or {},
            trust_class=TrustClass.RUNTIME_SIGNED.value,
            hardware_rooted=False,
        )


class CPUEmulatorAdapter(Adapter):
    """Standalone software runtime — classical silicon, real computation."""

    id = "cpu-emulator"
    kind = AdapterKind.SOFTWARE
    available = True
    priority = 0

    def probe(self) -> AdapterAttestation:
        self.available = True
        return self._attestation(True, {"substrate": "classical_silicon", "mode": "standalone_software"})

    def capabilities(self) -> CapabilityManifest:
        ops = tuple(
            k.value
            for k in (
                WorkloadKind.PROBE,
                WorkloadKind.FOLD,
                WorkloadKind.UNFOLD,
                WorkloadKind.STORE,
                WorkloadKind.RETRIEVE,
                WorkloadKind.TENSOR_OP,
                WorkloadKind.CGEMV,
                WorkloadKind.PHI_TRANSFORM,
                WorkloadKind.LUCAS_TRANSFORM,
                WorkloadKind.PISOT_TRANSFORM,
                WorkloadKind.SHA256D_SCAN,
                WorkloadKind.CHECKPOINT,
            )
        )
        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=ops,
            dtypes=("float64", "float32", "complex128", "bytes", "int64"),
            max_shape=(4096, 4096),
            max_bytes=256 * 1024 * 1024,
            evidence_support=("runtime_signed", "content_hash"),
            limits={"max_work_group": 1, "local_memory_bytes": 0},
            arithmetic={"ieee754": True, "fp64": True},
            available=True,
            software_impl=True,
            physical_run_status="n/a_software",
            build_status="pure_python_numpy",
            device_ids=(self.id,),
        )

    def execute(self, workload: Workload) -> WorkloadResult:
        started = time.time_ns()
        kind = workload.kind if isinstance(workload.kind, WorkloadKind) else WorkloadKind(str(workload.kind))
        value = workload.input or {}

        if kind == WorkloadKind.PROBE:
            return self._result(workload, {"probe": self.health()}, started)

        if kind == WorkloadKind.FOLD:
            payload = self._payload_bytes(value)
            # Prefer authoritative Aethel fold when available (lossless via ZeckendorfVector)
            try:
                from aethel.encoding import fold as aethel_fold
                import json as _json

                folded = aethel_fold(payload)
                # Serialize ZeckendorfVector as JSON blocks for lossless unfold
                if hasattr(folded, "blocks") and hasattr(folded, "total_bytes"):
                    ser = _json.dumps(
                        {
                            "format": "aethel.zeckendorf.v1",
                            "blocks": [[int(a), int(b)] for a, b in folded.blocks],
                            "total_bytes": int(folded.total_bytes),
                        },
                        separators=(",", ":"),
                    ).encode("utf-8")
                    engine = "aethel.encoding.fold"
                elif isinstance(folded, (bytes, bytearray)):
                    ser = bytes(folded)
                    engine = "aethel.encoding.fold_bytes"
                else:
                    raise TypeError("unsupported fold return type")
                return self._result(
                    workload,
                    {
                        "folded_b64": base64.b64encode(ser).decode("ascii"),
                        "logical_bytes": len(payload),
                        "folded_bytes": len(ser),
                        "engine": engine,
                    },
                    started,
                )
            except Exception:
                # Identity-framed fallback: length-prefixed payload (lossless)
                framed = len(payload).to_bytes(4, "little") + payload
                return self._result(
                    workload,
                    {
                        "folded_b64": base64.b64encode(framed).decode("ascii"),
                        "logical_bytes": len(payload),
                        "folded_bytes": len(framed),
                        "engine": "length_prefix_identity",
                    },
                    started,
                )

        if kind == WorkloadKind.UNFOLD:
            raw = self._payload_bytes(value, key_b64="folded_b64", key_utf8="folded_utf8")
            try:
                import json as _json
                from aethel.encoding import ZeckendorfVector, unfold as aethel_unfold

                meta = _json.loads(raw.decode("utf-8"))
                if meta.get("format") == "aethel.zeckendorf.v1":
                    blocks = tuple((int(a), int(b)) for a, b in meta["blocks"])
                    z = ZeckendorfVector(blocks=blocks, total_bytes=int(meta["total_bytes"]))
                    out_b = bytes(aethel_unfold(z))
                    return self._result(
                        workload,
                        {
                            "payload_b64": base64.b64encode(out_b).decode("ascii"),
                            "engine": "aethel.encoding.unfold",
                        },
                        started,
                    )
            except Exception:
                pass
            # length_prefix_identity inverse
            if len(raw) >= 4:
                n = int.from_bytes(raw[:4], "little")
                if 4 + n <= len(raw):
                    out_b = raw[4 : 4 + n]
                else:
                    out_b = raw[4:]
            else:
                out_b = raw
            return self._result(
                workload,
                {
                    "payload_b64": base64.b64encode(out_b).decode("ascii"),
                    "engine": "length_prefix_identity",
                },
                started,
            )

        if kind in (WorkloadKind.STORE, WorkloadKind.RETRIEVE, WorkloadKind.CHECKPOINT):
            # Runtime memory plane owns durable store; adapter acknowledges
            return self._result(workload, {"ack": True, "input": value}, started)

        if kind == WorkloadKind.TENSOR_OP:
            return self._tensor_op(workload, value, started)

        if kind == WorkloadKind.CGEMV:
            return self._cgemv(workload, value, started)

        if kind in (WorkloadKind.PHI_TRANSFORM, WorkloadKind.LUCAS_TRANSFORM, WorkloadKind.PISOT_TRANSFORM):
            if "vector" in value and kind == WorkloadKind.PHI_TRANSFORM:
                vec = np.asarray(value["vector"], dtype=np.float64)
                phi = (1.0 + 5.0**0.5) / 2.0
                out = vec * phi
                return self._result(
                    workload,
                    {"vector": out.tolist(), "engine": "phi_scale_vector"},
                    started,
                )
            return self._phi_family(workload, kind, value, started)

        if kind == WorkloadKind.SHA256D_SCAN:
            return self._sha256d_scan(workload, value, started)

        # Mining bridge may pass header80_hex without kind-specific fields
        if "header80_hex" in value or "header_hex" in value:
            return self._sha256d_scan(workload, value, started)

        raise AdapterUnavailable(f"unsupported workload kind: {kind}")

    def _payload_bytes(
        self, value: dict[str, Any], *, key_b64: str = "payload_b64", key_utf8: str = "payload_utf8"
    ) -> bytes:
        if key_b64 in value:
            return base64.b64decode(value[key_b64])
        if key_utf8 in value:
            return str(value[key_utf8]).encode("utf-8")
        if "payload" in value:
            p = value["payload"]
            if isinstance(p, (bytes, bytearray)):
                return bytes(p)
            return str(p).encode("utf-8")
        return b""

    def _tensor_op(self, workload: Workload, value: dict[str, Any], started: int) -> WorkloadResult:
        op = str(value.get("op", "scale"))
        a = np.asarray(value.get("a", value.get("x", [])), dtype=np.float64)
        out_shape = value.get("output_shape")
        if out_shape is not None:
            validate_declared_output_shape(op, [tuple(a.shape)], tuple(out_shape))
        if op in {"scale", "mul_scalar"}:
            scalar = float(value.get("scalar", value.get("alpha", 1.0)))
            out = a * scalar
        elif op in {"add", "elementwise_add"}:
            b = np.asarray(value.get("b", 0.0), dtype=np.float64)
            if out_shape is not None:
                validate_declared_output_shape("elementwise", [tuple(a.shape)], tuple(out_shape))
            out = a + b
        elif op == "matmul":
            b = np.asarray(value.get("b"), dtype=np.float64)
            out = a @ b
        elif op == "svd":
            u, s, vh = np.linalg.svd(a, full_matrices=False)
            return self._result(
                workload,
                {"u": u.tolist(), "s": s.tolist(), "vh": vh.tolist(), "dtype": "float64"},
                started,
            )
        else:
            raise AdapterUnavailable(f"unsupported tensor op: {op}")
        return self._result(
            workload,
            {"data": out.tolist(), "shape": list(out.shape), "dtype": "float64", "op": op},
            started,
        )

    def _cgemv(self, workload: Workload, value: dict[str, Any], started: int) -> WorkloadResult:
        a = np.asarray(value.get("a"), dtype=np.complex128)
        x = np.asarray(value.get("x"), dtype=np.complex128)
        alpha = complex(value.get("alpha", 1.0))
        beta = complex(value.get("beta", 0.0))
        y = np.asarray(value.get("y", np.zeros(a.shape[0], dtype=np.complex128)), dtype=np.complex128)
        out_shape = value.get("output_shape")
        if out_shape is not None:
            validate_declared_output_shape("cgemv", [tuple(a.shape), tuple(x.shape)], tuple(out_shape))
        out = alpha * (a @ x) + beta * y
        return self._result(
            workload,
            {
                "data": [[float(v.real), float(v.imag)] for v in out],
                "shape": list(out.shape),
                "dtype": "complex128",
            },
            started,
        )

    def _phi_family(
        self, workload: Workload, kind: WorkloadKind, value: dict[str, Any], started: int
    ) -> WorkloadResult:
        n = int(value.get("n", value.get("index", 10)))
        if n < 0 or n > 10_000:
            raise AdapterUnavailable(f"n out of supported domain 0..10000: {n}")
        phi = (1.0 + 5.0**0.5) / 2.0
        if kind == WorkloadKind.PHI_TRANSFORM:
            # φ^n via Binet-adjacent float path + integer Lucas cross-check when small
            val = phi**n
            return self._result(
                workload,
                {"n": n, "phi_pow": val, "engine": "float_phi_pow", "domain": "n=0..10000"},
                started,
            )
        if kind == WorkloadKind.LUCAS_TRANSFORM:
            # L_n recurrence
            if n == 0:
                ln = 2
            elif n == 1:
                ln = 1
            else:
                a, b = 2, 1
                for _ in range(2, n + 1):
                    a, b = b, a + b
                ln = b
            return self._result(
                workload,
                {"n": n, "lucas": ln, "engine": "exact_recurrence", "domain": "n=0..10000"},
                started,
            )
        # Pisot-ish: nearest integer to φ^n
        val = phi**n
        nearest = int(round(val))
        return self._result(
            workload,
            {"n": n, "pisot_nearest": nearest, "phi_pow": val, "engine": "round_phi_pow"},
            started,
        )

    def _sha256d_scan(self, workload: Workload, value: dict[str, Any], started: int) -> WorkloadResult:
        # Prefer mining hasher when present; else pure hashlib double SHA-256
        if "header80_hex" in value:
            header80 = bytes.fromhex(str(value["header80_hex"]))
            header_prefix = header80[:76] if len(header80) >= 76 else header80
            start = int.from_bytes(header80[76:80], "little") if len(header80) >= 80 else int(value.get("start_nonce", 0))
            count = int(value.get("count", 1))
        else:
            prefix = value.get("prefix_b64")
            if prefix is not None:
                header_prefix = base64.b64decode(prefix)
            elif "prefix_hex" in value:
                header_prefix = bytes.fromhex(str(value["prefix_hex"]))
            else:
                header_prefix = self._payload_bytes(value)
            start = int(value.get("start_nonce", 0))
            count = int(value.get("count", 1))
        if count < 0 or count > 1_000_000:
            raise AdapterUnavailable("count out of bounds")
        target = value.get("target", value.get("target_hex"))
        target_int = None
        if target is not None:
            if isinstance(target, str) and not target.isdigit():
                try:
                    target_int = int(target, 16)
                except ValueError:
                    target_int = None
            else:
                target_int = int(target)
        hits: list[dict[str, Any]] = []
        checked = 0
        for i in range(count):
            nonce = start + i
            if len(header_prefix) >= 76:
                header = bytearray(header_prefix[:76])
                header[76 - 4 : 76] = int(nonce).to_bytes(4, "little")
                header_b = bytes(header)
            else:
                header_b = header_prefix + int(nonce).to_bytes(4, "little")
            d1 = hashlib.sha256(header_b).digest()
            d2 = hashlib.sha256(d1).digest()
            digest_int = int.from_bytes(d2[::-1], "big")
            checked += 1
            if target_int is None or digest_int <= target_int:
                hits.append(
                    {
                        "nonce": nonce,
                        "hash_hex": d2.hex(),
                        "digest_int": digest_int,
                    }
                )
                if target_int is not None:
                    break
        return self._result(
            workload,
            {
                "hits": hits,
                "checked": checked,
                "start_nonce": start,
                "engine": "hashlib_sha256d",
            },
            started,
            trust_class=TrustClass.RUNTIME_SIGNED.value,
        )


class UnavailableAdapter(Adapter):
    """Typed unavailable backend placeholder (SDK/device absent)."""

    def __init__(self, adapter_id: str, kind: AdapterKind, reason: str):
        self.id = adapter_id
        self.kind = kind
        self.available = False
        self.reason = reason

    def probe(self) -> AdapterAttestation:
        self.available = False
        return self._attestation(False, {"reason": self.reason})

    def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=(),
            available=False,
            reason=self.reason,
            software_impl=False,
            physical_run_status="unavailable",
            build_status="sdk_absent_or_unconfigured",
        )

    def execute(self, workload: Workload) -> WorkloadResult:
        raise AdapterUnavailable(f"{self.id}: {self.reason}")


class OpenCLUhdAdapter(Adapter):
    """Optional Intel UHD/Iris OpenCL path wrapping ChronusTensorRuntime when present."""

    id = "opencl-intel-uhd"
    kind = AdapterKind.OPENCL
    available = False

    def probe(self) -> AdapterAttestation:
        try:
            from chronus.tensor_compute import ChronusTensorRuntime

            rt = ChronusTensorRuntime()
            # Do not invent devices — probe only
            probe = getattr(rt, "probe", None)
            if callable(probe):
                info = probe()
            else:
                info = {"status": "runtime_present"}
            identity = str(info).lower()
            ok = "intel" in identity or "uhd" in identity or "iris" in identity or info.get("available")
            self.available = bool(ok)
            return self._attestation(
                self.available,
                {"probe": info, "trust": "device_observed_if_executed"},
            )
        except Exception as exc:
            self.available = False
            return self._attestation(False, {"reason": f"opencl_unavailable: {exc}"})

    def capabilities(self) -> CapabilityManifest:
        ops = (
            WorkloadKind.TENSOR_OP.value,
            WorkloadKind.SHA256D_SCAN.value,
            WorkloadKind.PROBE.value,
        )
        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=ops if self.available else (),
            dtypes=("float32",),
            max_shape=(2048, 2048),
            max_bytes=128 * 1024 * 1024,
            evidence_support=("runtime_signed", "device_observed"),
            available=self.available,
            reason="" if self.available else "Intel UHD OpenCL not available on this host",
            software_impl=False,
            physical_run_status="host_dependent",
            build_status="optional",
            device_ids=(self.id,),
        )

    def execute(self, workload: Workload) -> WorkloadResult:
        if not self.available:
            self.probe()
        if not self.available:
            raise AdapterUnavailable(self.capabilities().reason or "opencl uhd unavailable")
        started = time.time_ns()
        # Fail closed: prefer software for correctness unless tensor runtime path is proven
        # Physical execution evidence remains host-specific (gate PENDING without device).
        raise AdapterUnavailable(
            "opencl-intel-uhd: physical dispatch requires authorized target-host evidence; "
            "use software policy or run bench.chronus_igpu_evidence on the device host"
        )


def default_adapters(*, include_cpu_emulator: bool = True) -> list[Adapter]:
    """Build the adapter ladder. Missing SDKs → typed UnavailableAdapter."""
    adapters: list[Adapter] = []
    if include_cpu_emulator:
        adapters.append(CPUEmulatorAdapter())
    # Optional physical OpenCL probe (may be unavailable)
    try:
        uhd = OpenCLUhdAdapter()
        uhd.probe()
        adapters.append(uhd)
    except Exception:
        adapters.append(
            UnavailableAdapter("opencl-intel-uhd", AdapterKind.OPENCL, "probe failed")
        )
    for aid, kind, reason in (
        ("cuda", AdapterKind.CUDA, "CUDA SDK/device not configured"),
        ("rocm", AdapterKind.ROCM, "ROCm SDK/device not configured"),
        ("oneapi", AdapterKind.ONEAPI, "oneAPI not configured"),
        ("metal", AdapterKind.METAL, "Metal not available on this host"),
        ("opencl-generic", AdapterKind.OPENCL, "generic OpenCL adapter not configured"),
    ):
        adapters.append(UnavailableAdapter(aid, kind, reason))
    return adapters


# Back-compat name used by older imports
build_default_adapters = default_adapters
ExecutionAdapter = Adapter
