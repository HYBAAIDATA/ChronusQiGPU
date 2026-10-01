"""IRExecutor — bind a KernelSpec to a capability-matched device and run it.

Binding rules:
- the device's measured capability map must cover the spec's
  ``required_capabilities``; anything else raises ``CapabilityMismatch`` —
  no silent fallback onto a device that never attested the capability;
- backend ``cpu`` binds the spec's oracle emitter (the definition of
  correctness for that op);
- backend ``opencl`` binds the real in-tree host for the spec's executor
  key (UnifiedPunchHost / BitcoinHasher / OpenCLLadderExecutor /
  ExactOpenCLAccelerator), pinned to the named device;
- backend ``asic`` binds only ``sha256d_scan`` through the MMIO bridge;
- ``run`` times the dispatch, returns an :class:`OpResult` carrying the
  full provenance, and — for mining ops — re-verifies any declared winner
  with hashlib before reporting it. The hash is the sole accept authority.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import numpy as np

from hyba.inventory import DeviceInfo
from hyba.math_ir.emit_cpu import emit_cpu
from hyba.math_ir.specs import KernelSpec, get_spec


class CapabilityMismatch(RuntimeError):
    """The device does not attest every capability the spec requires."""


@dataclass
class OpResult:
    """One executed op with its full measured provenance."""

    spec_name: str
    backend: str
    device_name: str
    capability_used: Optional[str]
    lucas_dispatch: Dict[str, Any]
    measured_ns: int
    clock_source: str
    truth_class: str  # "measured" | "cpu_reference" | "unconfigured"
    outputs: Dict[str, Any] = field(default_factory=dict)
    oracle_checked: bool = False

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "spec": self.spec_name,
            "backend": self.backend,
            "device_name": self.device_name,
            "measured_ns": self.measured_ns,
            "clock_source": self.clock_source,
            "truth_class": self.truth_class,
            "oracle_checked": self.oracle_checked,
        }
        if self.capability_used:
            out["capability_used"] = self.capability_used
        if self.lucas_dispatch:
            out["lucas_dispatch"] = dict(self.lucas_dispatch)
        out["outputs"] = {
            k: (v.tolist() if isinstance(v, np.ndarray) else v)
            for k, v in self.outputs.items()
        }
        return out


def _sha256d_verify(header80: bytes, nonce: int, target_int: int) -> bool:
    """hashlib is the sole accept authority for every mining result."""
    import hashlib

    blob = bytearray(header80)
    struct.pack_into("<I", blob, 76, nonce & 0xFFFFFFFF)
    digest = hashlib.sha256(hashlib.sha256(bytes(blob)).digest()).digest()
    return int.from_bytes(digest, "little") <= target_int


class IRExecutor:
    """Bind ``spec`` to ``device``; ``compile()`` resolves the callable."""

    def __init__(self, device: DeviceInfo, spec: KernelSpec | str) -> None:
        self.device = device
        self.spec = get_spec(spec) if isinstance(spec, str) else spec
        self._runner: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None
        self._host: Any = None
        self._truth_class = "unconfigured"

    # -- capability gate ---------------------------------------------------

    def _check_capabilities(self) -> None:
        if self.device.backend == "cpu":
            return  # the CPU oracle is always its own definition
        missing = [
            cap
            for cap in self.spec.required_capabilities
            if self.device.capability(cap) in (None, False, 0)
        ]
        if missing:
            raise CapabilityMismatch(
                f"{self.device.name} ({self.device.backend}) lacks measured "
                f"capabilities {missing} required by {self.spec.name}"
            )

    # -- compile ------------------------------------------------------------

    def compile(self) -> "IRExecutor":
        """Resolve the real backend callable for this device + spec."""
        self._check_capabilities()
        backend = self.device.backend
        if backend == "cpu":
            self._runner = emit_cpu(self.spec.name)
            self._truth_class = "cpu_reference"
        elif backend == "opencl":
            self._bind_opencl()
        elif backend == "asic":
            self._bind_asic()
        else:
            raise CapabilityMismatch(
                f"backend {backend!r} is not a runnable executor target"
            )
        return self

    def _bind_opencl(self) -> None:
        """Bind the real host for this spec's executor key."""
        name = self.device.name
        if self.spec.executor == "unified_punch_host":
            from Intelligence.unified_punch import UnifiedPunchHost

            host = UnifiedPunchHost(device=name)
            if not host.use_opencl:
                raise CapabilityMismatch(
                    f"unified_punch on {name}: OpenCL execution unavailable "
                    f"({host.fallback_reason or 'backend resolved to cpu'})"
                )
            self._host = host
            self._runner = self._run_punch_opencl
        elif self.spec.executor == "bitcoin_hasher":
            from mining.bitcoin_hasher import BitcoinHasher

            hasher = BitcoinHasher(device=name)
            if not hasher.backend.startswith("opencl:"):
                raise CapabilityMismatch(
                    f"sha256d on {name}: OpenCL unavailable "
                    f"({hasher.fallback_reason or 'unknown'})"
                )
            self._host = hasher
            self._runner = self._run_hasher_opencl
        elif self.spec.executor == "ladder_executor":
            from chronus.mla1517.scaling import OpenCLLadderExecutor

            self._host = OpenCLLadderExecutor()
            self._runner = self._run_ladder_opencl
        elif self.spec.executor == "exact_accelerator":
            from chronus.mla1517.accelerator import ExactOpenCLAccelerator

            self._host = ExactOpenCLAccelerator()
            self._runner = self._run_accelerator_opencl
        else:
            raise CapabilityMismatch(
                f"spec {self.spec.name} has no opencl executor binding"
            )
        self._truth_class = "measured"

    def _bind_asic(self) -> None:
        if self.spec.name != "sha256d_scan":
            raise CapabilityMismatch(
                f"spec {self.spec.name} has no ASIC executor binding"
            )
        self._runner = self._run_asic
        self._truth_class = "measured"

    # -- OpenCL adapters -----------------------------------------------------

    def _run_punch_opencl(
        self, inputs: Dict[str, Any], dispatch: Dict[str, Any]
    ) -> Dict[str, Any]:
        ids = np.asarray(inputs["punch_ids"], dtype=np.uint8)
        total = len(ids)
        n_per_punch = int(inputs.get("n", total))
        in_float = np.asarray(inputs.get("in_float", np.zeros(total * 11)), dtype=np.float32)
        in_ulong = np.asarray(inputs.get("in_ulong", np.zeros(total * 121)), dtype=np.uint64)
        in_int = np.asarray(inputs.get("in_int", np.zeros(total)), dtype=np.int32)
        in_double = np.asarray(inputs.get("in_double", np.zeros(total)), dtype=np.float64)
        return self._host.dispatch(
            ids,
            in_float,
            in_ulong,
            in_int,
            in_double,
            np.zeros(total * 11, dtype=np.float32),
            np.zeros(total * 121, dtype=np.uint64),
            np.zeros(total, dtype=np.int32),
            np.zeros(total, dtype=np.int64),
            np.zeros(total * 11, dtype=np.float64),
            total,
            n_per_punch,
        )

    def _run_hasher_opencl(
        self, inputs: Dict[str, Any], dispatch: Dict[str, Any]
    ) -> Dict[str, Any]:
        header80 = bytes(inputs["header"])
        target_be = inputs["target_be"]
        if len(header80) != 80 or len(target_be) != 32:
            raise ValueError("hasher inputs require 80B header + 32B big-endian target")
        if self.spec.name == "sha256d_m32":
            winner, digest, hashes = self._host.grind_target_m32(
                header80,
                target_be,
                int(inputs.get("base_nonce", 0)),
                inputs.get("lane_order"),
                int(inputs.get("count", dispatch.get("work_items", 32))),
            )
        elif self.spec.name == "sha256d_gold":
            winner, digest, hashes, fifo_hits = self._host.grind_target_gold(
                header80,
                target_be,
                int(inputs.get("count", dispatch.get("work_items", 1024))),
                seed=inputs.get("seed"),
            )
            return {
                "winning_nonce": winner,
                "winning_digest": digest,
                "hashes": hashes,
                "hit_nonces": fifo_hits,
            }
        else:
            winner, digest, hashes = self._host.grind_target_range(
                header80,
                target_be,
                int(inputs.get("base_nonce", 0)),
                int(inputs.get("count", dispatch.get("work_items", 1024))),
            )
        return {"winning_nonce": winner, "winning_digest": digest, "hashes": hashes}

    def _run_ladder_opencl(
        self, inputs: Dict[str, Any], dispatch: Dict[str, Any]
    ) -> Dict[str, Any]:
        rung = int(inputs["scale_index"])
        result = self._host.execute_rung(rung)
        return {
            "scale_index": rung,
            "fib": result.fib,
            "lucas": result.lucas,
            "padovan": result.padovan,
        }

    def _run_accelerator_opencl(
        self, inputs: Dict[str, Any], dispatch: Dict[str, Any]
    ) -> Dict[str, Any]:
        state_buffer = inputs["state_buffer"]  # pyopencl.Buffer owned by caller
        rung = int(inputs["rung"])
        qubit = int(inputs.get("qubit", 0))
        pow2 = self._host.apply_hadamard_ladder(
            state_buffer, target=qubit, rung=rung
        )
        return {"denominator_pow2": pow2, "rung": rung}

    def _run_asic(
        self, inputs: Dict[str, Any], dispatch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Drive the real MMIO contract: mask + base step + start/poll/stop.

        The bridge speaks the MLA1517 control API — difficulty mask and
        base step in, vault records out. A vault record is reported
        verbatim; ``winning_nonce`` is populated only when the caller
        supplies ``nonce_extractor`` — no field is invented.
        """
        import os

        from chronus.mla1517.hardware import MMIOBridge

        device_path = inputs.get("device_path") or os.environ.get(
            "MLA1517_MMIO_DEVICE"
        )
        if not device_path:
            raise CapabilityMismatch(
                "asic dispatch requires inputs['device_path'] or "
                "MLA1517_MMIO_DEVICE"
            )
        timeout_ms = int(inputs.get("timeout_ms", 100))
        extractor = inputs.get("nonce_extractor")
        with MMIOBridge(device_path) as bridge:
            bridge.set_difficulty_mask(int(inputs.get("difficulty_mask", 0)))
            bridge.set_base_step(int(inputs.get("base_nonce", 0)))
            bridge.start()
            try:
                record = bridge.poll_vault(timeout_ms)
            finally:
                bridge.stop()
        out: Dict[str, Any] = {"vault_record": None, "winning_nonce": None}
        if record is not None:
            out["vault_record"] = {
                "node_id": record.node_id,
                "sequence": record.sequence,
                "state": record.state.hex(),
            }
            if extractor is not None:
                out["winning_nonce"] = int(extractor(record)) & 0xFFFFFFFF
        return out

    # -- run ------------------------------------------------------------------

    def run(
        self,
        inputs: Dict[str, Any],
        dispatch_config: Optional[Dict[str, Any]] = None,
    ) -> OpResult:
        if self._runner is None:
            raise RuntimeError("IRExecutor.run before compile()")
        dispatch = dict(dispatch_config or {})
        started = time.perf_counter_ns()
        outputs = self._runner(inputs, dispatch)
        measured_ns = time.perf_counter_ns() - started

        oracle_checked = False
        winner = outputs.get("winning_nonce")
        if (
            self.spec.name in ("sha256d_scan", "sha256d_m32", "sha256d_gold")
            and winner is not None
        ):
            if "target_be" in inputs:
                target_int = int.from_bytes(inputs["target_be"], "big")
            else:
                target_int = int(inputs["target"])
            header80 = bytes(inputs["header"])
            if len(header80) == 76:
                header80 = header80 + b"\x00" * 4
            if not _sha256d_verify(header80, int(winner), target_int):
                raise RuntimeError(
                    f"{self.spec.name}: device declared nonce {winner} but "
                    "hashlib recheck rejects it — result refused"
                )
            oracle_checked = True

        cap = dispatch.get("capability_used") or (
            self.spec.required_capabilities[0]
            if self.spec.required_capabilities
            else None
        )
        return OpResult(
            spec_name=self.spec.name,
            backend=self.device.backend,
            device_name=self.device.name,
            capability_used=cap,
            lucas_dispatch=dispatch.get("lucas_dispatch", {}),
            measured_ns=measured_ns,
            clock_source="perf_counter",
            truth_class=self._truth_class,
            outputs=outputs,
            oracle_checked=oracle_checked,
        )


__all__ = ["CapabilityMismatch", "IRExecutor", "OpResult"]
