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
from chronus.backends.limbs import encode_int256, decode_int256

KERNEL_SHA256 = "25725484f1ec55b841de4c6d9f428f554a746126a5285163e5f9e8414dc16173"
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
MAX_ELEMENTS = 4096
MAX_DECIMAL_DIGITS = 1024


def _wire_integer(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        if value.bit_length() <= 3402 and len(str(abs(value))) <= MAX_DECIMAL_DIGITS:
            return value
    if isinstance(value, str):
        digits = value[1:] if value.startswith("-") else value
        if 1 <= len(digits) <= MAX_DECIMAL_DIGITS and digits.isascii() and digits.isdecimal():
            return int(value)
    raise ValueError(f"coefficients must be integers or decimal strings of at most {MAX_DECIMAL_DIGITS} digits")


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

    @property
    def backend_id(self) -> str:
        return self.name

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
        outputs, _ = self._dispatch(inputs, factor)
        verify_fold(inputs, outputs, 90)
        lucas, fibonacci = outputs[0].trace(), outputs[0].b
        if (
            lucas != 6440026026380244498
            or fibonacci != 2880067194370816120
            or lucas * lucas - 5 * fibonacci * fibonacci != 4
        ):
            raise ParityVerificationError("OpenCL Lucas known-answer test failed")

    def probe_silicon(self) -> dict[str, Any]:
        pci_address = None
        if "cl_nv_device_attribute_query" in self.device.extensions.split():
            try:
                bus = int(self.device.get_info(self._cl.device_info.PCI_BUS_ID_NV))
                slot = int(self.device.get_info(self._cl.device_info.PCI_SLOT_ID_NV))
                pci_address = {"domain": None, "bus": bus, "device": slot >> 3, "function": slot & 7}
            except self._cl.Error as exc:
                raise HardwareUnavailableError("Failed to query device PCI information") from exc
        return {
            "device_name": self.device.name.strip(),
            "vendor": self.device.vendor.strip(),
            "vendor_id": int(self.device.vendor_id),
            "driver_version": self.device.driver_version.strip(),
            "compute_units": int(self.device.max_compute_units),
            "error_correction_supported": bool(self.device.error_correction_support),
            "unified_memory_reported": bool(self.device.host_unified_memory),
            "pci_address": pci_address,
            "pci_device_id": None,
            "kernel_sha256": KERNEL_SHA256,
            "known_answer_test": "passed",
            "transfer_mode": "opencl-allocated-host-buffer-mapped",
            "zero_copy_verified": False,
        }

    def supports(self, workload_type: str) -> bool:
        return workload_type in self.supported_workloads

    def _dispatch(
        self, values: list[PhiElement], factor: PhiElement
    ) -> tuple[list[PhiElement], dict[str, int]]:
        for value in values:
            _checked(value.a)
            _checked(value.b)
        try:
            factors = [encode_int256(factor.a), encode_int256(factor.b)]
        except OverflowError as exc:
            raise LatticeOverflowError("PV factor exceeds signed 256-bit range") from exc
        cl, np = self._cl, self._np

        def mapped_write(buffer, data):
            mapped, _ = cl.enqueue_map_buffer(
                self.queue, buffer, cl.map_flags.WRITE, 0, data.shape, data.dtype,
            )
            try:
                mapped[...] = data
            finally:
                mapped.base.release(self.queue).wait()

        def mapped_read(buffer, shape, dtype):
            mapped, _ = cl.enqueue_map_buffer(
                self.queue, buffer, cl.map_flags.READ, 0, shape, dtype,
            )
            try:
                return mapped.copy()
            finally:
                mapped.base.release(self.queue).wait()

        a = np.array([element.a for element in values], dtype=np.int64)
        b = np.array([element.b for element in values], dtype=np.int64)
        factor_data = np.array(factors, dtype=np.uint64)
        limb_shape = (len(values), 4)
        try:
            flags = cl.mem_flags
            host_flags = flags.ALLOC_HOST_PTR
            d_a = cl.Buffer(self.context, flags.READ_ONLY | host_flags, size=a.nbytes)
            d_b = cl.Buffer(self.context, flags.READ_ONLY | host_flags, size=b.nbytes)
            d_factors = cl.Buffer(self.context, flags.READ_ONLY | host_flags, size=factor_data.nbytes)
            d_out_a = cl.Buffer(self.context, flags.WRITE_ONLY | host_flags, size=len(values) * 32)
            d_out_b = cl.Buffer(self.context, flags.WRITE_ONLY | host_flags, size=len(values) * 32)
            d_status = cl.Buffer(self.context, flags.WRITE_ONLY | host_flags, size=len(values) * 4)
            mapped_write(d_a, a)
            mapped_write(d_b, b)
            mapped_write(d_factors, factor_data)
            kernel = cl.Kernel(self.program, "pv_lattice_fold")
            kernel(self.queue, (len(values),), None, d_a, d_b, d_factors,
                   d_out_a, d_out_b, d_status)
            status = mapped_read(d_status, (len(values),), np.dtype(np.uint32))
            if np.any(status & np.uint32(~7 & 0xFFFFFFFF)):
                raise ParityVerificationError("OpenCL returned an invalid status")
            if np.any(status & np.uint32(4)):
                raise LatticeOverflowError("OpenCL calculation exceeds signed 256-bit range")
            out_a = mapped_read(d_out_a, limb_shape, np.dtype(np.uint64))
            out_b = mapped_read(d_out_b, limb_shape, np.dtype(np.uint64))
        except cl.Error as exc:
            raise HardwareUnavailableError("OpenCL GPU dispatch failed") from exc
        outputs = [
            PhiElement(
                decode_int256(tuple(map(int, out_a[i]))),
                decode_int256(tuple(map(int, out_b[i]))),
                value.denominator,
            ) for i, value in enumerate(values)
        ]
        return outputs, {
            "fit_int64": int(np.count_nonzero(status == 0)),
            "requires_128_bits": int(np.count_nonzero(status == 1)),
            "requires_256_bits": int(np.count_nonzero(status & np.uint32(2))),
        }

    def dispatch_pv_fold(
        self, values: list[PhiElement], order: int
    ) -> tuple[list[PhiElement], dict[str, Any]]:
        if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 360:
            raise ValueError("order must be an integer between 0 and 360")
        if not 1 <= len(values) <= MAX_ELEMENTS:
            raise ValueError(f"values must contain 1 to {MAX_ELEMENTS} elements")
        outputs, widths = self._dispatch(values, phi_power(order))
        verify_fold(values, outputs, order)
        sign = -1 if order % 2 else 1
        if any(output.norm() != value.norm() * sign for value, output in zip(values, outputs)):
            raise ParityVerificationError("OpenCL norm invariant failed")
        return outputs, {
            "execution_mode": self.execution_mode,
            "device": self.probe_silicon(),
            "verification": "full_exact_host_parity",
            "norm_invariant_verified": True,
            "intermediate_width_counts": widths,
        }

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
        if not isinstance(order, int) or isinstance(order, bool) or not 0 <= order <= 360:
            raise ValueError("order must be an integer between 0 and 360")
        if not isinstance(raw_values, list) or not 1 <= len(raw_values) <= MAX_ELEMENTS:
            raise ValueError(f"values must contain 1 to {MAX_ELEMENTS} elements")
        values = []
        for value in raw_values:
            if not isinstance(value, dict) or set(value) != {"a", "b", "denominator"}:
                raise ValueError("each value must contain a, b and denominator")
            values.append(PhiElement(
                _wire_integer(value["a"]), _wire_integer(value["b"]),
                _wire_integer(value["denominator"]),
            ))
        outputs, receipt = self.dispatch_pv_fold(values, order)
        return {
            **receipt,
            "values": [
                {"a": str(value.a), "b": str(value.b), "denominator": str(value.denominator)}
                for value in outputs
            ],
        }
