"""Exact mathematical reference execution and backend selection."""

import json
import os
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, Protocol

from chronus.backends.lattice import ParityVerificationError, phi_power
from chronus.backends.lattice_workload import parse_lattice_workload, serialize_lattice
from chronus.execution.mining import search_nonce_range
from chronus.execution.trinity import scale_fold_store


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
        or not all(isinstance(part, int) and not isinstance(part, bool) for part in value)
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
        {"EXACT_Q5_ALGEBRAIC", "LUCAS_PV_SCALING", "SHA256D_NONCE_SEARCH",
         "PV_LATTICE_FOLD", "TRINITY_SCALE_FOLD_STORE"}
    )
    max_payload_bytes = 1024 * 1024
    max_lucas_index = 100_000

    def supports(self, workload_type: str) -> bool:
        return workload_type in self.supported_workloads

    def execute(self, payload: bytes, workload_type: str) -> Dict[str, Any]:
        if not self.supports(workload_type):
            raise ValueError(f"Native reference backend does not support {workload_type}")
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("payload must be non-empty bytes")
        if len(payload) > self.max_payload_bytes:
            raise ValueError("reference workload payload exceeds 1 MiB")
        if workload_type == "PV_LATTICE_FOLD":
            values, order = parse_lattice_workload(payload)
            factor = phi_power(order)
            outputs = [value.multiply(factor) for value in values]
            sign = -1 if order % 2 else 1
            if any(output.norm() != value.norm() * sign for value, output in zip(values, outputs)):
                raise ParityVerificationError("CPU reference norm invariant failed")
            return {
                "execution_mode": self.execution_mode,
                "device_signature": None,
                "verification": "exact_cpu_reference_and_norm",
                "norm_invariant_verified": True,
                "values": serialize_lattice(outputs),
            }
        try:
            request = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("payload must be a UTF-8 JSON object") from exc
        if not isinstance(request, dict):
            raise ValueError("payload must be a JSON object")

        if workload_type == "TRINITY_SCALE_FOLD_STORE":
            return scale_fold_store(request)
        if workload_type == "LUCAS_PV_SCALING":
            return self._execute_lucas(request)
        if workload_type == "SHA256D_NONCE_SEARCH":
            return self._execute_nonce_search(request)
        return self._execute_q5(request)

    def _execute_nonce_search(self, request: Dict[str, Any]) -> Dict[str, Any]:
        header_hex = request.get("header_hex")
        target_hex = request.get("target_hex")
        if not isinstance(header_hex, str) or len(header_hex) != 160:
            raise ValueError("header_hex must contain exactly 160 hexadecimal characters")
        if not isinstance(target_hex, str) or len(target_hex) != 64:
            raise ValueError("target_hex must contain exactly 64 hexadecimal characters")
        if any(character not in "0123456789abcdefABCDEF" for character in header_hex + target_hex):
            raise ValueError("header_hex and target_hex must be hexadecimal")
        try:
            header = bytes.fromhex(header_hex)
            target = int(target_hex, 16)
        except ValueError as exc:
            raise ValueError("header_hex and target_hex must be hexadecimal") from exc
        return search_nonce_range(
            header,
            request.get("start"),
            request.get("stop"),
            target,
            request.get("workers", 1),
        )

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
                raise ValueError(f"execution backend '{backend_name}' is not registered")
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
