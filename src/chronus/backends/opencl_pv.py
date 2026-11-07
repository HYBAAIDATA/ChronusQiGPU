"""Opt-in OpenCL GPU adapter with exact host-side bounds and full parity checks."""

import hashlib
import json
from importlib.resources import files
from typing import Any

from chronus.backends.lattice import (
    HardwareUnavailableError,
    LatticeOverflowError,
    ParityVerificationError,
    PhiElement,
    phi_power,
    verify_fold,
)

KERNEL_SHA256 = "02e59826ed062ca9f790f263a7174a3d1eddf220706c62a57520e4fadd6c09c5"
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
MAX_ELEMENTS = 4096


def _checked(value: int) -> int:
    if not INT64_MIN <= value <= INT64_MAX:
        raise LatticeOverflowError("OpenCL fixed-width operation would overflow int64")
    return value


def validate_fixed_width(values: list[PhiElement], factor: PhiElement) -> None:
    """Prove every device intermediate fits before any device arithmetic runs."""
    c, d = _checked(factor.a), _checked(factor.b)
    for element in values:
        a, b = _checked(element.a), _checked(element.b)
        ac, bd, ad, bc = (_checked(a * c), _checked(b * d), _checked(a * d), _checked(b * c))
        _checked(ac + bd)
        _checked(_checked(ad + bc) + bd)


class OpenCLPVBackend:
    """A GPU-only backend; no CPU OpenCL or reference fallback is implicit."""

    name = "opencl-pv"
    execution_mode = "PHYSICAL_ACCELERATOR"
    supported_workloads = frozenset({"PV_LATTICE_FOLD"})

    def __init__(self) -> None:
        try:
            import numpy as np
            import pyopencl as cl
        except ImportError as exc:
            raise HardwareUnavailableError("Install the accelerator extra to use OpenCL") from exc

        self._np = np
        self._cl = cl
        source = files("chronus.kernels").joinpath("pv_lattice.cl").read_bytes()
        if hashlib.sha256(source).hexdigest() != KERNEL_SHA256:
            raise HardwareUnavailableError("Packaged OpenCL kernel digest mismatch")
        try:
            platforms = cl.get_platforms()
            devices = [
                device
                for platform in platforms
                for device in platform.get_devices()
                if device.type & cl.device_type.GPU
            ]
            if not devices:
                raise HardwareUnavailableError("No OpenCL GPU device is available")
            self.device = devices[0]
            self.context = cl.Context([self.device])
            self.queue = cl.CommandQueue(self.context)
            self.program = cl.Program(self.context, source.decode("utf-8")).build()
        except cl.Error as exc:
            raise HardwareUnavailableError("OpenCL GPU initialization failed") from exc

        inputs = [PhiElement(1, 0)]
        factor = phi_power(90)
        outputs = self._dispatch(inputs, factor)
        verify_fold(inputs, outputs, 90)
        if outputs[0].trace() != 6440026026380244498:
            raise ParityVerificationError("OpenCL Lucas known-answer test failed")

    def probe_silicon(self) -> dict[str, Any]:
        return {
            "device_name": self.device.name.strip(),
            "vendor": self.device.vendor.strip(),
            "vendor_id": int(self.device.vendor_id),
            "driver_version": self.device.driver_version.strip(),
            "compute_units": int(self.device.max_compute_units),
            "error_correction_supported": bool(self.device.error_correction_support),
            "unified_memory_reported": bool(self.device.host_unified_memory),
            "kernel_sha256": KERNEL_SHA256,
            "known_answer_test": "passed",
            "transfer_mode": "opencl-buffer-copy",
        }

    def supports(self, workload_type: str) -> bool:
        return workload_type in self.supported_workloads

    def _dispatch(self, values: list[PhiElement], factor: PhiElement) -> list[PhiElement]:
        validate_fixed_width(values, factor)
        cl, np = self._cl, self._np
        a = np.array([element.a for element in values], dtype=np.int64)
        b = np.array([element.b for element in values], dtype=np.int64)
        out_a = np.empty_like(a)
        out_b = np.empty_like(b)
        flags = cl.mem_flags
        try:
            d_a = cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=a)
            d_b = cl.Buffer(self.context, flags.READ_ONLY | flags.COPY_HOST_PTR, hostbuf=b)
            d_out_a = cl.Buffer(self.context, flags.WRITE_ONLY, size=out_a.nbytes)
            d_out_b = cl.Buffer(self.context, flags.WRITE_ONLY, size=out_b.nbytes)
            self.program.pv_lattice_fold(
                self.queue, (len(values),), None, d_a, d_b,
                np.int64(factor.a), np.int64(factor.b), d_out_a, d_out_b,
            )
            cl.enqueue_copy(self.queue, out_a, d_out_a)
            cl.enqueue_copy(self.queue, out_b, d_out_b)
            self.queue.finish()
        except cl.Error as exc:
            raise HardwareUnavailableError("OpenCL GPU dispatch failed") from exc
        return [
            PhiElement(int(out_a[i]), int(out_b[i]), value.denominator)
            for i, value in enumerate(values)
        ]

    def execute(self, payload: bytes, workload_type: str) -> dict[str, Any]:
        if not self.supports(workload_type):
            raise ValueError(f"OpenCL backend does not support {workload_type}")
        if len(payload) > 1024 * 1024:
            raise ValueError("payload exceeds 1 MiB")
        try:
            request = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("payload must be a UTF-8 JSON object") from exc
        if not isinstance(request, dict):
            raise ValueError("payload must be a JSON object")
        order, raw_values = request.get("order"), request.get("values")
        if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 90:
            raise ValueError("order must be an integer between 0 and 90")
        if not isinstance(raw_values, list) or not 1 <= len(raw_values) <= MAX_ELEMENTS:
            raise ValueError(f"values must contain 1 to {MAX_ELEMENTS} elements")
        values = []
        for value in raw_values:
            if not isinstance(value, dict) or set(value) != {"a", "b", "denominator"}:
                raise ValueError("each value must contain a, b and denominator")
            try:
                values.append(PhiElement(value["a"], value["b"], value["denominator"]))
            except TypeError as exc:
                raise ValueError(str(exc)) from exc
        factor = phi_power(order)
        outputs = self._dispatch(values, factor)
        verify_fold(values, outputs, order)
        return {
            "execution_mode": self.execution_mode,
            "device": self.probe_silicon(),
            "verification": "full_exact_host_parity",
            "values": [
                {"a": value.a, "b": value.b, "denominator": value.denominator}
                for value in outputs
            ],
        }
