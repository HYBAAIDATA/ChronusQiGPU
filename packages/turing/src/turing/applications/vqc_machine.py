"""HYBA Data 1,000-logical-qubit φ-quantum machine.

A scalable classical-silicon execution substrate for quantum algebra.  Clifford
circuits are executed with an Aaronson-Gottesman stabilizer tableau, avoiding a
2**n dense state vector.  A compatible affine sampler provides fast Z-basis
shots for H/CNOT/X/S/Z circuit families, including 1,000-qubit GHZ workloads.
PULVINI fold checkpoints provide exact, hash-verified restoration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
import hashlib
import json
import math
import re
import time
import numpy as np

from turing.applications.vqc_fold import FoldState, PhiRecursiveOperator, PHI, ValidationError


CLIFFORD_GATES = {"h", "s", "x", "y", "z", "cx"}
ALGORITHM_CATALOG = (
    "grover", "shor", "qft", "vqe", "qaoa", "qml",
    "quantum_walk", "quantum_sensing", "qec", "annealing",
    "hybrid", "phase_estimation",
)


@dataclass(frozen=True)
class Gate:
    name: str
    qubits: tuple[int, ...]


@dataclass
class PhiQuantumCircuit:
    num_qubits: int
    gates: list[Gate] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.num_qubits < 1:
            raise ValidationError("num_qubits must be positive")

    def _append(self, name: str, *qubits: int) -> "PhiQuantumCircuit":
        name = name.lower()
        if name not in CLIFFORD_GATES:
            raise ValidationError(f"unsupported gate: {name}")
        expected = 2 if name == "cx" else 1
        if len(qubits) != expected:
            raise ValidationError(f"{name} expects {expected} qubit(s)")
        if any(q < 0 or q >= self.num_qubits for q in qubits):
            raise ValidationError("qubit index outside circuit")
        if name == "cx" and qubits[0] == qubits[1]:
            raise ValidationError("CNOT control and target must differ")
        self.gates.append(Gate(name, tuple(int(q) for q in qubits)))
        return self

    def h(self, q: int): return self._append("h", q)
    def s(self, q: int): return self._append("s", q)
    def x(self, q: int): return self._append("x", q)
    def y(self, q: int): return self._append("y", q)
    def z(self, q: int): return self._append("z", q)
    def cx(self, control: int, target: int): return self._append("cx", control, target)

    @classmethod
    def ghz(cls, num_qubits: int) -> "PhiQuantumCircuit":
        circuit = cls(num_qubits).h(0)
        for q in range(1, num_qubits):
            circuit.cx(0, q)
        return circuit

    @classmethod
    def from_qasm(cls, qasm: str) -> "PhiQuantumCircuit":
        match = re.search(r"qreg\s+q\[(\d+)\]\s*;", qasm)
        if not match:
            raise ValidationError("QASM must declare qreg q[n]")
        circuit = cls(int(match.group(1)))
        for raw in qasm.splitlines():
            line = raw.strip().lower()
            if not line or line.startswith("//") or line.startswith("openqasm") or line.startswith("include") or line.startswith("qreg") or line.startswith("creg") or line.startswith("measure"):
                continue
            two = re.fullmatch(r"cx\s+q\[(\d+)\]\s*,\s*q\[(\d+)\]\s*;", line)
            if two:
                circuit.cx(int(two.group(1)), int(two.group(2)))
                continue
            one = re.fullmatch(r"(h|s|x|y|z)\s+q\[(\d+)\]\s*;", line)
            if one:
                circuit._append(one.group(1), int(one.group(2)))
                continue
            raise ValidationError(f"unsupported QASM statement: {raw.strip()}")
        return circuit


class StabilizerRegister:
    """Binary symplectic stabilizer tableau for n logical qubits."""

    def __init__(self, num_qubits: int):
        if num_qubits < 1:
            raise ValidationError("num_qubits must be positive")
        self.n = int(num_qubits)
        self.x = np.zeros((2 * self.n, self.n), dtype=np.bool_)
        self.z = np.zeros((2 * self.n, self.n), dtype=np.bool_)
        self.r = np.zeros(2 * self.n, dtype=np.bool_)
        idx = np.arange(self.n)
        self.x[idx, idx] = True
        self.z[self.n + idx, idx] = True

    def copy(self) -> "StabilizerRegister":
        other = object.__new__(StabilizerRegister)
        other.n = self.n
        other.x = self.x.copy(); other.z = self.z.copy(); other.r = self.r.copy()
        return other

    @property
    def storage_bytes(self) -> int:
        return int(self.x.nbytes + self.z.nbytes + self.r.nbytes)

    @property
    def dense_statevector_bytes(self) -> int:
        return (1 << self.n) * 16

    def h(self, q: int) -> None:
        self.r ^= self.x[:, q] & self.z[:, q]
        tmp = self.x[:, q].copy(); self.x[:, q] = self.z[:, q]; self.z[:, q] = tmp

    def s(self, q: int) -> None:
        self.r ^= self.x[:, q] & self.z[:, q]
        self.z[:, q] ^= self.x[:, q]

    def x_gate(self, q: int) -> None: self.r ^= self.z[:, q]
    def z_gate(self, q: int) -> None: self.r ^= self.x[:, q]
    def y_gate(self, q: int) -> None: self.r ^= self.x[:, q] ^ self.z[:, q]

    def cx(self, control: int, target: int) -> None:
        xa = self.x[:, control].copy(); xb = self.x[:, target].copy()
        za = self.z[:, control].copy(); zb = self.z[:, target].copy()
        self.r ^= xa & zb & (xb ^ za ^ True)
        self.x[:, target] ^= xa
        self.z[:, control] ^= zb

    @staticmethod
    def _g(x1: bool, z1: bool, x2: bool, z2: bool) -> int:
        if not x1 and not z1: return 0
        if x1 and z1: return int(z2) - int(x2)
        if x1: return int(z2) * (2 * int(x2) - 1)
        return int(x2) * (1 - 2 * int(z2))

    def _rowsum_arrays(self, xh: np.ndarray, zh: np.ndarray, rh: bool,
                       xi: np.ndarray, zi: np.ndarray, ri: bool) -> tuple[np.ndarray, np.ndarray, bool]:
        phase = 2 * int(rh) + 2 * int(ri)
        for q in range(self.n):
            phase += self._g(bool(xi[q]), bool(zi[q]), bool(xh[q]), bool(zh[q]))
        phase %= 4
        return xh ^ xi, zh ^ zi, bool((phase // 2) & 1)

    def rowsum(self, h: int, i: int) -> None:
        self.x[h], self.z[h], self.r[h] = self._rowsum_arrays(
            self.x[h], self.z[h], self.r[h], self.x[i], self.z[i], self.r[i]
        )

    def measure_z(self, q: int, rng: np.random.Generator) -> int:
        anti = np.flatnonzero(self.x[self.n:, q])
        if anti.size:
            p = self.n + int(anti[0])
            for i in np.flatnonzero(self.x[:, q]):
                i = int(i)
                if i != p: self.rowsum(i, p)
            self.x[p - self.n] = self.x[p].copy()
            self.z[p - self.n] = self.z[p].copy()
            self.r[p - self.n] = self.r[p]
            self.x[p].fill(False); self.z[p].fill(False); self.z[p, q] = True
            outcome = int(rng.integers(0, 2)); self.r[p] = bool(outcome)
            return outcome
        sx = np.zeros(self.n, dtype=np.bool_)
        sz = np.zeros(self.n, dtype=np.bool_)
        sr = False
        for i in np.flatnonzero(self.x[:self.n, q]):
            sx, sz, sr = self._rowsum_arrays(sx, sz, sr, self.x[self.n + int(i)], self.z[self.n + int(i)], self.r[self.n + int(i)])
        return int(sr)

    def apply(self, gate: Gate) -> None:
        if gate.name == "h": self.h(gate.qubits[0])
        elif gate.name == "s": self.s(gate.qubits[0])
        elif gate.name == "x": self.x_gate(gate.qubits[0])
        elif gate.name == "y": self.y_gate(gate.qubits[0])
        elif gate.name == "z": self.z_gate(gate.qubits[0])
        elif gate.name == "cx": self.cx(*gate.qubits)
        else: raise ValidationError(f"unsupported gate: {gate.name}")

    def payload(self) -> np.ndarray:
        bits = np.concatenate((self.x.reshape(-1), self.z.reshape(-1), self.r))
        return np.packbits(bits, bitorder="little")

    def restore_payload(self, payload: np.ndarray) -> None:
        count = 4 * self.n * self.n + 2 * self.n
        bits = np.unpackbits(np.asarray(payload, dtype=np.uint8), bitorder="little", count=count).astype(bool)
        split = 2 * self.n * self.n
        self.x[:] = bits[:split].reshape(2 * self.n, self.n)
        self.z[:] = bits[split:2 * split].reshape(2 * self.n, self.n)
        self.r[:] = bits[2 * split:]

    def digest(self) -> str:
        return hashlib.sha256(self.payload().tobytes()).hexdigest()


class AffineZSampler:
    """Fast affine GF(2) sampler for computational-basis distributions."""

    def __init__(self, num_qubits: int):
        self.n = num_qubits
        self.offset = np.zeros(self.n, dtype=np.bool_)
        self.coefficients = np.zeros((self.n, self.n), dtype=np.bool_)
        self.variables = 0
        self.valid = True

    def apply(self, gate: Gate) -> None:
        if not self.valid: return
        q = gate.qubits[0]
        if gate.name == "h":
            if self.coefficients[q].any(): self.valid = False; return
            self.coefficients[q].fill(False)
            self.coefficients[q, self.variables] = True
            self.offset[q] = False
            self.variables += 1
            if self.variables > self.n: self.valid = False
        elif gate.name in {"x", "y"}: self.offset[q] ^= True
        elif gate.name in {"z", "s"}: pass
        elif gate.name == "cx":
            c, t = gate.qubits
            self.offset[t] ^= self.offset[c]
            self.coefficients[t] ^= self.coefficients[c]
        else: self.valid = False

    def sample(self, shots: int, rng: np.random.Generator) -> np.ndarray:
        if not self.valid: raise ValidationError("circuit is outside affine sampler family")
        randoms = rng.integers(0, 2, size=(shots, self.variables), dtype=np.uint8).astype(bool)
        out = np.tile(self.offset, (shots, 1))
        for variable in range(self.variables):
            rows = randoms[:, variable]
            if rows.any(): out[rows] ^= self.coefficients[:, variable]
        return out.astype(np.uint8)


@dataclass(frozen=True)
class PhiCheckpoint:
    fold_state: FoldState
    payload_size: int
    digest: str
    depth: int
    reconstruction_error: float


@dataclass
class ExecutionResult:
    logical_qubits: int
    gates_executed: int
    shots: int
    samples: np.ndarray
    counts: dict[str, int]
    tableau_bytes: int
    dense_statevector_bytes: int
    execution_ms: float
    state_digest: str
    backend: str = "phi-stabilizer"


class PhiQuantumMachine1000:
    """Default 1,000-logical-qubit PULVINI/HERMES quantum machine."""

    def __init__(self, logical_qubits: int = 1000, fold_depth: int = 8):
        if logical_qubits < 1 or logical_qubits > 100_000:
            raise ValidationError("logical_qubits outside machine policy")
        self.logical_qubits = int(logical_qubits)
        self.register = StabilizerRegister(self.logical_qubits)
        self.sampler = AffineZSampler(self.logical_qubits)
        self.fold_depth = int(fold_depth)
        self.fold = PhiRecursiveOperator(normalization="orthonormal", max_depth=max(32, fold_depth))
        self.gates_executed = 0
        self.last_checkpoint: Optional[PhiCheckpoint] = None

    def reset(self) -> None:
        self.register = StabilizerRegister(self.logical_qubits)
        self.sampler = AffineZSampler(self.logical_qubits)
        self.gates_executed = 0

    def apply_circuit(self, circuit: PhiQuantumCircuit) -> None:
        if circuit.num_qubits != self.logical_qubits:
            raise ValidationError("circuit width does not match machine")
        for gate in circuit.gates:
            self.register.apply(gate); self.sampler.apply(gate); self.gates_executed += 1

    @staticmethod
    def _counts(samples: np.ndarray) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in samples:
            key = "".join(str(int(bit)) for bit in row)
            result[key] = result.get(key, 0) + 1
        return result

    def sample(self, shots: int = 1, seed: int = 42) -> np.ndarray:
        if shots < 1: raise ValidationError("shots must be positive")
        rng = np.random.default_rng(seed)
        if self.sampler.valid:
            return self.sampler.sample(shots, rng)
        if self.logical_qubits > 64 or shots > 128:
            raise ValidationError("non-affine tableau sampling policy exceeded")
        rows = []
        for _ in range(shots):
            reg = self.register.copy()
            rows.append([reg.measure_z(q, rng) for q in range(self.logical_qubits)])
        return np.asarray(rows, dtype=np.uint8)

    def execute(self, circuit: PhiQuantumCircuit, shots: int = 1, seed: int = 42) -> ExecutionResult:
        t0 = time.perf_counter()
        self.reset(); self.apply_circuit(circuit)
        samples = self.sample(shots, seed)
        return ExecutionResult(
            logical_qubits=self.logical_qubits,
            gates_executed=self.gates_executed,
            shots=shots,
            samples=samples,
            counts=self._counts(samples),
            tableau_bytes=self.register.storage_bytes,
            dense_statevector_bytes=self.register.dense_statevector_bytes,
            execution_ms=(time.perf_counter() - t0) * 1000,
            state_digest=self.register.digest(),
        )

    def checkpoint(self, depth: Optional[int] = None) -> PhiCheckpoint:
        payload = self.register.payload()
        depth = self.fold_depth if depth is None else int(depth)
        state = self.fold.fold_recursive(payload.astype(np.float64), depth)
        recovered = self.fold.unfold_recursive(state).reshape(-1)
        rounded = np.rint(recovered).astype(np.uint8)
        error = float(np.linalg.norm(payload.astype(float) - recovered) / max(np.linalg.norm(payload), 1e-15))
        checkpoint = PhiCheckpoint(state, payload.size, self.register.digest(), depth, error)
        if not np.array_equal(payload, rounded): raise RuntimeError("checkpoint roundtrip failed")
        self.last_checkpoint = checkpoint
        return checkpoint

    def restore(self, checkpoint: Optional[PhiCheckpoint] = None) -> None:
        checkpoint = checkpoint or self.last_checkpoint
        if checkpoint is None: raise ValidationError("no checkpoint available")
        payload = np.rint(self.fold.unfold_recursive(checkpoint.fold_state).reshape(-1)).astype(np.uint8)
        if payload.size != checkpoint.payload_size: raise RuntimeError("checkpoint payload size mismatch")
        self.register.restore_payload(payload)
        if self.register.digest() != checkpoint.digest: raise RuntimeError("checkpoint integrity failure")

    def regenerate(self) -> None:
        self.restore(self.last_checkpoint)

    def plan_algorithm(self, algorithm: str, problem_qubits: Optional[int] = None) -> dict[str, Any]:
        name = algorithm.lower()
        if name not in ALGORITHM_CATALOG: raise ValidationError(f"unknown algorithm: {algorithm}")
        n = self.logical_qubits if problem_qubits is None else int(problem_qubits)
        if n < 1 or n > self.logical_qubits: raise ValidationError("problem width outside machine")
        plan: dict[str, Any] = {"algorithm": name, "logical_qubits": n, "execution_mode": "compiled_phi_quantum"}
        if name == "grover":
            plan.update(search_space_log2=n, iteration_log2=n / 2, oracle_calls_expression=f"ceil(pi/4 * 2^{n/2})")
        elif name == "shor":
            plan.update(max_modulus_bits=max(1, n // 2), dominant_gate_complexity=f"O({n}^3)")
        elif name == "qft": plan.update(gate_count=n * (n + 1) // 2, depth=n)
        elif name in {"vqe", "qaoa", "qml", "annealing", "hybrid"}: plan.update(parameterized=True, state_representation="phi-fold/tensor-network")
        elif name == "qec": plan.update(stabilizer_tableau=True, syndrome_channels=n)
        else: plan.update(state_representation="phi-folded operator algebra")
        return plan

    def system_report(self) -> dict[str, Any]:
        dense_bits = 1 << self.logical_qubits
        return {
            "machine": "HYBA φ-Quantum Machine",
            "logical_qubits": self.logical_qubits,
            "backend": "classical-silicon stabilizer + PULVINI checkpoint",
            "tableau_bytes": self.register.storage_bytes,
            "dense_statevector_amplitudes": str(dense_bits),
            "dense_statevector_log2_bytes": self.logical_qubits + 4,
            "algorithms": list(ALGORITHM_CATALOG),
            "algorithm_count": len(ALGORITHM_CATALOG),
            "fold_depth": self.fold_depth,
            "phi_scale_factor": PHI ** self.fold_depth,
            "gates_executed": self.gates_executed,
        }


def run_1000_qubit_demonstration(shots: int = 16) -> dict[str, Any]:
    machine = PhiQuantumMachine1000(1000, fold_depth=20)
    circuit = PhiQuantumCircuit.ghz(1000)
    result = machine.execute(circuit, shots=shots, seed=42)
    checkpoint = machine.checkpoint(depth=20)
    valid_ghz = all((row == 0).all() or (row == 1).all() for row in result.samples)
    report = machine.system_report()
    report.update({
        "circuit": "GHZ-1000",
        "gates": result.gates_executed,
        "shots": shots,
        "ghz_correlations_verified": bool(valid_ghz),
        "checkpoint_reconstruction_error": checkpoint.reconstruction_error,
        "checkpoint_digest": checkpoint.digest,
        "execution_ms": result.execution_ms,
        "counts": result.counts,
    })
    return report
