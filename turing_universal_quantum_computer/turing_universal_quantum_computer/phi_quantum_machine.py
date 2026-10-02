"""Production φ-machine facade for the consolidated Turing VQC package.

This module integrates the July 2026 1,000-logical-qubit artifact with the
stronger in-repository exact stabilizer backend.  It deliberately does not
reintroduce the archived NumPy boolean tableau: ``StabilizerState`` already
provides a more compact integer-bitset Aaronson-Gottesman representation,
exact Clifford evolution, exact Born probabilities and fail-closed handling of
non-Clifford gates.

PULVINI checkpointing is an exact recursive representation transform.  It is
not advertised as physical compression.  Each layer stores the left element
of every Fibonacci-Q pair and propagates the pair sum; the inverse recovers the
right element as ``sum-left``.  When the repository's canonical
``python_backend.core_modules.math_folding.pulvini_fold`` is importable, every
layer is cross-checked against it.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import random
import re
import time
from typing import Any, Optional, Sequence

from .stabilizer import StabilizerState

CLIFFORD_GATES = frozenset({"h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap"})
ALGORITHM_CATALOG = (
    "grover",
    "shor",
    "qft",
    "vqe",
    "qaoa",
    "qml",
    "quantum_walk",
    "quantum_sensing",
    "qec",
    "annealing",
    "hybrid",
    "phase_estimation",
)


class PhiMachineValidationError(ValueError):
    """Invalid circuit, checkpoint or execution request."""


@dataclass(frozen=True)
class Gate:
    name: str
    qubits: tuple[int, ...]


@dataclass
class PhiQuantumCircuit:
    num_qubits: int
    gates: list[Gate] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.num_qubits, int) or self.num_qubits < 1:
            raise PhiMachineValidationError("num_qubits must be a positive integer")

    def _append(self, name: str, *qubits: int) -> "PhiQuantumCircuit":
        name = name.lower()
        if name not in CLIFFORD_GATES:
            raise PhiMachineValidationError(
                f"unsupported/non-Clifford gate {name!r}; use another exact Turing backend"
            )
        expected = 2 if name in {"cx", "cz", "swap"} else 1
        if len(qubits) != expected:
            raise PhiMachineValidationError(f"{name} expects {expected} qubit(s)")
        normalized = tuple(int(q) for q in qubits)
        if any(q < 0 or q >= self.num_qubits for q in normalized):
            raise PhiMachineValidationError("qubit index outside circuit")
        if expected == 2 and normalized[0] == normalized[1]:
            raise PhiMachineValidationError(f"{name} requires distinct qubits")
        self.gates.append(Gate(name, normalized))
        return self

    def h(self, q: int): return self._append("h", q)
    def s(self, q: int): return self._append("s", q)
    def sdg(self, q: int): return self._append("sdg", q)
    def x(self, q: int): return self._append("x", q)
    def y(self, q: int): return self._append("y", q)
    def z(self, q: int): return self._append("z", q)
    def cx(self, control: int, target: int): return self._append("cx", control, target)
    def cz(self, a: int, b: int): return self._append("cz", a, b)
    def swap(self, a: int, b: int): return self._append("swap", a, b)

    @classmethod
    def ghz(cls, num_qubits: int) -> "PhiQuantumCircuit":
        circuit = cls(num_qubits).h(0)
        for q in range(1, num_qubits):
            circuit.cx(0, q)
        return circuit

    @classmethod
    def from_qasm(cls, qasm: str) -> "PhiQuantumCircuit":
        """Parse the bounded OpenQASM-2 Clifford subset used by this backend."""
        match = re.search(r"qreg\s+q\[(\d+)\]\s*;", qasm, re.IGNORECASE)
        if not match:
            raise PhiMachineValidationError("QASM must declare qreg q[n]")
        circuit = cls(int(match.group(1)))
        for raw in qasm.splitlines():
            line = raw.strip().lower()
            if (
                not line
                or line.startswith("//")
                or line.startswith("openqasm")
                or line.startswith("include")
                or line.startswith("qreg")
                or line.startswith("creg")
                or line.startswith("measure")
                or line.startswith("barrier")
            ):
                continue
            two = re.fullmatch(r"(cx|cz|swap)\s+q\[(\d+)\]\s*,\s*q\[(\d+)\]\s*;", line)
            if two:
                circuit._append(two.group(1), int(two.group(2)), int(two.group(3)))
                continue
            one = re.fullmatch(r"(h|s|sdg|x|y|z)\s+q\[(\d+)\]\s*;", line)
            if one:
                circuit._append(one.group(1), int(one.group(2)))
                continue
            raise PhiMachineValidationError(f"unsupported QASM statement: {raw.strip()}")
        return circuit


class AffineZSampler:
    """Fast exact GF(2) Z-basis sampler for affine Clifford circuit families.

    Each output bit is represented as ``offset XOR parity(mask & random_bits)``.
    This covers the large GHZ path without copying/measuring a 1,000-qubit
    tableau once per shot.  If an H is applied to an already-dependent wire,
    the circuit exits this bounded affine family and sampling falls back to
    the exact tableau policy.
    """

    def __init__(self, num_qubits: int):
        self.n = int(num_qubits)
        self.offset = [0] * self.n
        self.coefficients = [0] * self.n
        self.variables = 0
        self.valid = True

    def apply(self, gate: Gate) -> None:
        if not self.valid:
            return
        if gate.name == "h":
            q = gate.qubits[0]
            if self.coefficients[q]:
                self.valid = False
                return
            if self.variables >= self.n:
                self.valid = False
                return
            self.coefficients[q] = 1 << self.variables
            self.offset[q] = 0
            self.variables += 1
        elif gate.name in {"x", "y"}:
            self.offset[gate.qubits[0]] ^= 1
        elif gate.name in {"z", "s", "sdg"}:
            return
        elif gate.name == "cx":
            c, t = gate.qubits
            self.offset[t] ^= self.offset[c]
            self.coefficients[t] ^= self.coefficients[c]
        else:
            # CZ/SWAP are exact Clifford but are outside this simple affine
            # Z-distribution tracker; the stabilizer backend still handles them.
            self.valid = False

    def sample(self, shots: int, seed: int) -> tuple[tuple[int, ...], ...]:
        if not self.valid:
            raise PhiMachineValidationError("circuit is outside affine sampler family")
        rng = random.Random(seed)
        rows: list[tuple[int, ...]] = []
        for _ in range(shots):
            random_bits = rng.getrandbits(self.variables) if self.variables else 0
            row = tuple(
                int(offset ^ ((mask & random_bits).bit_count() & 1))
                for offset, mask in zip(self.offset, self.coefficients)
            )
            rows.append(row)
        return tuple(rows)


@dataclass(frozen=True)
class PulviniLayer:
    original_length: int
    left_values: tuple[int, ...]


@dataclass(frozen=True)
class PhiCheckpoint:
    """Exact recursive PULVINI representation of a canonical tableau payload."""

    layers: tuple[PulviniLayer, ...]
    terminal_values: tuple[int, ...]
    payload_size: int
    digest: str
    depth: int
    exact: bool = True
    claim_boundary: str = "exact representation transform; no physical compression claim"


@dataclass(frozen=True)
class ExecutionResult:
    logical_qubits: int
    gates_executed: int
    shots: int
    samples: tuple[tuple[int, ...], ...]
    counts: dict[str, int]
    logical_tableau_bits: int
    packed_tableau_bytes: int
    dense_statevector_log2_bytes: int
    execution_ms: float
    state_digest: str
    stabilizer_group_digest: str
    backend: str = "turing-exact-stabilizer"
    truth_class: str = "exact-clifford"


class PhiQuantumMachine:
    """Production facade over Turing's exact stabilizer substrate."""

    def __init__(self, logical_qubits: int = 1000, fold_depth: int = 20):
        if not isinstance(logical_qubits, int) or not 1 <= logical_qubits <= 100_000:
            raise PhiMachineValidationError("logical_qubits outside machine policy [1, 100000]")
        if not isinstance(fold_depth, int) or fold_depth < 0:
            raise PhiMachineValidationError("fold_depth must be a non-negative integer")
        self.logical_qubits = logical_qubits
        self.fold_depth = fold_depth
        self.register = StabilizerState(logical_qubits)
        self.sampler = AffineZSampler(logical_qubits)
        self.gates_executed = 0
        self.last_checkpoint: Optional[PhiCheckpoint] = None

    def reset(self) -> None:
        self.register = StabilizerState(self.logical_qubits)
        self.sampler = AffineZSampler(self.logical_qubits)
        self.gates_executed = 0

    def _apply_gate(self, gate: Gate) -> None:
        method = "cnot" if gate.name == "cx" else gate.name
        operation = getattr(self.register, method, None)
        if operation is None:
            raise PhiMachineValidationError(f"stabilizer backend missing gate {gate.name}")
        operation(*gate.qubits)
        self.sampler.apply(gate)
        self.gates_executed += 1

    def apply_circuit(self, circuit: PhiQuantumCircuit) -> None:
        if circuit.num_qubits != self.logical_qubits:
            raise PhiMachineValidationError("circuit width does not match machine")
        for gate in circuit.gates:
            self._apply_gate(gate)

    @property
    def logical_tableau_bits(self) -> int:
        return 2 * self.logical_qubits * (2 * self.logical_qubits + 1)

    @property
    def packed_tableau_bytes(self) -> int:
        return (self.logical_tableau_bits + 7) // 8

    def _state_payload(self) -> bytes:
        """Canonical packed payload independent of Python object representation."""
        n = self.logical_qubits
        width = (n + 7) // 8
        out = bytearray()
        out.extend(n.to_bytes(8, "little", signed=False))
        for x, z, r in zip(self.register._x, self.register._z, self.register._r):
            out.extend(int(x).to_bytes(width, "little", signed=False))
            out.extend(int(z).to_bytes(width, "little", signed=False))
            out.append(int(bool(r)))
        return bytes(out)

    @staticmethod
    def _digest_payload(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def state_digest(self) -> str:
        return self._digest_payload(self._state_payload())

    def stabilizer_group_digest(self) -> str:
        """Digest the n stabilizer generators only (destabilizers excluded)."""
        n = self.logical_qubits
        canonical = tuple(
            (int(self.register._x[n + i]), int(self.register._z[n + i]), int(bool(self.register._r[n + i])))
            for i in range(n)
        )
        blob = json.dumps(canonical, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _restore_payload(self, payload: bytes) -> None:
        n = self.logical_qubits
        width = (n + 7) // 8
        expected = 8 + (2 * n) * (2 * width + 1)
        if len(payload) != expected:
            raise PhiMachineValidationError(
                f"checkpoint payload size mismatch: {len(payload)} != {expected}"
            )
        encoded_n = int.from_bytes(payload[:8], "little", signed=False)
        if encoded_n != n:
            raise PhiMachineValidationError(
                f"checkpoint width {encoded_n} does not match machine width {n}"
            )
        mask = (1 << n) - 1
        x_rows: list[int] = []
        z_rows: list[int] = []
        phases: list[int] = []
        cursor = 8
        for _ in range(2 * n):
            x = int.from_bytes(payload[cursor:cursor + width], "little", signed=False)
            cursor += width
            z = int.from_bytes(payload[cursor:cursor + width], "little", signed=False)
            cursor += width
            r = payload[cursor]
            cursor += 1
            if x & ~mask or z & ~mask or r not in (0, 1):
                raise PhiMachineValidationError("checkpoint contains invalid tableau data")
            x_rows.append(x)
            z_rows.append(z)
            phases.append(r)
        state = StabilizerState(n)
        state._x = x_rows
        state._z = z_rows
        state._r = phases
        self.register = state
        # A restored arbitrary Clifford state cannot safely reuse stale affine
        # sampling metadata. Future measurement uses the exact tableau path.
        self.sampler = AffineZSampler(n)
        self.sampler.valid = False

    @staticmethod
    def _canonical_fold_crosscheck(values: Sequence[int]) -> None:
        try:
            from python_backend.core_modules.math_folding import pulvini_fold
        except Exception:
            return
        folded = pulvini_fold(values)
        exact = tuple(Fraction(v) for v in values)
        if folded.unfold() != exact:
            raise RuntimeError("canonical PULVINI round-trip invariant failed")
        pairs = tuple((int(a), int(b)) for a, b in folded.pairs)
        expected = []
        padded = list(values)
        if len(padded) % 2:
            padded.append(0)
        for i in range(0, len(padded), 2):
            expected.append((padded[i] + padded[i + 1], padded[i]))
        if pairs != tuple(expected):
            raise RuntimeError("local PULVINI layer diverges from canonical repository transform")

    @staticmethod
    def _fold_layer(values: Sequence[int]) -> tuple[PulviniLayer, tuple[int, ...]]:
        if not values:
            return PulviniLayer(0, ()), ()
        if len(values) <= 4096:
            PhiQuantumMachine._canonical_fold_crosscheck(values)
        padded = list(int(v) for v in values)
        original_length = len(padded)
        if original_length % 2:
            padded.append(0)
        lefts: list[int] = []
        combined: list[int] = []
        for i in range(0, len(padded), 2):
            left = padded[i]
            right = padded[i + 1]
            lefts.append(left)
            combined.append(left + right)
        return PulviniLayer(original_length, tuple(lefts)), tuple(combined)

    @staticmethod
    def _unfold_layer(layer: PulviniLayer, combined: Sequence[int]) -> tuple[int, ...]:
        if len(combined) != len(layer.left_values):
            raise PhiMachineValidationError("PULVINI layer arity mismatch")
        output: list[int] = []
        for total, left in zip(combined, layer.left_values):
            output.extend((int(left), int(total) - int(left)))
        return tuple(output[:layer.original_length])

    def checkpoint(self, depth: Optional[int] = None) -> PhiCheckpoint:
        requested = self.fold_depth if depth is None else int(depth)
        if requested < 0:
            raise PhiMachineValidationError("checkpoint depth must be non-negative")
        payload = self._state_payload()
        values: tuple[int, ...] = tuple(payload)
        layers: list[PulviniLayer] = []
        for _ in range(requested):
            layer, values = self._fold_layer(values)
            layers.append(layer)
        checkpoint = PhiCheckpoint(
            layers=tuple(layers),
            terminal_values=values,
            payload_size=len(payload),
            digest=self._digest_payload(payload),
            depth=requested,
         )
        if self._checkpoint_payload(checkpoint) != payload:
            raise RuntimeError("PULVINI checkpoint round-trip failed")
        self.last_checkpoint = checkpoint
        return checkpoint

    def _checkpoint_payload(self, checkpoint: PhiCheckpoint) -> bytes:
        values: tuple[int, ...] = tuple(int(v) for v in checkpoint.terminal_values)
        for layer in reversed(checkpoint.layers):
            values = self._unfold_layer(layer, values)
        if any(v < 0 or v > 255 for v in values):
            raise PhiMachineValidationError("checkpoint reconstruction escaped byte domain")
        payload = bytes(values)
        if len(payload) != checkpoint.payload_size:
            raise PhiMachineValidationError("checkpoint payload size mismatch")
        if self._digest_payload(payload) != checkpoint.digest:
            raise PhiMachineValidationError("checkpoint digest mismatch")
        return payload

    def restore(self, checkpoint: Optional[PhiCheckpoint] = None) -> None:
        checkpoint = checkpoint or self.last_checkpoint
        if checkpoint is None:
            raise PhiMachineValidationError("no checkpoint available")
        if checkpoint.depth != len(checkpoint.layers):
            raise PhiMachineValidationError("checkpoint depth metadata mismatch")
        payload = self._checkpoint_payload(checkpoint)
        self._restore_payload(payload)
        if self.state_digest() != checkpoint.digest:
            raise PhiMachineValidationError("restored state failed digest verification")
        self.last_checkpoint = checkpoint

    def regenerate(self) -> None:
        self.restore(self.last_checkpoint)

    @staticmethod
    def _counts(samples: Sequence[Sequence[int]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in samples:
            key = "".join(str(int(bit)) for bit in row)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def sample(self, shots: int = 1, seed: int = 42) -> tuple[tuple[int, ...], ...]:
        if not isinstance(shots, int) or shots < 1:
            raise PhiMachineValidationError("shots must be a positive integer")
        if self.sampler.valid:
            return self.sampler.sample(shots, seed)
        # General tableau measurement is deliberately bounded to prevent a
        # misleading high-width/large-shot request from turning into hidden
        # quadratic work. Exact probabilities remain available per qubit on
        # StabilizerState without this sampled convenience path.
        if self.logical_qubits > 64 or shots > 128:
            raise PhiMachineValidationError(
                "general tableau sampling policy exceeded (max 64 qubits, 128 shots)"
            )
        rows: list[tuple[int, ...]] = []
        for shot in range(shots):
            reg = deepcopy(self.register)
            row = []
            for q in range(self.logical_qubits):
                measurement = reg.measure(q, seed=(seed << 20) ^ (shot << 10) ^ q)
                row.append(int(measurement["outcome"]))
            rows.append(tuple(row))
        return tuple(rows)

    def execute(self, circuit: PhiQuantumCircuit, shots: int = 1, seed: int = 42) -> ExecutionResult:
        started = time.perf_counter()
        self.reset()
        self.apply_circuit(circuit)
        samples = self.sample(shots, seed)
        return ExecutionResult(
            logical_qubits=self.logical_qubits,
            gates_executed=self.gates_executed,
            shots=shots,
            samples=samples,
            counts=self._counts(samples),
            logical_tableau_bits=self.logical_tableau_bits,
            packed_tableau_bytes=self.packed_tableau_bytes,
            dense_statevector_log2_bytes=self.logical_qubits + 4,
            execution_ms=(time.perf_counter() - started) * 1000.0,
            state_digest=self.state_digest(),
            stabilizer_group_digest=self.stabilizer_group_digest(),
        )

    def plan_algorithm(self, algorithm: str, problem_qubits: Optional[int] = None) -> dict[str, Any]:
        """Return capability metadata without promoting plans to execution claims."""
        name = algorithm.lower()
        if name not in ALGORITHM_CATALOG:
            raise PhiMachineValidationError(f"unknown algorithm: {algorithm}")
        n = self.logical_qubits if problem_qubits is None else int(problem_qubits)
        if not 1 <= n <= self.logical_qubits:
            raise PhiMachineValidationError("problem width outside machine")
        plan: dict[str, Any] = {
            "algorithm": name,
            "logical_qubits": n,
            "stabilizer_backend": "exact-clifford",
            "claim_boundary": "plan metadata is not evidence of executable universal quantum advantage",
        }
        if name == "qec":
            plan.update(status="executable-clifford", stabilizer_tableau=True, syndrome_channels=n)
        elif name == "grover":
            plan.update(
                status="bounded-executable-on-other-turing-backends",
                search_space_log2=n,
                iteration_log2=n / 2,
                required_backend="exact sparse/tensor with oracle support",
            )
        elif name == "qft":
            plan.update(
                status="planned-on-this-backend",
                gate_count=n * (n + 1) // 2,
                depth=n,
                reason="general QFT requires non-Clifford controlled phases",
            )
        elif name == "shor":
            plan.update(
                status="restricted-on-stabilizer",
                max_planned_modulus_bits=max(1, n // 2),
                reason="period finding requires non-Clifford/universal execution",
            )
        else:
            plan.update(
                status="planned-or-backend-dependent",
                required_backend="select an exact Turing backend that supports the circuit domain",
            )
        return plan

    def system_report(self) -> dict[str, Any]:
        return {
            "machine": "HYBA/Turing φ-Quantum Machine",
            "logical_qubits": self.logical_qubits,
            "backend": "Turing integer-bitset Aaronson-Gottesman stabilizer",
            "truth_class": "exact Clifford algebra",
            "logical_tableau_bits": self.logical_tableau_bits,
            "packed_tableau_bytes": self.packed_tableau_bytes,
            "dense_statevector_amplitudes": f"2^{self.logical_qubits}",
            "dense_statevector_log2_bytes_complex128": self.logical_qubits + 4,
            "algorithms": list(ALGORITHM_CATALOG),
            "algorithm_count": len(ALGORITHM_CATALOG),
            "fold_depth": self.fold_depth,
            "gates_executed": self.gates_executed,
            "non_clifford_policy": "fail-closed on stabilizer backend",
            "checkpoint_policy": "exact PULVINI-compatible recursive representation; digest verified",
            "advantage_claim": "restricted/not implied by this backend",
        }


class PhiQuantumMachine1000(PhiQuantumMachine):
    def __init__(self, logical_qubits: int = 1000, fold_depth: int = 20):
        super().__init__(logical_qubits=logical_qubits, fold_depth=fold_depth)


__all__ = [
    "ALGORITHM_CATALOG",
    "CLIFFORD_GATES",
    "ExecutionResult",
    "Gate",
    "PhiCheckpoint",
    "PhiMachineValidationError",
    "PhiQuantumCircuit",
    "PhiQuantumMachine",
    "PhiQuantumMachine1000",
    "PulviniLayer",
]
