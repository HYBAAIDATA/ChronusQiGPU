"""Exact Lucas/Pisot ladder and strict OpenCL execution boundary."""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from .core import fib, lucas

from lucas.ladder import SCALE_RUNGS

LUCAS_PISOT_LADDER = tuple(SCALE_RUNGS)

# Bespoke HYBA iGPU identity — same contract as mining/bitcoin_hasher.py.
# Duplicated deliberately: this substrate module must not import siblings.
DEFAULT_HYBA_ALIASES = ("hyba-mla1517", "hyba_mla1517", "mla1517", "hyba")


def _hyba_aliases() -> tuple:
    raw = os.environ.get("HYBA_DEVICE_ALIAS", "").strip()
    if raw:
        return tuple(a.strip().lower() for a in raw.split(",") if a.strip())
    return DEFAULT_HYBA_ALIASES


def _require_hyba() -> bool:
    return os.environ.get("HYBA_REQUIRE_HYBA", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _identity_tokens(name: str) -> tuple:
    raw = os.environ.get(name, "").strip()
    return tuple(token.strip().casefold() for token in raw.split(",") if token.strip())


def _device_matches_identity(dev) -> bool:
    device_name = str(getattr(dev, "name", "")).strip().casefold()
    vendor = str(getattr(dev, "vendor", "")).strip().casefold()
    required_name = os.environ.get("HYBA_DEVICE_NAME", "").strip().casefold()
    required_vendor = os.environ.get("HYBA_DEVICE_VENDOR", "").strip().casefold()
    pci_ids = _identity_tokens("HYBA_DEVICE_PCI_IDS")
    if required_name and device_name != required_name:
        return False
    if required_vendor and required_vendor not in vendor:
        return False
    if pci_ids and not any(token in device_name for token in pci_ids):
        return False
    return True


def _identity_configured() -> bool:
    return bool(
        os.environ.get("HYBA_DEVICE_NAME", "").strip()
        or os.environ.get("HYBA_DEVICE_VENDOR", "").strip()
        or os.environ.get("HYBA_DEVICE_PCI_IDS", "").strip()
    )


class GPUExecutionUnavailable(RuntimeError):
    """The requested GPU execution path is absent or cannot prove exactness."""


@dataclass(frozen=True)
class ExactScaleResult:
    scale: int
    fibonacci: int
    lucas: int
    padovan: int


def padovan(n: int) -> int:
    if n < 0:
        raise ValueError("scale must be non-negative")
    a, b, c = 1, 1, 1
    for _ in range(3, n + 1):
        a, b, c = b, c, a + b
    return a if n == 0 else (b if n == 1 else c)


def exact_ladder() -> tuple[ExactScaleResult, ...]:
    return tuple(ExactScaleResult(n, fib(n), lucas(n), padovan(n)) for n in LUCAS_PISOT_LADDER)


def _select_device(cl, devices):
    """Prefer the HYBA identity, then a GPU, then another OpenCL device.

    ``HYBA_REQUIRE_HYBA`` fails explicitly when no qualifying device
    enumerates — the ladder never silently executes on a different device.
    When ``HYBA_DEVICE_NAME``/``HYBA_DEVICE_VENDOR``/``HYBA_DEVICE_PCI_IDS``
    are configured, the identity gate replaces the alias check (same
    contract as ``mining/bitcoin_hasher.py::_select_opencl_device``).
    """
    aliases = _hyba_aliases()
    if _require_hyba() and _identity_configured():
        for dev in devices:
            if _device_matches_identity(dev):
                return dev
        names = [f"{getattr(d, 'vendor', '')}: {getattr(d, 'name', '')}" for d in devices]
        raise GPUExecutionUnavailable(
            "HYBA_REQUIRE_HYBA identity gate rejected all OpenCL devices "
            f"(vendor={os.environ.get('HYBA_DEVICE_VENDOR', '')!r}, "
            f"pci_ids={os.environ.get('HYBA_DEVICE_PCI_IDS', '')!r}, "
            f"name={os.environ.get('HYBA_DEVICE_NAME', '')!r}); found: {names}"
        )
    if _require_hyba():
        for dev in devices:
            name = str(getattr(dev, "name", "")).strip().casefold()
            if any(a and a in name for a in aliases):
                return dev
        names = [str(getattr(d, "name", "")).strip() for d in devices]
        raise GPUExecutionUnavailable(
            "HYBA_REQUIRE_HYBA set but no HYBA-alias OpenCL device enumerated "
            f"(aliases={list(aliases)}); found: {names}"
        )
    for dev in devices:
        name = str(getattr(dev, "name", "")).strip().casefold()
        if any(a and a in name for a in aliases):
            return dev
    gpu_devices = [dev for dev in devices if dev.type & cl.device_type.GPU]
    if gpu_devices:
        return gpu_devices[0]
    return devices[0]


class OpenCLLadderExecutor:
    """Execute the declared ladder on a real OpenCL host device."""

    def __init__(self, kernel_path: str | Path | None = None):
        try:
            import pyopencl as cl
        except ImportError as exc:
            raise GPUExecutionUnavailable(
                "pyopencl is not installed; OpenCL ladder execution unavailable"
            ) from exc
        self.cl = cl
        try:
            platforms = cl.get_platforms()
        except cl.LogicError as exc:
            raise GPUExecutionUnavailable(f"OpenCL runtime reported no platforms: {exc}") from exc
        devices = [device for platform in platforms for device in platform.get_devices()]
        if not devices:
            raise GPUExecutionUnavailable("no OpenCL device discovered")
        self.device = _select_device(cl, devices)
        if self.device.type & cl.device_type.GPU:
            self.execution_backend = "opencl:gpu"
        elif self.device.type & int(getattr(cl.device_type, "CPU", 0) or 0):
            self.execution_backend = "opencl:cpu"
        else:
            self.execution_backend = "opencl:accelerator"
        self.context = cl.Context(devices=[self.device])
        self.queue = cl.CommandQueue(self.context)
        source = Path(
            kernel_path or Path(__file__).parents[2] / "kernels/mla1517_lucas_pisot_scale.cl"
        ).read_text()
        self.program = cl.Program(self.context, source).build()

    def _execute_scales(self, scales: tuple[int, ...]) -> tuple[ExactScaleResult, ...]:
        if not scales or any(scale not in LUCAS_PISOT_LADDER for scale in scales):
            raise ValueError("every scale must be one of the declared Lucas-Pisot rungs")
        import numpy as np

        mf = np.dtype([("fib", "<u8"), ("lucas", "<u8"), ("padovan", "<u8")])
        scale_array = np.asarray(scales, dtype=np.uint32)
        out = np.empty(len(scales), dtype=mf)
        mfcl = self.cl.mem_flags
        sb = self.cl.Buffer(self.context, mfcl.READ_ONLY | mfcl.COPY_HOST_PTR, hostbuf=scale_array)
        ob = self.cl.Buffer(self.context, mfcl.WRITE_ONLY, out.nbytes)
        self.program.mla1517_lucas_pisot_scale(
            self.queue, (len(scales),), None, sb, ob, np.uint32(len(scales))
        )
        self.cl.enqueue_copy(self.queue, out, ob).wait()
        result = tuple(
            ExactScaleResult(int(n), int(row["fib"]), int(row["lucas"]), int(row["padovan"]))
            for n, row in zip(scales, out)
        )
        expected = tuple(ExactScaleResult(n, fib(n), lucas(n), padovan(n)) for n in scales)
        if result != expected:
            raise GPUExecutionUnavailable("OpenCL result failed exact Lucas/Pisot invariant check")
        return result

    def execute(self, scales: tuple[int, ...] = LUCAS_PISOT_LADDER) -> tuple[ExactScaleResult, ...]:
        """Execute the complete declared ladder on the real OpenCL device."""
        if tuple(scales) != LUCAS_PISOT_LADDER:
            raise ValueError("the complete declared ladder is required for this operation")
        return self._execute_scales(tuple(scales))

    def execute_rung(self, rung: int) -> ExactScaleResult:
        """Execute one declared rung on the real OpenCL device.

        This is a device dispatch, not a CPU fallback.  The exact integer
        reference is used only as an invariant check after the device returns.
        """
        if rung not in LUCAS_PISOT_LADDER:
            raise ValueError("strict scale violation")
        return self._execute_scales((rung,))[0]
