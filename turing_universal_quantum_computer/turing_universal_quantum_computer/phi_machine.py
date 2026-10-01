"""HYBA 1,000-logical-qubit execution profile for Turing.

This module integrates the July 2026 HYBA φ-machine artifact into Turing without
creating a competing stabilizer implementation. Turing's existing
``StabilizerState`` remains the execution authority for Clifford algebra.

Claim boundary
--------------
* Clifford execution is exact on the stabilizer backend.
* PULVINI/T_phi checkpoints are exact reversible custody transforms; they are
  not represented here as compression.
* General non-Clifford algorithms are capability metadata unless another exact
  Turing backend explicitly supports the requested bounded problem.
* No speedup, advantage, supremacy, physical-QPU, or mining-consensus claim is
  implied by this profile.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import random
import re
import struct
from typing import Any

from .stabilizer import StabilizerDomainError, StabilizerState
from .turing_core import t_phi_fold, t_phi_unfold

CLIFFORD_GATES = frozenset({"h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap"})
ALGORITHM_CATALOG = (
    "grover", "shor", "qft", "vqe", "qaoa", "qml", "quantum_walk",
    "quantum_sensing", "qec", "annealing", "hybrid", "phase_estimation",
)


@dataclass(frozen=True)
class Gate:
    name: str
    qubits: tuple[int, ...]


@dataclass
class PhiQuantumCircuit:
    """Small circuit builder for the exact Clifford surface used by Turing."""

    num_qubits: int
    gates: list[Gate] = field(default_factory=list)

    def __post_init__(self) -> None:
        if int(self.num_qubits) < 1:
            raise ValueError("num_qubits must be positive")
        self.num_qubits = int(self.num_qubits)

    def _append(self, name: str, *qubits: int) -> "PhiQuantumCircuit":
        name = str(name).lower()
        if name not in CLIFFORD_GATES:
            raise StabilizerDomainError(f"{name} is outside the Clifford machine surface")
        expected = 2 if name in {"cx", "cz", "swap"} else 1
        if len(qubits) != expected:
            raise ValueError(f"{name} expects {expected} qubit(s)")
        q = tuple(int(v) for v in qubits)
        if any(v < 0 or v >= self.num_qubits for v in q):
            raise IndexError("qubit index outside circuit")
        if expected == 2 and q[0] == q[1]:
            raise ValueError(f"{name} requires distinct qubits")
        self.gates.append(Gate(name, q))
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
        for q in range(1, int(num_qubits)):
            circuit.cx(0, q)
        return circuit

    @classmethod
    def from_qasm(cls, qasm: str) -> "PhiQuantumCircuit":
        match = re.search(r"qreg\s+q\[(\d+)\]\s*;", qasm, flags=re.IGNORECASE)
        if not match:
            raise ValueError("QASM must declare qreg q[n]")
        circuit = cls(int(match.group(1)))
        for raw in qasm.splitlines():
            line = raw.strip().lower()
            if (
                not line or line.startswith("//") or line.startswith("openqasm")
                or line.startswith("include") or line.startswith("qreg")
                or line.startswith("creg") or line.startswith("measure")
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
            raise ValueError(f"unsupported QASM statement: {raw.strip()}")
        return circuit


@dataclass(frozen=True)
class PhiCheckpoint:
    folded_payload: bytes
    level_lengths: tuple[int, ...]
    logical_qubits: int
    state_digest: str
    depth: int


@dataclass(frozen=True)
class ExecutionResult:
    logical_qubits: int
    gates_executed: int
    state_digest: str
    tableau_bytes: int
    backend: str
    truth_class: str


def _tableau_payload(state: StabilizerState) -> bytes:
    """Stable exact serialization of the Turing CHP tableau."""
    n = int(state.n)
    width = (n + 7) // 8
    out = bytearray(b"TURING-CHP-1")
    out.extend(struct.pack("<II", n, width))
    for x, z, r in zip(state._x, state._z, state._r):
        out.extend(int(x).to_bytes(width, "little", signed=False))
        out.extend(int(z).to_bytes(width, "little", signed=False))
        out.append(int(bool(r)))
    return bytes(out)


def _restore_tableau(payload: bytes) -> StabilizerState:
    magic = b"TURING-CHP-1"
    if not payload.startswith(magic):
        raise ValueError("invalid Turing tableau payload")
    pos = len(magic)
    if len(payload) < pos + 8:
        raise ValueError("truncated Turing tableau payload")
    n, width = struct.unpack_from("<II", payload, pos)
    pos += 8
    expected = pos + 2 * n * (2 * width + 1)
    if n < 1 or width != (n + 7) // 8 or len(payload) != expected:
        raise ValueError("invalid Turing tableau dimensions")
    state = StabilizerState(n)
    xs: list[int] = []
    zs: list[int] = []
    rs: list[int] = []
    for _ in range(2 * n):
        xs.append(int.from_bytes(payload[pos:pos + width], "little")); pos += width
        zs.append(int.from_bytes(payload[pos:pos + width], "little")); pos += width
        r = payload[pos]; pos += 1
        if r not in (0, 1):
            raise ValueError("invalid tableau phase bit")
        rs.append(r)
    state._x = xs
    state._z = zs
    state._r = rs
    return state


def state_digest(state: StabilizerState) -> str:
    return hashlib.sha256(_tableau_payload(state)).hexdigest()


class PhiQuantumMachine1000:
    """Turing-backed HYBA φ-machine profile, defaulting to 1,000 qubits."""

    def __init__(self, logical_qubits: int = 1000, fold_depth: int = 20):
        logical_qubits = int(logical_qubits)
        fold_depth = int(fold_depth)
        if logical_qubits < 1 or logical_qubits > 100_000:
            raise ValueError("logical_qubits outside machine policy")
        if fold_depth < 0 or fold_depth > 256:
            raise ValueError("fold_depth outside checkpoint policy")
        self.logical_qubits = logical_qubits
        self.fold_depth = fold_depth
        self.register = StabilizerState(logical_qubits)
        self.gates_executed = 0
        self.last_checkpoint: PhiCheckpoint | None = None

    def reset(self) -> None:
        self.register = StabilizerState(self.logical_qubits)
        self.gates_executed = 0

    def _apply_gate(self, gate: Gate) -> None:
        method = "cnot" if gate.name == "cx" else gate.name
        fn = getattr(self.register, method, None)
        if fn is None:
            raise StabilizerDomainError(f"Turing stabilizer has no exact rule for {gate.name}")
        fn(*gate.qubits)

    def apply_circuit(self, circuit: PhiQuantumCircuit) -> None:
        if circuit.num_qubits != self.logical_qubits:
            raise ValueError("circuit width does not match machine")
        for gate in circuit.gates:
            self._apply_gate(gate)
            self.gates_executed += 1

    def execute(self, circuit: PhiQuantumCircuit) -> ExecutionResult:
        self.reset()
        self.apply_circuit(circuit)
        payload = _tableau_payload(self.register)
        return ExecutionResult(
            logical_qubits=self.logical_qubits,
            gates_executed=self.gates_executed,
            state_digest=hashlib.sha256(payload).hexdigest(),
            tableau_bytes=len(payload),
            backend="turing-stabilizer",
            truth_class="exact_clifford_tableau",
        )

    def checkpoint(self, depth: int | None = None) -> PhiCheckpoint:
        depth = self.fold_depth if depth is None else int(depth)
        if depth < 0 or depth > 256:
            raise ValueError("checkpoint depth outside policy")
        raw = _tableau_payload(self.register)
        digest = hashlib.sha256(raw).hexdigest()
        folded = raw
        level_lengths: list[int] = []
        for _ in range(depth):
            level_lengths.append(len(folded))
            folded = t_phi_fold(folded)
        checkpoint = PhiCheckpoint(
            folded_payload=folded,
            level_lengths=tuple(level_lengths),
            logical_qubits=self.logical_qubits,
            state_digest=digest,
            depth=depth,
        )
        if self._checkpoint_raw(checkpoint) != raw:
            raise RuntimeError("exact checkpoint roundtrip failed")
        self.last_checkpoint = checkpoint
        return checkpoint

    @staticmethod
    def _checkpoint_raw(checkpoint: PhiCheckpoint) -> bytes:
        raw = checkpoint.folded_payload
        for original_len in reversed(checkpoint.level_lengths):
            raw = t_phi_unfold(raw, original_len)
        return raw

    def restore(self, checkpoint: PhiCheckpoint | None = None) -> None:
        checkpoint = checkpoint or self.last_checkpoint
        if checkpoint is None:
            raise ValueError("no checkpoint available")
        if checkpoint.logical_qubits != self.logical_qubits:
            raise ValueError("checkpoint width does not match machine")
        raw = self._checkpoint_raw(checkpoint)
        if hashlib.sha256(raw).hexdigest() != checkpoint.state_digest:
            raise RuntimeError("checkpoint integrity failure")
        self.register = _restore_tableau(raw)

    def regenerate(self) -> None:
        self.restore(self.last_checkpoint)

    def _stabilizer_contains(self, target_x: int, target_z: int,
                             target_r: int = 0) -> bool:
        n = self.logical_qubits
        vectors = [int(self.register._x[n + i]) | (int(self.register._z[n + i]) << n)
                   for i in range(n)]
        pivots: dict[int, tuple[int, int]] = {}
        for i, vector in enumerate(vectors):
            v, coeff = vector, 1 << i
            while v:
                bit = v.bit_length() - 1
                pivot = pivots.get(bit)
                if pivot is None:
                    pivots[bit] = (v, coeff)
                    break
                v ^= pivot[0]
                coeff ^= pivot[1]
        target = int(target_x) | (int(target_z) << n)
        coeff, v = 0, target
        while v:
            bit = v.bit_length() - 1
            pivot = pivots.get(bit)
            if pivot is None:
                return False
            v ^= pivot[0]
            coeff ^= pivot[1]
        sx = sz = sr = 0
        for i in range(n):
            if not ((coeff >> i) & 1):
                continue
            xi = int(self.register._x[n + i])
            zi = int(self.register._z[n + i])
            ri = int(bool(self.register._r[n + i]))
            g = StabilizerState._gsum(xi, zi, sx, sz)
            phase = (2 * ri + 2 * sr + g) % 4
            if phase not in (0, 2):
                return False
            sr = 1 if phase == 2 else 0
            sx ^= xi
            sz ^= zi
        return sx == int(target_x) and sz == int(target_z) and sr == int(bool(target_r))

    def verifies_ghz_stabilizer_group(self) -> bool:
        """Verify +X^\\otimes n and all positive Z_i Z_(i+1) generators."""
        n = self.logical_qubits
        if not self._stabilizer_contains((1 << n) - 1, 0, 0):
            return False
        return all(self._stabilizer_contains(0, (1 << i) | (1 << (i + 1)), 0)
                   for i in range(n - 1))

    def plan_algorithm(self, algorithm: str,
                       problem_qubits: int | None = None) -> dict[str, Any]:
        name = str(algorithm).lower()
        if name not in ALGORITHM_CATALOG:
            raise ValueError(f"unknown algorithm: {algorithm}")
        n = self.logical_qubits if problem_qubits is None else int(problem_qubits)
        if n < 1 or n > self.logical_qubits:
            raise ValueError("problem width outside machine")
        status: dict[str, tuple[str, str]] = {
            "qec": ("executable_clifford", "turing-stabilizer"),
            "quantum_walk": ("exact_other_turing_backend", "closed_form_or_sparse"),
            "annealing": ("exact_other_turing_backend", "free_fermion_closed_form"),
            "grover": ("bounded_exact_other_turing_backend", "sparse_exact_only"),
            "shor": ("restricted_non_clifford", "not_executable_on_stabilizer"),
            "qft": ("planned_non_clifford_general", "not_executable_on_stabilizer"),
            "vqe": ("planned_non_clifford_general", "not_executable_on_stabilizer"),
            "qaoa": ("planned_non_clifford_general", "not_executable_on_stabilizer"),
            "qml": ("planned_non_clifford_general", "not_executable_on_stabilizer"),
            "quantum_sensing": ("planned_non_clifford_general", "not_executable_on_stabilizer"),
            "hybrid": ("planned_composite", "requires_explicit_backend_routing"),
            "phase_estimation": ("planned_non_clifford_general", "not_executable_on_stabilizer"),
        }
        execution_status, backend = status[name]
        plan: dict[str, Any] = {
            "algorithm": name,
            "logical_qubits": n,
            "execution_status": execution_status,
            "backend": backend,
            "clifford_machine_authority": name == "qec",
        }
        if name == "grover":
            plan.update(search_space_log2=n,
                        oracle_calls_expression=f"ceil(pi/4 * 2^{n/2})")
        elif name == "shor":
            plan.update(max_planned_modulus_bits=max(1, n // 2), executable=False)
        elif name == "qft":
            plan.update(planned_gate_count=n * (n + 1) // 2, executable=False)
        elif name == "qec":
            plan.update(stabilizer_tableau=True, syndrome_channels=n, executable=True)
        return plan

    def system_report(self) -> dict[str, Any]:
        payload = _tableau_payload(self.register)
        return {
            "machine": "HYBA φ-machine profile on Turing",
            "logical_qubits": self.logical_qubits,
            "backend": "Turing exact Clifford stabilizer",
            "truth_class": "exact_clifford_tableau",
            "materialized_dense_state": False,
            "dense_statevector_amplitudes": f"2^{self.logical_qubits}",
            "tableau_serialized_bytes": len(payload),
            "checkpoint_depth": self.fold_depth,
            "checkpoint_transform": "exact reversible T_phi custody",
            "checkpoint_compression_claim": False,
            "speedup_claim": False,
            "algorithm_catalog": [self.plan_algorithm(name) for name in ALGORITHM_CATALOG],
        }


def seeded_clifford_digest(n_qubits: int = 64, gates: int = 256,
                            seed: int = 20260802) -> str:
    rng = random.Random(seed)
    circuit = PhiQuantumCircuit(n_qubits)
    singles = ("h", "s", "sdg", "x", "y", "z")
    for _ in range(int(gates)):
        if rng.random() < 0.35 and n_qubits > 1:
            a = rng.randrange(n_qubits)
            b = rng.randrange(n_qubits - 1)
            if b >= a:
                b += 1
            circuit._append(rng.choice(("cx", "cz", "swap")), a, b)
        else:
            circuit._append(rng.choice(singles), rng.randrange(n_qubits))
    machine = PhiQuantumMachine1000(n_qubits, fold_depth=20)
    result = machine.execute(circuit)
    checkpoint = machine.checkpoint(20)
    before = result.state_digest
    machine.reset()
    machine.restore(checkpoint)
    after = state_digest(machine.register)
    if before != after:
        raise RuntimeError("seeded Clifford checkpoint reproduction failed")
    return before


def run_1000_qubit_verification() -> dict[str, Any]:
    """Corrected 1,000-qubit evidence gate; no weak GHZ shot-correlation proof."""
    machine = PhiQuantumMachine1000(1000, fold_depth=20)
    result = machine.execute(PhiQuantumCircuit.ghz(1000))
    group_ok = machine.verifies_ghz_stabilizer_group()
    checkpoint = machine.checkpoint(20)
    machine.reset()
    machine.restore(checkpoint)
    restored_digest = state_digest(machine.register)
    return {
        "logical_qubits": 1000,
        "gates_executed": result.gates_executed,
        "backend": result.backend,
        "truth_class": result.truth_class,
        "direct_stabilizer_group_equality": group_ok,
        "state_digest": result.state_digest,
        "restored_digest": restored_digest,
        "checkpoint_depth": checkpoint.depth,
        "checkpoint_exact": restored_digest == result.state_digest,
        "ghz_shot_correlation_used_as_evidence": False,
        "speedup_claim": False,
    }


__all__ = [
    "ALGORITHM_CATALOG", "CLIFFORD_GATES", "ExecutionResult", "Gate",
    "PhiCheckpoint", "PhiQuantumCircuit", "PhiQuantumMachine1000",
    "run_1000_qubit_verification", "seeded_clifford_digest", "state_digest",
]
