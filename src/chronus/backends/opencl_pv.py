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
from chronus.backends.lattice_workload import (
    checked_int64 as _checked,
    parse_lattice_workload,
    serialize_lattice,
)
from chronus.config import runtime_bounds
from chronus.core.scaling import planck_ladder

KERNEL_SHA256 = "c285c78ab1e2bc1d54dce4b92fc4cd7c75539b084fc91bee02ed7b425690c346"


def validate_fixed_width(values: list[PhiElement], factor: PhiElement) -> None:
    """Prove every device intermediate fits before any device arithmetic runs."""
    c, d = _checked(factor.a), _checked(factor.b)
    for element in values:
        a, b = _checked(element.a), _checked(element.b)
        ac, bd, ad, bc = (
            _checked(a * c),
            _checked(b * d),
            _checked(a * d),
            _checked(b * c),
        )
        _checked(ac + bd)
        _checked(_checked(ad + bc) + bd)


class OpenCLPVBackend:
    """A GPU-only backend; no CPU OpenCL or reference fallback is implicit."""

    name = "opencl-pv"
    execution_mode = "PHYSICAL_ACCELERATOR"
    supported_workloads = frozenset({"PV_LATTICE_FOLD", "EXACT_PHASE_SEARCH"})

    @property
    def backend_id(self) -> str:
        return self.name

    def __init__(self) -> None:
        try:
            import numpy as np
            import pyopencl as cl
        except ImportError as exc:
            raise HardwareUnavailableError(
                "Install the accelerator extra to use OpenCL"
            ) from exc

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
                pci_address = {
                    "domain": None,
                    "bus": bus,
                    "device": slot >> 3,
                    "function": slot & 7,
                }
            except self._cl.Error as exc:
                raise HardwareUnavailableError(
                    "Failed to query device PCI information"
                ) from exc
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
        if factor.a < 0 or factor.b < 0 or factor.denominator != 1:
            raise ValueError(
                "OpenCL PV factors must have non-negative integer coefficients"
            )
        for value in values:
            _checked(value.a)
            _checked(value.b)
        try:
            factors = [encode_int256(factor.a), encode_int256(factor.b)]
        except OverflowError as exc:
            raise LatticeOverflowError(
                "PV factor exceeds signed 256-bit range"
            ) from exc
        cl, np = self._cl, self._np

        def mapped_write(buffer, data):
            mapped, _ = cl.enqueue_map_buffer(
                self.queue,
                buffer,
                cl.map_flags.WRITE,
                0,
                data.shape,
                data.dtype,
            )
            try:
                mapped[...] = data
            finally:
                mapped.base.release(self.queue).wait()

        def mapped_read(buffer, shape, dtype):
            mapped, _ = cl.enqueue_map_buffer(
                self.queue,
                buffer,
                cl.map_flags.READ,
                0,
                shape,
                dtype,
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
            d_factors = cl.Buffer(
                self.context, flags.READ_ONLY | host_flags, size=factor_data.nbytes
            )
            d_out_a = cl.Buffer(
                self.context, flags.WRITE_ONLY | host_flags, size=len(values) * 32
            )
            d_out_b = cl.Buffer(
                self.context, flags.WRITE_ONLY | host_flags, size=len(values) * 32
            )
            d_status = cl.Buffer(
                self.context, flags.WRITE_ONLY | host_flags, size=len(values) * 4
            )
            mapped_write(d_a, a)
            mapped_write(d_b, b)
            mapped_write(d_factors, factor_data)
            kernel = cl.Kernel(self.program, "pv_lattice_fold")
            kernel(
                self.queue,
                (len(values),),
                None,
                d_a,
                d_b,
                d_factors,
                d_out_a,
                d_out_b,
                d_status,
            )
            status = mapped_read(d_status, (len(values),), np.dtype(np.uint32))
            if np.any(status & np.uint32(4)):
                raise LatticeOverflowError(
                    "OpenCL calculation exceeds signed 256-bit range"
                )
            if np.any((status != 0) & (status != 1) & (status != 3)):
                raise ParityVerificationError("OpenCL returned an invalid status")
            out_a = mapped_read(d_out_a, limb_shape, np.dtype(np.uint64))
            out_b = mapped_read(d_out_b, limb_shape, np.dtype(np.uint64))
        except cl.Error as exc:
            raise HardwareUnavailableError("OpenCL GPU dispatch failed") from exc
        outputs = [
            PhiElement(
                decode_int256(tuple(map(int, out_a[i]))),
                decode_int256(tuple(map(int, out_b[i]))),
                value.denominator,
            )
            for i, value in enumerate(values)
        ]
        return outputs, {
            "executed_64_bit": int(np.count_nonzero(status == 0)),
            "executed_128_bit": int(np.count_nonzero(status == 1)),
            "executed_256_bit": int(np.count_nonzero(status == 3)),
        }

    def dispatch_pv_fold(
        self, values: list[PhiElement], order: int
    ) -> tuple[list[PhiElement], dict[str, Any]]:
        bounds = runtime_bounds()
        max_order = bounds["max_pv_order"]
        if (
            not isinstance(order, int)
            or isinstance(order, bool)
            or not 0 <= order <= max_order
        ):
            raise ValueError(f"order must be an integer between 0 and {max_order}")
        max_elements = bounds["max_lattice_elements"]
        if not 1 <= len(values) <= max_elements:
            raise ValueError(f"values must contain 1 to {max_elements} elements")
        ladder = planck_ladder(len(values)) if len(values) > 1 else [len(values)]
        # Dispatch rung by rung along the Lucas ladder: the accelerator scales
        # by PV powers, each rung verified independently before merging.
        factor = phi_power(order)
        outputs: list[PhiElement] = []
        widths = {"executed_64_bit": 0, "executed_128_bit": 0, "executed_256_bit": 0}
        offset = 0
        for rung in ladder:
            rung_outputs, rung_widths = self._dispatch(values[offset:offset + rung], factor)
            verify_fold(values[offset:offset + rung], rung_outputs, order)
            outputs.extend(rung_outputs)
            for key in widths:
                widths[key] += rung_widths.get(key, 0)
            offset += rung
        verify_fold(values, outputs, order)
        sign = -1 if order % 2 else 1
        if any(
            output.norm() != value.norm() * sign
            for value, output in zip(values, outputs)
        ):
            raise ParityVerificationError("OpenCL norm invariant failed")
        device = self.probe_silicon()
        return outputs, {
            "execution_mode": self.execution_mode,
            "device": device,
            "device_signature": {
                "vendor_id": device["vendor_id"],
                "device_id": device["pci_device_id"],
                "pci_address": device["pci_address"],
                "driver_version": device["driver_version"],
            },
            "verification": "full_exact_host_parity",
            "norm_invariant_verified": True,
            "execution_tier_counts": widths,
            "planck_ladder": ladder,
            "scaling_series": "lucas-pv",
        }

    def dispatch_phase_search(
        self, num_qubits: int, marked_count: int
    ) -> dict[str, Any]:
        """Execute one-shot phase search with 32-lane on-device consensus.

        Every lane recomputes the field iterate independently; the host
        requires unanimous agreement and verifies the result against the
        exact closed form before accepting.
        """
        from chronus.quantum.metallic_search import jform_one_shot_phases
        from chronus.quantum.subspace import uniform_subspace, jform_subspace_iterate

        if not isinstance(num_qubits, int) or isinstance(num_qubits, bool) or num_qubits < 1:
            raise ValueError("num_qubits must be a positive integer")
        n = 1 << num_qubits
        if not isinstance(marked_count, int) or not 1 <= marked_count < n:
            raise ValueError("marked_count must be in [1, 2**num_qubits)")
        alpha, beta = jform_one_shot_phases(num_qubits, marked_count)[0]
        n_mod = pow(2, num_qubits, 257)
        n_mod_inv = pow(n_mod, -1, 257)
        u = pow(30, num_qubits, 257)
        cl, np = self._cl, self._np
        lanes = 32
        try:
            flags = cl.mem_flags
            d_marked = cl.Buffer(self.context, flags.WRITE_ONLY, size=lanes * 4)
            d_unmarked = cl.Buffer(self.context, flags.WRITE_ONLY, size=lanes * 4)
            kernel = cl.Kernel(self.program, "phase_consensus")
            kernel.set_args(
                np.uint32(alpha), np.uint32(beta), np.uint32(u),
                np.uint32(marked_count), np.uint32(n_mod), np.uint32(n_mod_inv),
                d_marked, d_unmarked,
            )
            cl.enqueue_nd_range_kernel(self.queue, kernel, (lanes,), None)
            marked_dev = np.empty(lanes, dtype=np.uint32)
            unmarked_dev = np.empty(lanes, dtype=np.uint32)
            cl.enqueue_copy(self.queue, marked_dev, d_marked)
            cl.enqueue_copy(self.queue, unmarked_dev, d_unmarked)
            self.queue.finish()
        except cl.Error as exc:
            raise HardwareUnavailableError("OpenCL phase consensus dispatch failed") from exc
        if len(set(marked_dev.tolist())) != 1 or len(set(unmarked_dev.tolist())) != 1:
            raise ParityVerificationError("accelerator lanes disagree on phase search")
        expected = jform_subspace_iterate(
            uniform_subspace(num_qubits, marked_count), alpha, beta
        )
        if int(marked_dev[0]) != expected.marked_amplitude \
                or int(unmarked_dev[0]) != expected.unmarked_amplitude:
            raise ParityVerificationError("accelerator phase search mismatches host reference")
        device = self.probe_silicon()
        return {
            "execution_mode": self.execution_mode,
            "surface": "client-accelerator",
            "field": "F_257",
            "iterations": 1,
            "state": {
                "num_qubits": num_qubits,
                "marked_count": marked_count,
                "marked_amplitude": expected.marked_amplitude,
                "unmarked_amplitude": expected.unmarked_amplitude,
                "representation": "rank-2-symbolic",
            },
            "phases": {"alpha": alpha, "beta": beta},
            "lane_consensus": True,
            "lanes_verified": lanes,
            "device": device,
            "device_signature": {
                "vendor_id": device["vendor_id"],
                "device_id": device["pci_device_id"],
                "pci_address": device["pci_address"],
                "driver_version": device["driver_version"],
            },
            "verification": "32_lane_device_consensus_and_host_closed_form",
        }

    def execute(self, payload: bytes, workload_type: str) -> dict[str, Any]:
        if not self.supports(workload_type):
            raise ValueError(f"OpenCL backend does not support {workload_type}")
        if workload_type == "EXACT_PHASE_SEARCH":
            try:
                request = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError("payload must be a UTF-8 JSON object") from exc
            if not isinstance(request, dict):
                raise ValueError("payload must be a JSON object")
            return self.dispatch_phase_search(
                request.get("num_qubits"), request.get("marked_count")
            )
        values, order = parse_lattice_workload(payload)
        outputs, receipt = self.dispatch_pv_fold(values, order)
        return {
            **receipt,
            "values": serialize_lattice(outputs),
        }
