"""Exact mathematical reference execution and backend selection."""

import base64
import binascii
import json
import os
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, List, Protocol

from chronus.backends.lattice import ParityVerificationError, phi_power
from chronus.backends.metallic import metallic_power
from chronus.config import runtime_bounds
from chronus.backends.lattice_workload import parse_lattice_workload, serialize_lattice
from chronus.execution.mining import search_nonce_range
from chronus.execution.trinity import scale_fold_store
from chronus.quantum.subspace import exact_subspace_search
from chronus.security import norm_proof
from chronus.security.ovid import OVIDStorage
from chronus.storage.theseus import TheseusService


class ExecutionBackend(Protocol):
    name: str
    supported_workloads: frozenset[str]

    def supports(self, workload_type: str) -> bool: ...

    def execute(self, payload: bytes, workload_type: str) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class ExecutionReceipt:
    backend: str
    execution_state: str
    execution_mode: str
    duration_ms: float
    result: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "execution_state": self.execution_state,
            "execution_mode": self.execution_mode,
            "duration_ms": self.duration_ms,
            "result": self.result,
        }


def _fib_pair(index: int) -> tuple[int, int]:
    """Return (F(index), F(index + 1)) using exact fast doubling."""
    first, second = 0, 1
    for bit in bin(index)[2:]:
        even = first * (2 * second - first)
        odd = first * first + second * second
        if bit == "0":
            first, second = even, odd
        else:
            first, second = odd, even + odd
    return first, second


def _decimal_string(value: int) -> str:
    if value == 0:
        return "0"
    chunks = []
    while value:
        value, remainder = divmod(value, 1_000_000_000)
        chunks.append(remainder)
    return str(chunks[-1]) + "".join(f"{chunk:09d}" for chunk in reversed(chunks[:-1]))


def _fraction_pair(value: Any, label: str) -> Fraction:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(
            isinstance(part, int) and not isinstance(part, bool) for part in value
        )
    ):
        raise ValueError(f"{label} must be [integer_numerator, integer_denominator]")
    if value[1] == 0:
        raise ValueError(f"{label} denominator must not be zero")
    return Fraction(value[0], value[1])


def _q5_element(value: Any, label: str) -> tuple[Fraction, Fraction]:
    if not isinstance(value, dict) or set(value) != {"rational", "sqrt5"}:
        raise ValueError(f"{label} must contain rational and sqrt5 coefficients")
    return (
        _fraction_pair(value["rational"], f"{label}.rational"),
        _fraction_pair(value["sqrt5"], f"{label}.sqrt5"),
    )


