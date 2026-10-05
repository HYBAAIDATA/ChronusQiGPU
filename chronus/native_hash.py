"""Chronus-owned native SHA-256d execution (CUDA + Metal).

OpenCL remains a first-class substrate under ``chronus-opencl`` /
``mining.bitcoin_hasher``. This module adds independent mining hash paths:

* ``chronus-cuda``  — Chronus CUDA C kernels via CuPy RawModule
* ``chronus-metal`` — Apple GPU path when a Metal-capable stack is present

Rules (aligned with native tensor delivery):
  * ``opencl_required = False`` for CUDA and Metal
  * **No silent fallback** between CUDA ↔ Metal ↔ OpenCL ↔ CPU
  * Explicit backend request fails closed when the runtime/device is absent
  * Host ``hashlib`` re-verification remains the mining accept authority
  * Physical performance claims require target-host evidence (not this module alone)

Tensor ops live in ``chronus.native_tensor``; this module is **mining SHA-256d only**.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence
import time

import numpy as np

_KERNELS_DIR = Path(__file__).resolve().parent / "kernels"
_CUDA_SOURCE_PATH = _KERNELS_DIR / "bitcoin_sha256d.cu"


@dataclass(frozen=True)
class NativeHashProbe:
    backend_id: str
    available: bool
    opencl_required: bool = False
    device_name: str = ""
    device_index: int | None = None
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    physical_run_status: str = "unverified"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NativeHashResult:
    digests: np.ndarray  # (count, 32) uint8
    backend_id: str
    device_name: str
    wall_time_ns: int
    device_time_ns: int | None
    kernel_identity: str
    opencl_required: bool = False
    hardware_rooted: bool = False  # never claimed here without attestation
    checked: int = 0

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["digests_shape"] = list(self.digests.shape)
        d.pop("digests", None)
        return d


class NativeHashUnavailable(RuntimeError):
    """Typed fail-closed error — never rewrite to another backend."""


def _load_cupy():
    try:
        import cupy as cp  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise NativeHashUnavailable(f"CuPy/CUDA runtime unavailable: {exc}") from exc
    return cp


def probe_cuda() -> NativeHashProbe:
    """Report CUDA hash path only after a real CUDA device is enumerated."""
    try:
        cp = _load_cupy()
        count = int(cp.cuda.runtime.getDeviceCount())
        if count <= 0:
            return NativeHashProbe(
                backend_id="chronus-cuda",
                available=False,
                opencl_required=False,
                reason="CUDA runtime present but device count is 0",
            )
        index = 0
        props = dict(cp.cuda.runtime.getDeviceProperties(index))
        name = props.get("name")
        if isinstance(name, (bytes, bytearray)):
            name = name.decode("utf-8", errors="replace")
        name = str(name or f"cuda:{index}")
        return NativeHashProbe(
            backend_id="chronus-cuda",
            available=True,
            opencl_required=False,
            device_name=name,
            device_index=index,
            detail={"device_count": count, "props_keys": sorted(str(k) for k in props.keys())[:12]},
            physical_run_status="host_dependent",
        )
    except NativeHashUnavailable as exc:
        return NativeHashProbe(
            backend_id="chronus-cuda",
            available=False,
            opencl_required=False,
            reason=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        return NativeHashProbe(
            backend_id="chronus-cuda",
            available=False,
            opencl_required=False,
            reason=f"cuda_probe_failed: {exc}",
        )


def probe_metal() -> NativeHashProbe:
    """Report Metal hash path only when an Apple GPU stack is actually usable."""
    # Prefer MLX (common Chronus/Apple path); fall back to metal/pyobjc signals.
    try:
        import mlx.core as mx  # type: ignore

        # MLX default device
        try:
            dev = mx.default_device()
            name = str(dev)
        except Exception:
            name = "mlx-default"
        # Require GPU-ish device, not pure CPU
        lname = name.lower()
        if "cpu" in lname and "gpu" not in lname:
            return NativeHashProbe(
                backend_id="chronus-metal",
                available=False,
                opencl_required=False,
                reason=f"MLX default device is CPU-only: {name}",
                device_name=name,
            )
        return NativeHashProbe(
            backend_id="chronus-metal",
            available=True,
            opencl_required=False,
            device_name=name,
            detail={"stack": "mlx"},
            physical_run_status="host_dependent",
        )
    except Exception as mlx_exc:  # noqa: BLE001
        mlx_reason = f"mlx_unavailable: {mlx_exc}"
    # Secondary: Metal framework presence without full kernel path yet
    try:
        import Metal  # type: ignore  # noqa: F401

        return NativeHashProbe(
            backend_id="chronus-metal",
            available=False,
            opencl_required=False,
            reason="Metal framework importable but Chronus Metal SHA-256d kernel stack not bound (MLX preferred)",
            detail={"stack": "metal_framework_only", "mlx": mlx_reason},
            physical_run_status="unavailable",
        )
    except Exception as metal_exc:  # noqa: BLE001
        return NativeHashProbe(
            backend_id="chronus-metal",
            available=False,
            opencl_required=False,
            reason=f"{mlx_reason}; metal_framework: {metal_exc}",
        )


def _cuda_module(cp):
    source = _CUDA_SOURCE_PATH.read_text(encoding="utf-8")
    # CuPy RawModule
    return cp.RawModule(code=source, options=("-std=c++11",))


def sha256d_batch_cuda(
    header80: bytes | bytearray,
    nonces: Sequence[int] | np.ndarray,
    *,
    device_index: int | None = None,
) -> NativeHashResult:
    """Execute Chronus CUDA SHA-256d. Fail closed — no OpenCL/CPU rewrite."""
    if len(header80) != 80:
        raise ValueError("header80 must be exactly 80 bytes")
    probe = probe_cuda()
    if not probe.available:
        raise NativeHashUnavailable(
            f"chronus-cuda requested but unavailable: {probe.reason}"
        )
    cp = _load_cupy()
    idx = int(device_index if device_index is not None else (probe.device_index or 0))
    with cp.cuda.Device(idx):
        mod = _cuda_module(cp)
        kernel = mod.get_function("bitcoin_sha256d")
        nonce_arr = np.asarray(list(nonces), dtype=np.uint32)
        count = int(nonce_arr.size)
        if count <= 0:
            raise ValueError("nonces must be non-empty")
        if count > 1_048_576:
            raise NativeHashUnavailable("cuda sha256d batch exceeds 1<<20 bound")

        d_header = cp.asarray(np.frombuffer(bytes(header80), dtype=np.uint8))
        d_nonces = cp.asarray(nonce_arr)
        d_digests = cp.zeros((count, 32), dtype=cp.uint8)

        block = 256
        grid = (count + block - 1) // block
        started = time.time_ns()
        kernel(
            (grid,),
            (block,),
            (d_header, d_nonces, d_digests, np.uint32(count)),
        )
        cp.cuda.get_current_stream().synchronize()
        wall = int(time.time_ns() - started)
        host = cp.asnumpy(d_digests)

    return NativeHashResult(
        digests=host,
        backend_id="chronus-cuda",
        device_name=probe.device_name,
        wall_time_ns=wall,
        device_time_ns=wall,  # stream sync wall; finer GPU timers optional later
        kernel_identity="chronus.kernels.bitcoin_sha256d.cu::bitcoin_sha256d",
        opencl_required=False,
        hardware_rooted=False,
        checked=count,
    )


def sha256d_batch_metal(
    header80: bytes | bytearray,
    nonces: Sequence[int] | np.ndarray,
) -> NativeHashResult:
    """Metal SHA-256d path.

    Current contract: fail closed unless a verified Metal/MLX mining kernel is
    bound. We do **not** silently run CPU hashlib and label it Metal.
    """
    if len(header80) != 80:
        raise ValueError("header80 must be exactly 80 bytes")
    probe = probe_metal()
    if not probe.available:
        raise NativeHashUnavailable(
            f"chronus-metal requested but unavailable: {probe.reason}"
        )
    # Explicit: no CPU emulation under Metal identity
    raise NativeHashUnavailable(
        "chronus-metal: Apple GPU SHA-256d kernel binding not yet production-verified "
        "on this host build; refuse CPU-labeled-as-Metal. "
        "Use backend=opencl or backend=cpu explicitly, or complete Metal kernel bring-up."
    )


def sha256d_batch(
    backend: str,
    header80: bytes | bytearray,
    nonces: Sequence[int] | np.ndarray,
    **kwargs: Any,
) -> NativeHashResult:
    """Dispatch to a **named** native backend. No cross-backend fallback."""
    b = str(backend).lower().strip()
    if b in {"cuda", "chronus-cuda", "gpu-cuda"}:
        return sha256d_batch_cuda(header80, nonces, **kwargs)
    if b in {"metal", "chronus-metal", "gpu-metal"}:
        return sha256d_batch_metal(header80, nonces)
    raise NativeHashUnavailable(
        f"unknown native hash backend {backend!r}; "
        "use chronus-cuda | chronus-metal (OpenCL/CPU are separate substrates)"
    )


def reference_sha256d_batch(
    header80: bytes | bytearray,
    nonces: Sequence[int] | np.ndarray,
) -> np.ndarray:
    """CPU hashlib reference for conformance (not a native GPU backend)."""
    import hashlib

    if len(header80) != 80:
        raise ValueError("header80 must be exactly 80 bytes")
    out = np.zeros((len(list(nonces)), 32), dtype=np.uint8)
    base = bytearray(header80)
    for i, n in enumerate(nonces):
        base[76:80] = int(n).to_bytes(4, "little")
        d1 = hashlib.sha256(bytes(base)).digest()
        d2 = hashlib.sha256(d1).digest()
        out[i] = np.frombuffer(d2, dtype=np.uint8)
    return out


__all__ = [
    "NativeHashProbe",
    "NativeHashResult",
    "NativeHashUnavailable",
    "probe_cuda",
    "probe_metal",
    "sha256d_batch",
    "sha256d_batch_cuda",
    "sha256d_batch_metal",
    "reference_sha256d_batch",
]