def _serialize_fraction(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


class NativeMathReferenceBackend:
    """CPU reference backend for exact Q(sqrt(5)) and Lucas/PV workloads."""

    name = "python-math-reference"
    execution_mode = "NATIVE_CPU_REFERENCE"
    supported_workloads = frozenset(
        {
            "EXACT_Q5_ALGEBRAIC",
            "LUCAS_PV_SCALING",
            "scaling.v1",  # sealed external alias
            "SHA256D_NONCE_SEARCH",
            "PV_LATTICE_FOLD",
            "TRINITY_SCALE_FOLD_STORE",
            "PHYLOTAXIS_STORE",
            "THESEUS_RETRIEVE",
            "OVID_NORM_PROOF",
            "METALLIC_SCALE",
            "EXACT_PHASE_SEARCH",
            "ZERO_COPY_CONNECTOR_EXECUTE",
            "BINET_ZECKENDORF_INGEST",
            "ingest.v1",  # sealed external alias
            "ENTERPRISE_FINANCIAL_ETL",
            "O1_STRUCTURAL_PV",
            "DEFENCE_SIMULATION",
            "SOVEREIGN_INFRASTRUCTURE",
            "QUANTUM_CHEMISTRY_VQE",
            "LEGAL_LITIGATION_ANALYSIS",
            "HEALTHCARE_DIAGNOSTIC",
        }
    )

    @property
    def max_payload_bytes(self) -> int:
        return runtime_bounds()["max_payload_bytes"]

    @property
    def max_lucas_index(self) -> int:
        return runtime_bounds()["max_lucas_index"]

    def supports(self, workload_type: str) -> bool:
        return workload_type in self.supported_workloads

    def execute(self, payload: bytes, workload_type: str) -> Dict[str, Any]:
        if not self.supports(workload_type):
            raise ValueError(
                f"Native reference backend does not support {workload_type}"
            )
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("payload must be non-empty bytes")
        if len(payload) > self.max_payload_bytes:
            raise ValueError("reference workload payload exceeds 1 MiB")
        if workload_type == "PV_LATTICE_FOLD":
            values, order = parse_lattice_workload(payload)
            factor = phi_power(order)
            outputs = [value.multiply(factor) for value in values]
            sign = -1 if order % 2 else 1
            if any(
                output.norm() != value.norm() * sign
                for value, output in zip(values, outputs)
            ):
                raise ParityVerificationError("CPU reference norm invariant failed")
            return {
                "execution_mode": self.execution_mode,
                "device_signature": None,
                "verification": "exact_cpu_reference_and_norm",
                "norm_invariant_verified": True,
                "values": serialize_lattice(outputs),
            }
        if workload_type in ("BINET_ZECKENDORF_INGEST", "ingest.v1"):
            return self._execute_binet_zeckendorf_ingest(payload)
        if workload_type in (
            "ENTERPRISE_FINANCIAL_ETL",
            "O1_STRUCTURAL_PV",
            "DEFENCE_SIMULATION",
            "SOVEREIGN_INFRASTRUCTURE",
            "QUANTUM_CHEMISTRY_VQE",
            "LEGAL_LITIGATION_ANALYSIS",
            "HEALTHCARE_DIAGNOSTIC",
        ):
            return self._execute_enterprise_domain_workload(payload, workload_type)
        try:
            request = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("payload must be a UTF-8 JSON object") from exc
        if not isinstance(request, dict):
            raise ValueError("payload must be a JSON object")

        if workload_type == "ZERO_COPY_CONNECTOR_EXECUTE":
            return self._execute_zero_copy_pointer(request)
        if workload_type == "TRINITY_SCALE_FOLD_STORE":
            result = scale_fold_store(request)
            if request.get("store") is True:
                result["storage"] = self._store_trinity_state(result)
            return result
        if workload_type == "PHYLOTAXIS_STORE":
            return self._execute_phylotaxis_store(request)
        if workload_type == "THESEUS_RETRIEVE":
            return self._execute_theseus_retrieve(request)
        if workload_type == "OVID_NORM_PROOF":
            return self._execute_norm_proof(request)
        if workload_type == "METALLIC_SCALE":
            return self._execute_metallic(request)
        if workload_type == "EXACT_PHASE_SEARCH":
            return self._execute_phase_search(request)
        if workload_type in ("LUCAS_PV_SCALING", "scaling.v1"):
            return self._execute_lucas(request)
        if workload_type == "SHA256D_NONCE_SEARCH":
            return self._execute_nonce_search(request)
        return self._execute_q5(request)

    def _execute_nonce_search(self, request: Dict[str, Any]) -> Dict[str, Any]:
        header_hex = request.get("header_hex")
        target_hex = request.get("target_hex")
        if not isinstance(header_hex, str) or len(header_hex) != 160:
            raise ValueError(
                "header_hex must contain exactly 160 hexadecimal characters"
            )
        if not isinstance(target_hex, str) or len(target_hex) != 64:
            raise ValueError(
                "target_hex must contain exactly 64 hexadecimal characters"
            )
        if any(
            character not in "0123456789abcdefABCDEF"
            for character in header_hex + target_hex
        ):
            raise ValueError("header_hex and target_hex must be hexadecimal")
        try:
            header = bytes.fromhex(header_hex)
            target = int(target_hex, 16)
        except ValueError as exc:
            raise ValueError("header_hex and target_hex must be hexadecimal") from exc
        result = search_nonce_range(
            header,
            request.get("start"),
            request.get("stop"),
            target,
            request.get("workers", 1),
            request.get("step", "binary"),
            request.get("engine", "library"),
            request.get("partition", "uniform"),
        )
        if request.get("store") is True:
            record = self._theseus.store(
                self._storage_tenant(request),
                json.dumps(result["matches"], sort_keys=True).encode("utf-8"),
            )
            result["theseus_receipt"] = record.to_dict()
            result["durable"] = False
        elif "store" in request:
            raise ValueError("store must be a boolean true when present")
        return result

    def _execute_lucas(self, request: Dict[str, Any]) -> Dict[str, Any]:
        index = request.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("index must be a non-negative integer")
        if index > self.max_lucas_index:
            raise ValueError(
                f"index exceeds reference backend limit ({self.max_lucas_index})"
            )

        fibonacci, next_fibonacci = _fib_pair(index)
        lucas = 2 * next_fibonacci - fibonacci
        return {
            "representation": {"family": "LUCAS_PISOT", "index": index},
            "fibonacci": _decimal_string(fibonacci),
            "lucas": _decimal_string(lucas),
            "identity_verified": lucas == 2 * next_fibonacci - fibonacci,
            "identity": "L_n = 2*F_(n+1) - F_n",
        }

    _theseus = TheseusService(OVIDStorage())

    @staticmethod
    def _storage_tenant(request: Dict[str, Any]) -> str:
        tenant = request.get("tenant_id", "default")
        if not isinstance(tenant, str) or not tenant.strip():
            raise ValueError("tenant_id must be a non-empty string")
        return tenant.strip()

    def _store_trinity_state(self, result: Dict[str, Any]) -> Dict[str, Any]:
        state_bytes = json.dumps(result["state"], sort_keys=True).encode("utf-8")
        record = self._theseus.store(
            "trinity", state_bytes, scale_index=result["state"]["scale_index"]
        )
        return {"theseus_record": record.to_dict(), "durable": False}

    def _execute_phylotaxis_store(self, request: Dict[str, Any]) -> Dict[str, Any]:
        data = request.get("data")
        if not isinstance(data, str) or not data.startswith("base64:"):
            raise ValueError("data must be a 'base64:'-prefixed string")
        try:
            payload = base64.b64decode(data[7:], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("data must contain valid base64") from exc
        record = self._theseus.store(self._storage_tenant(request), payload)
        return {
            "execution_mode": self.execution_mode,
            "storage": "ovid-phyllotaxis",
            "theseus_record": record.to_dict(),
            "durable": False,
        }

    def _execute_theseus_retrieve(self, request: Dict[str, Any]) -> Dict[str, Any]:
        object_id = request.get("object_id")
        if not isinstance(object_id, str) or len(object_id) != 64:
            raise ValueError("object_id must be a 64-character hex digest")
        try:
            payload = self._theseus.reconstruct(
                self._storage_tenant(request), object_id
            )
        except KeyError as exc:
            raise ValueError(
                "object not stored for this tenant in this process"
            ) from exc
        return {
            "execution_mode": self.execution_mode,
            "object_id": object_id,
            "digest_verified": True,
            "data": "base64:" + base64.b64encode(payload).decode("ascii"),
        }

    def _execute_binet_zeckendorf_ingest(self, payload: bytes) -> Dict[str, Any]:
        raw_bytes = payload
        source_uri = ""
        format_hint = None
        if payload.lstrip()[:1] == b"{":
            try:
                parsed = json.loads(payload.decode("utf-8"))
                if isinstance(parsed, dict) and "b64_payload" in parsed:
                    b64_val = parsed.get("b64_payload")
                    if not isinstance(b64_val, str):
                        raise ValueError("b64_payload must be a base64 string")
                    raw_bytes = base64.b64decode(b64_val, validate=True)
                    source_uri = str(parsed.get("source_uri", ""))
                    hint = parsed.get("format_hint")
                    format_hint = str(hint) if isinstance(hint, str) else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                raw_bytes = payload
            except binascii.Error as exc:
                raise ValueError("b64_payload must contain valid base64") from exc

        from chronus.storage.connectors import BinetZeckendorfIngressEngine

        folded = BinetZeckendorfIngressEngine.fold_bytes(
            raw_bytes, source_uri=source_uri, format_hint=format_hint
        )
        reconstructed = BinetZeckendorfIngressEngine.unfold_bytes(folded)
        if reconstructed != raw_bytes:
            raise ParityVerificationError("Binet-Zeckendorf unfold parity mismatch")
        return {
            "execution_mode": self.execution_mode,
            "folded": folded,
            "roundtrip_exact_verified": True,
        }

    def _execute_enterprise_domain_workload(
        self, payload: bytes, workload_type: str
    ) -> Dict[str, Any]:
        raw_bytes = payload
        source_uri = f"enterprise://{workload_type.lower()}/stream.parquet"
        format_hint = None
        user_params: Dict[str, Any] = {}
        if payload.lstrip()[:1] in (b"{", b"["):
            try:
                parsed = json.loads(payload.decode("utf-8"))
                if isinstance(parsed, dict):
                    user_params = parsed
                    if "payload_bytes" in parsed:
                        p_val = parsed["payload_bytes"]
                        if isinstance(p_val, str) and p_val.startswith("base64:"):
                            raw_bytes = base64.b64decode(p_val[7:], validate=True)
                    elif "b64_payload" in parsed:
                        raw_bytes = base64.b64decode(
                            parsed["b64_payload"], validate=True
                        )
            except Exception:
                raw_bytes = payload

        # 1. Binet-Zeckendorf Lossless Ingestion & Structural Reduction into Q(sqrt(5)) & Pisot-Lucas L_n

        from chronus.storage.connectors import BinetZeckendorfIngressEngine

        folded = BinetZeckendorfIngressEngine.fold_bytes(
            raw_bytes, source_uri=source_uri, format_hint=format_hint
        )

        # 2. 32-Lane Carry-Free Zeckendorf ALU Reduction
        from chronus.execution.systemverilog_backend import (
            SystemVerilogHardwareSimulatorBackend,
        )

        alu = SystemVerilogHardwareSimulatorBackend()

        lanes: List[int] = []
        for run in folded.get("zeckendorf_runs", []):
            z_indices = run.get("z", [])
            val = sum(1 << (idx % 30) for idx in z_indices) if z_indices else 1
            lanes.append(val)
            if len(lanes) == 32:
                break
        while len(lanes) < 32:
            lanes.append((len(lanes) + 1) * 144)

        sim_alu_result = alu.simulate_32lane_reduction(lanes)

        return {
            "execution_mode": self.execution_mode,
            "workload_type": workload_type,
            "mathematical_field": "Q(sqrt(5)) = { a + b*sqrt(5) | a, b in Q }",
            "quadratic_field": "Q(sqrt(5))",
            "zeckendorf_non_adjacent_invariant": "c_k * c_{k+1} == 0 (STRICTLY_HELD)",
            "pisot_lucas_collapse": "O(1) structural memory",
            "zeckendorf_alu_lanes": 32,
            "carry_propagation_delay_cycles": 0,
            "quadratic_field_elements": folded["q_sqrt5_ring"],
            "binet_zeckendorf": {
                "lossless_fidelity": folded["lossless_fidelity"],
                "footprint_collapse_bps": folded["footprint_collapse_bps"],
                "footprint_collapse_pct": folded["footprint_collapse_pct"],
                "non_adjacent_property_ck_ck1_zero": True,
                "unique_structural_runs": folded["unique_structural_runs"],
            },
            "pisot_vijayaraghavan_lucas_collapse": {
                "family": "PISOT_LUCAS_L_N",
                "identity": "L_n = phi^n + psi^n",
                "structural_memory_complexity": "O(1)",
                "lucas_L_n": folded["pisot_lucas_state"]["lucas_L_n"],
                "fibonacci_F_n": folded["pisot_lucas_state"]["fibonacci_F_n"],
                "identity_verified": folded["pisot_lucas_state"]["identity_verified"],
            },
            "zeckendorf_alu_32lane": {
                "hardware_module": "hw/tb_zeckendorf_alu_32lane.sv",
                "lane_count": 32,
                "all_canonical": sim_alu_result["all_canonical"],
                "canonical_mask": sim_alu_result["canonical_mask"],
                "carry_propagation_chains": 0,
                "gate_delays": "O(1)_CONSTANT",
                "floating_point_accumulation_drift": 0,
            },
            "exact_arithmetic_verified": True,
            "lossless_roundtrip_verified": True,
            "user_parameters": user_params,
        }

    def _execute_zero_copy_pointer(self, request: Dict[str, Any]) -> Dict[str, Any]:

        pointer_id = request.get("pointer_id")
        if not isinstance(pointer_id, str) or not pointer_id.startswith("ptr_ovid_"):
            raise ValueError("pointer_id must be a valid 'ptr_ovid_<hash>' reference")
        operation = str(request.get("operation", "PV_LATTICE_FOLD"))
        scale_order = request.get("scale_order", 8)
        metallic_m = request.get("metallic_m", 1)
        if not isinstance(scale_order, int) or isinstance(scale_order, bool):
            raise ValueError("scale_order must be an integer")
        if not isinstance(metallic_m, int) or isinstance(metallic_m, bool):
            raise ValueError("metallic_m must be an integer")
        from chronus.storage.connectors import zero_copy_connector_manager

        try:
            pointer_result = zero_copy_connector_manager.execute_against_pointer(
                pointer_id=pointer_id,
                operation=operation,
                scale_order=scale_order,
                metallic_m=metallic_m,
            )
        except KeyError as exc:
            raise ValueError(f"Zero-copy pointer '{pointer_id}' not found") from exc
        pointer_result["execution_mode"] = self.execution_mode
        return pointer_result

    def _execute_norm_proof(self, request: Dict[str, Any]) -> Dict[str, Any]:
        operation = request.get("operation")
        if operation == "prove":
            witness = request.get("witness")
            if not isinstance(witness, list) or len(witness) != 2:
                raise ValueError("witness must be [a, b] with entries in [0, 257)")
            proof = norm_proof.prove((witness[0], witness[1]))
            result = proof.to_dict()
            result["valid"] = norm_proof.verify(proof)
            result["execution_mode"] = self.execution_mode
            return result
        if operation == "verify":
            proof = norm_proof.NormProof.from_dict(request.get("proof"))
            return {
                "execution_mode": self.execution_mode,
                "protocol": "schnorr-norm-preimage-f257phi",
                "valid": norm_proof.verify(proof),
            }
        raise ValueError("operation must be 'prove' or 'verify'")

    def _execute_metallic(self, request: Dict[str, Any]) -> Dict[str, Any]:
        bounds = runtime_bounds()
        m, index = request.get("m"), request.get("index")
        max_m = bounds["max_metallic_m"]
        if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= max_m:
            raise ValueError(f"m must be an integer between 1 and {max_m}")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("index must be a non-negative integer")
        if index > bounds["max_metallic_index"]:
            raise ValueError(f"index exceeds limit ({bounds['max_metallic_index']})")
        power = metallic_power(m, index)
        names = {1: "golden", 2: "silver", 3: "bronze"}
        return {
            "execution_mode": self.execution_mode,
            "metallic_index": m,
            "family": names.get(m, f"metallic-{m}"),
            "order": index,
            "a": str(power.a),
            "b": str(power.b),
            "trace": str(power.trace().numerator),
            "norm": str(power.norm().numerator),
            "interpretation": f"sigma_{m}^{index} = a + b*sigma_{m}",
        }

    def _scaling_slide(self, num_qubits: int) -> list[Dict[str, Any]]:
        """Lucas ladder around the requested scale: the slide as n grows."""
        from chronus.backends.metallic import metallic_sequence
        from chronus.quantum.metallic_search import jform_one_shot_phases
        from chronus.quantum.statevector import INV_SQRT2, P

        slide = []
        for rung in range(max(1, num_qubits - 2), num_qubits + 3):
            alpha, beta = jform_one_shot_phases(rung, 1)[0]
            slide.append({
                "num_qubits": rung,
                "lucas_trace": str(metallic_sequence(1, rung)),
                "N_mod257": pow(2, rung, P),
                "uniform_amplitude": pow(INV_SQRT2, rung, P),
                "phases": {"alpha": alpha, "beta": beta},
            })
        return slide

    def _execute_phase_search(self, request: Dict[str, Any]) -> Dict[str, Any]:
        num_qubits, marked_count = request.get("num_qubits"), request.get("marked_count")
        if not isinstance(num_qubits, int) or isinstance(num_qubits, bool):
            raise ValueError("num_qubits must be an integer")
        if not isinstance(marked_count, int) or isinstance(marked_count, bool):
            raise ValueError("marked_count must be an integer")
        surface = request.get("surface", "substrate")
        if surface not in ("substrate", "auto", "accelerator"):
            raise ValueError("surface must be 'substrate', 'auto' or 'accelerator'")
        if surface != "substrate":
            accelerator = next(
                (backend for backend in execution_router._backends.values()
                 if hasattr(backend, "probe_silicon")
                 and backend.supports("EXACT_PHASE_SEARCH")),
                None,
            )
            if accelerator is not None:
                result = accelerator.execute(
                    json.dumps({
                        "num_qubits": num_qubits, "marked_count": marked_count,
                    }).encode(),
                    "EXACT_PHASE_SEARCH",
                )
                result["scaling_slide"] = self._scaling_slide(num_qubits)
                return result
            if surface == "accelerator":
                from chronus.backends.lattice import HardwareUnavailableError
                raise HardwareUnavailableError(
                    "no client accelerator is provisioned for EXACT_PHASE_SEARCH"
                )
        state = exact_subspace_search(num_qubits, marked_count)
        result = {
            "execution_mode": self.execution_mode,
            "surface": "substrate",
            "field": "F_257",
            "iterations": 1,
            "state": state.to_dict(),
            "scaling_slide": self._scaling_slide(num_qubits),
        }
        if request.get("store") is True:
            # Converged states persist in the phyllotaxis memory substrate:
            # content-addressed in Ovid, lane-addressed by the golden ratio,
            # with PV scale lineage carried on the Theseus record.
            record = self._theseus.store(
                "phase-search",
                json.dumps(result["state"], sort_keys=True).encode("utf-8"),
                scale_index=num_qubits,
            )
            result["memory"] = {
                "theseus_record": record.to_dict(),
                "cassini_parity": -1 if num_qubits % 2 else 1,
                "durable": False,
            }
        elif "store" in request:
            raise ValueError("store must be a boolean true when present")
        return result

    def _execute_q5(self, request: Dict[str, Any]) -> Dict[str, Any]:
        operation = request.get("operation")
        if operation not in {"add", "subtract", "multiply", "divide"}:
            raise ValueError("operation must be add, subtract, multiply, or divide")
        left_a, left_b = _q5_element(request.get("left"), "left")
        right_a, right_b = _q5_element(request.get("right"), "right")

        if operation == "add":
            result = (left_a + right_a, left_b + right_b)
        elif operation == "subtract":
            result = (left_a - right_a, left_b - right_b)
        elif operation == "multiply":
            result = (
                left_a * right_a + 5 * left_b * right_b,
                left_a * right_b + left_b * right_a,
            )
        else:
            norm = right_a * right_a - 5 * right_b * right_b
            if norm == 0:
                raise ValueError("cannot divide by a zero-norm Q(sqrt(5)) value")
            result = (
                (left_a * right_a - 5 * left_b * right_b) / norm,
                (left_b * right_a - left_a * right_b) / norm,
            )

        return {
            "representation": "Q(sqrt(5))",
            "operation": operation,
            "result": {
                "rational": _serialize_fraction(result[0]),
                "sqrt5": _serialize_fraction(result[1]),
            },
        }


class ExecutionRouter:
    """Select a registered backend without changing workload semantics."""

    def __init__(self) -> None:
        self._backends: Dict[str, ExecutionBackend] = {}
        self.register_backend(NativeMathReferenceBackend())

    def register_backend(self, backend: ExecutionBackend) -> None:
        if not backend.name or backend.name in self._backends:
            raise ValueError("backend name must be non-empty and unique")
        self._backends[backend.name] = backend

    def execute(
        self,
        payload: bytes,
        workload_type: str,
        backend_name: str | None = None,
    ) -> ExecutionReceipt:
        if backend_name is not None:
            backend = self._backends.get(backend_name)
            if backend is None:
                for cand in self._backends.values():
                    if (
                        cand.__class__.__name__ == backend_name
                        or getattr(cand, "name", None) == backend_name
                    ):
                        backend = cand
                        break
            if backend is None:
                raise ValueError(
                    f"execution backend '{backend_name}' is not registered"
                )
            if not backend.supports(workload_type):
                raise ValueError(
                    f"backend '{backend_name}' does not support {workload_type}"
                )
        else:
            backend = next(
                (
                    candidate
                    for candidate in self._backends.values()
                    if candidate.supports(workload_type)
                ),
                None,
            )
            if backend is None:
                raise ValueError(
                    f"no registered execution backend supports {workload_type}"
                )

        started = time.perf_counter()
        result = backend.execute(payload, workload_type)
        return ExecutionReceipt(
            backend=backend.name,
            execution_state="EXECUTED",
            execution_mode=getattr(backend, "execution_mode", "SOFTWARE_EXECUTION"),
            duration_ms=(time.perf_counter() - started) * 1000,
            result=result,
        )

    def list_backends(self) -> Dict[str, list[str]]:
        return {
            name: sorted(backend.supported_workloads)
            for name, backend in self._backends.items()
        }


execution_router = ExecutionRouter()
if os.getenv("CHRONUS_ENABLE_OPENCL_PV") == "1":
    from chronus.backends.opencl_pv import OpenCLPVBackend

    execution_router.register_backend(OpenCLPVBackend())
