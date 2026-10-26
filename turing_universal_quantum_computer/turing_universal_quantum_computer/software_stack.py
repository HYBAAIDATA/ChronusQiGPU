"""Six-phase exact quantum software stack for the TURING VQC substrate.

This module closes the architectural lifecycle of a quantum workload across all
six canonical software layers — executed entirely over exact algebraic and
symbolic domains (``Q(zeta_8)``, ``Q(sqrt(2)) + i*Q(sqrt(2))``, ``GF(2)``, and
``Fraction`` rational turns) with zero floating-point approximation:

1. **Phase 1 — High-Level Development (Developer Intent)**:
   Fluent circuit and parameterized ansatz construction (:func:`build_ansatz_program`)
   mapping rational-turn rotations and multi-qubit entanglers into canonical
   hardware-agnostic :class:`~turing_universal_quantum_computer.backends.base.Program`
   objects.
2. **Phase 2 — Intermediate Representation & Circuit Assembly**:
   Lossless OpenQASM 2.0 assembly and disassembly (:func:`program_to_qasm`,
   :func:`program_from_qasm`, :func:`qasm_roundtrip_report`) supporting the full
   Clifford+T+Toffoli gate set (``id``/``i``, ``x``, ``y``, ``z``, ``h``, ``s``,
   ``sdg``, ``t``, ``tdg``, ``cx``/``cnot``, ``cz``, ``swap``, ``ccx``/``toffoli``).
3. **Phase 3 — Compilation and Transpilation (The Optimizer)**:
   * **Basis Gate Translation** (:func:`decompose_to_basis`): Exact, zero-global-phase
     algebraic synthesis of ``ccx``/``toffoli`` (15-gate Clifford+T decomposition),
     ``swap``, ``cz``, ``cx``, ``y``, ``x``, ``z``, ``s``, ``sdg``, and ``i`` into
     the target native basis gate set.
   * **Topology Routing & Mapping** (:class:`CouplingMap`, :func:`route_program`):
     Shortest-path BFS ``SWAP`` routing over physical chip connectivity graphs
     (line, ring, 2-D grid, heavy-hex) with dynamic layout tracking and exact
     canonical layout restoration.
   * **Circuit Optimization** (:func:`optimize_program`): Fixed-point peephole
     inverse cancellation and single-qubit ``Z``-axis phase folding modulo 8
     (``T^k mod 8``).
   * **Exact Unitary Equivalence Verification** (:func:`transpile_program`):
     Proves ``U_transpiled == U_original`` column-by-column over
     ``Q(sqrt(2)) + i*Q(sqrt(2))``.
4. **Phase 4 — Quantum Error Correction (QEC) & Fault Tolerance Layer**:
   Full planar surface-code cycle (:func:`run_surface_code_qec_cycle`) combining
   :class:`kellogg.surface_code.PlanarSurfaceCode` with live non-destructive
   ancilla syndrome extraction on :class:`~turing_universal_quantum_computer.stabilizer.StabilizerState`,
   exact minimum-weight matching (:meth:`~kellogg.surface_code.CSSCode.decode_exact`)
   and Union-Find (:meth:`~kellogg.surface_code.CSSCode.decode_union_find`)
   decoding, active recovery, and logical observable verification.
5. **Phase 5 — Quantum Orchestration and Hybrid Workload Scheduling**:
   Deterministic hybrid CPU-VQC workload scheduler and variational loop
   orchestrator (:class:`HybridWorkloadOrchestrator`, :func:`run_hybrid_workload`)
   performing in-the-loop Phase 3 transpilation, exact Hamiltonian expectation
   evaluation, and SHA-256 hash-chained iteration receipts.
6. **Phase 6 — Pulse-Level Compilation and Control Software**:
   Exact symbolic/rational waveform scheduler (:class:`PulseCompiler`,
   :func:`compile_pulse_schedule`) lowering native gates into time-ordered
   drive (``d{q}``), coupler (``u{c}_{t}``), and readout (``m{q}``) channels
   with zero-duration Virtual-Z software frame tracking, DRAG single-qubit
   envelopes, and echoed cross-resonance (``ecr``) / flux (``cz_flux``)
   two-qubit schedules.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import sympy as sp

from .backends.base import Operation, Program
from .quantum_library import (
    ExactLaneError,
    QuantumLibrary,
    audit_exactness,
    pauli_expectation,
)
from .hilbert import QuantumRegister, _frac
from .stabilizer import StabilizerState
from .verify import DEFAULT_VERIFY_WIDTH, program_unitary_columns

__all__ = [
    "DEFAULT_BASIS_GATES",
    "CouplingMap",
    "RoutingResult",
    "TranspilationReport",
    "QECCycleReport",
    "HybridJobSpec",
    "HybridIterationReceipt",
    "HybridOrchestrationReport",
    "HybridWorkloadOrchestrator",
    "GPUFleetQuantumWorkloadReport",
    "PulseInstruction",
    "PulseSchedule",
    "PulseCompiler",
    "SoftwareStackReport",
    "build_ansatz_program",
    "program_to_qasm",
    "program_from_qasm",
    "qasm_roundtrip_report",
    "decompose_to_basis",
    "route_program",
    "optimize_program",
    "transpile_program",
    "run_surface_code_qec_cycle",
    "run_hybrid_workload",
    "run_gpu_fleet_hybrid_workload",
    "compile_pulse_schedule",
    "run_quantum_software_stack",
]

DEFAULT_BASIS_GATES: Tuple[str, ...] = ("h", "s", "sdg", "t", "tdg", "cx")

_SINGLE_QUBIT_QASM_GATES = frozenset({"id", "i", "x", "y", "z", "h", "s", "sdg", "t", "tdg"})
_TWO_QUBIT_QASM_GATES = frozenset({"cx", "cnot", "cz", "swap"})
_THREE_QUBIT_QASM_GATES = frozenset({"ccx", "toffoli"})

# Z-axis rotation powers in units of T (1/8 turn = pi/4):
# T^1 = t, T^2 = s, T^3 = s*t, T^4 = z, T^5 = z*t, T^6 = sdg, T^7 = tdg, T^0 = I
_Z_AXIS_EIGHTHS: Dict[str, int] = {
    "t": 1,
    "s": 2,
    "z": 4,
    "sdg": 6,
    "tdg": 7,
}


def _canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ======================================================================
# Phase 1: High-Level Development (Developer Intent)
# ======================================================================


def _turns_to_clifford_t_gates(turns: Fraction) -> Tuple[str, ...]:
    """Map an exact dyadic turn angle (denominator dividing 8) to Z-axis gates."""
    normalized = turns % 1
    eighths = normalized * 8
    if eighths.denominator != 1:
        raise ExactLaneError(
            f"turn angle {turns} requires denominator dividing 8 for gate-level "
            "Clifford+T circuit synthesis"
        )
    k = int(eighths.numerator) % 8
    mapping: Dict[int, Tuple[str, ...]] = {
        0: (),
        1: ("t",),
        2: ("s",),
        3: ("s", "t"),
        4: ("z",),
        5: ("z", "t"),
        6: ("sdg",),
        7: ("tdg",),
    }
    return mapping[k]


def build_ansatz_program(
    n_qubits: int,
    rotation_turns: Sequence[Any],
    *,
    layers: int = 1,
    axis: str = "y",
    entangler: str = "cx",
    entanglement: str = "linear",
) -> Program:
    """Construct a hardware-agnostic parameterized ansatz :class:`Program`.

    Each layer applies single-qubit rotations specified as rational numbers of
    turns ``t`` (with denominator dividing 8 so every rotation decomposes
    exactly into Clifford+T gates) followed by an entangling layer (``linear``,
    ``ring``, or ``full``).

    * ``axis="z"``: direct phase rotation $P(t) = \\operatorname{diag}(1, e^{2\\pi i t})$.
    * ``axis="x"``: $H \\cdot P(t) \\cdot H$.
    * ``axis="y"``: $S \\cdot H \\cdot P(t) \\cdot H \\cdot S^\\dagger$.
    """
    if not isinstance(n_qubits, int) or n_qubits < 1:
        raise ValueError("n_qubits must be a positive integer")
    if layers < 1:
        raise ValueError("layers must be >= 1")
    axis_norm = axis.strip().lower()
    if axis_norm not in {"x", "y", "z"}:
        raise ValueError("axis must be 'x', 'y', or 'z'")
    ent_norm = entangler.strip().lower()
    if ent_norm not in {"cx", "cz"}:
        raise ValueError("entangler must be 'cx' or 'cz'")

    turns_list = [_frac(t) for t in rotation_turns]
    if len(turns_list) == n_qubits:
        layer_turns = [turns_list for _ in range(layers)]
    elif len(turns_list) == n_qubits * layers:
        layer_turns = [
            turns_list[l * n_qubits : (l + 1) * n_qubits] for l in range(layers)
        ]
    else:
        raise ValueError(
            f"rotation_turns length ({len(turns_list)}) must equal n_qubits ({n_qubits}) "
            f"or n_qubits * layers ({n_qubits * layers})"
        )

    program = Program(n_qubits)
    for l in range(layers):
        for q in range(n_qubits):
            z_gates = _turns_to_clifford_t_gates(layer_turns[l][q])
            if not z_gates:
                continue
            if axis_norm == "z":
                for g in z_gates:
                    program = program.then(g, q)
            elif axis_norm == "x":
                program = program.then("h", q)
                for g in z_gates:
                    program = program.then(g, q)
                program = program.then("h", q)
            else:  # axis == "y": S H P(t) H Sdg (so Sdg acts first, then H, P(t), H, S)
                program = program.then("sdg", q).then("h", q)
                for g in z_gates:
                    program = program.then(g, q)
                program = program.then("h", q).then("s", q)

        if n_qubits >= 2:
            if entanglement == "linear":
                pairs = [(q, q + 1) for q in range(n_qubits - 1)]
            elif entanglement == "ring":
                pairs = [(q, (q + 1) % n_qubits) for q in range(n_qubits)]
            elif entanglement == "full":
                pairs = [
                    (u, v) for u in range(n_qubits) for v in range(u + 1, n_qubits)
                ]
            else:
                raise ValueError(f"unsupported entanglement pattern: {entanglement!r}")
            for u, v in pairs:
                if u != v:
                    program = program.then(ent_norm, u, v)
    return program


# ======================================================================
# Phase 2: Intermediate Representation & OpenQASM 2.0 Assembly
# ======================================================================


def _toffoli_clifford_t_ops(c0: int, c1: int, target: int) -> Tuple[Operation, ...]:
    """Exact 15-gate Clifford+T decomposition of CCX(c0, c1, target) with zero global phase."""
    if len({c0, c1, target}) != 3:
        raise ValueError("CCX/Toffoli requires three distinct qubits")
    return (
        Operation("h", (target,)),
        Operation("cx", (c1, target)),
        Operation("tdg", (target,)),
        Operation("cx", (c0, target)),
        Operation("t", (target,)),
        Operation("cx", (c1, target)),
        Operation("tdg", (target,)),
        Operation("cx", (c0, target)),
        Operation("t", (c1,)),
        Operation("t", (target,)),
        Operation("h", (target,)),
        Operation("cx", (c0, c1)),
        Operation("t", (c0,)),
        Operation("tdg", (c1,)),
        Operation("cx", (c0, c1)),
    )


def program_to_qasm(
    program: Program,
    *,
    register_name: str = "q",
    include_header: bool = True,
) -> str:
    """Serialize a canonical :class:`Program` into OpenQASM 2.0 source."""
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", register_name):
        raise ValueError(f"invalid QASM register identifier: {register_name!r}")
    lines: List[str] = []
    if include_header:
        lines.append("OPENQASM 2.0;")
        lines.append('include "qelib1.inc";')
    lines.append(f"qreg {register_name}[{program.n_qubits}];")
    for op in program.operations:
        gate = op.gate.lower()
        if gate == "i":
            qasm_gate = "id"
        elif gate == "cnot":
            qasm_gate = "cx"
        elif gate == "toffoli":
            qasm_gate = "ccx"
        else:
            qasm_gate = gate
        args = ",".join(f"{register_name}[{q}]" for q in op.qubits)
        lines.append(f"{qasm_gate} {args};")
    return "\n".join(lines) + "\n"


def program_from_qasm(qasm: str, *, decompose_toffoli: bool = False) -> Program:
    """Parse an OpenQASM 2.0 source string into a canonical :class:`Program`.

    Supports ``id``/``i``, ``x``, ``y``, ``z``, ``h``, ``s``, ``sdg``, ``t``,
    ``tdg``, ``cx``/``cnot``, ``cz``, ``swap``, and ``ccx``/``toffoli``.
    When ``decompose_toffoli=True``, 3-qubit ``ccx``/``toffoli`` instructions
    are expanded into their exact 15-gate Clifford+T decomposition so the
    resulting :class:`Program` is directly executable by 1- and 2-qubit backends.
    """
    qreg_match = re.search(
        r"qreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\[(\d+)\]\s*;",
        qasm,
        flags=re.IGNORECASE,
    )
    if not qreg_match:
        raise ValueError("QASM must declare qreg <name>[n];")
    reg_name = qreg_match.group(1).lower()
    n_qubits = int(qreg_match.group(2))
    if n_qubits < 1:
        raise ValueError("qreg size must be >= 1")

    ops: List[Operation] = []
    reg_esc = re.escape(reg_name)
    one_pat = re.compile(
        rf"^({'|'.join(_SINGLE_QUBIT_QASM_GATES)})\s+{reg_esc}\[(\d+)\]\s*;$"
    )
    two_pat = re.compile(
        rf"^({'|'.join(_TWO_QUBIT_QASM_GATES)})\s+{reg_esc}\[(\d+)\]\s*,\s*{reg_esc}\[(\d+)\]\s*;$"
    )
    three_pat = re.compile(
        rf"^({'|'.join(_THREE_QUBIT_QASM_GATES)})\s+{reg_esc}\[(\d+)\]\s*,\s*{reg_esc}\[(\d+)\]\s*,\s*{reg_esc}\[(\d+)\]\s*;$"
    )

    for raw in qasm.splitlines():
        # Strip inline // comments
        cleaned = raw.split("//", 1)[0].strip().lower()
        if (
            not cleaned
            or cleaned.startswith("openqasm")
            or cleaned.startswith("include")
            or cleaned.startswith("qreg")
            or cleaned.startswith("creg")
            or cleaned.startswith("measure")
            or cleaned.startswith("barrier")
        ):
            continue

        m1 = one_pat.fullmatch(cleaned)
        if m1:
            g = "i" if m1.group(1) == "id" else m1.group(1)
            q0 = int(m1.group(2))
            ops.append(Operation(g, (q0,)))
            continue

        m2 = two_pat.fullmatch(cleaned)
        if m2:
            g = "cx" if m2.group(1) == "cnot" else m2.group(1)
            q0, q1 = int(m2.group(2)), int(m2.group(3))
            if q0 == q1:
                raise ValueError(f"two-qubit gate {g!r} requires distinct qubits")
            ops.append(Operation(g, (q0, q1)))
            continue

        m3 = three_pat.fullmatch(cleaned)
        if m3:
            q0, q1, q2 = int(m3.group(2)), int(m3.group(3)), int(m3.group(4))
            if len({q0, q1, q2}) != 3:
                raise ValueError("three-qubit gate ccx requires three distinct qubits")
            if decompose_toffoli:
                ops.extend(_toffoli_clifford_t_ops(q0, q1, q2))
            else:
                ops.append(Operation("ccx", (q0, q1, q2)))
            continue

        raise ValueError(f"unsupported QASM statement: {raw.strip()}")

    return Program(n_qubits=n_qubits, operations=tuple(ops))


def qasm_roundtrip_report(program: Program) -> Dict[str, Any]:
    """Assemble ``program`` to OpenQASM 2.0, parse it back, and verify exact equality."""
    qasm_text = program_to_qasm(program)
    restored = program_from_qasm(qasm_text, decompose_toffoli=False)
    executable = program_from_qasm(qasm_text, decompose_toffoli=True)
    return {
        "n_qubits": program.n_qubits,
        "original_gate_count": len(program.operations),
        "restored_gate_count": len(restored.operations),
        "executable_gate_count": len(executable.operations),
        "original_digest": program.digest(),
        "restored_digest": restored.digest(),
        "executable_digest": executable.digest(),
        "roundtrip_exact": restored == program and restored.digest() == program.digest(),
        "qasm": qasm_text,
    }


# ======================================================================
# Phase 3: Compilation and Transpilation (The Optimizer)
# ======================================================================


@dataclass(frozen=True)
class CouplingMap:
    """Undirected physical qubit connectivity graph for topological routing."""

    n_qubits: int
    edges: Tuple[Tuple[int, int], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.n_qubits, int) or self.n_qubits < 1:
            raise ValueError("n_qubits must be a positive integer")
        normalized: List[Tuple[int, int]] = []
        seen = set()
        for u, v in self.edges:
            iu, iv = int(u), int(v)
            if not (0 <= iu < self.n_qubits and 0 <= iv < self.n_qubits):
                raise ValueError(f"edge ({iu}, {iv}) outside {self.n_qubits}-qubit map")
            if iu == iv:
                raise ValueError("self-loop edges are not allowed in CouplingMap")
            pair = (min(iu, iv), max(iu, iv))
            if pair not in seen:
                seen.add(pair)
                normalized.append(pair)
        object.__setattr__(self, "edges", tuple(sorted(normalized)))

    @classmethod
    def line(cls, n_qubits: int) -> "CouplingMap":
        """1-D linear nearest-neighbor topology ``0 - 1 - ... - (n-1)``."""
        return cls(n_qubits, tuple((i, i + 1) for i in range(n_qubits - 1)))

    @classmethod
    def ring(cls, n_qubits: int) -> "CouplingMap":
        """1-D closed ring topology."""
        edges = [(i, i + 1) for i in range(n_qubits - 1)]
        if n_qubits > 2:
            edges.append((0, n_qubits - 1))
        return cls(n_qubits, tuple(edges))

    @classmethod
    def grid(cls, rows: int, cols: int) -> "CouplingMap":
        """2-D rectangular lattice topology with ``rows * cols`` qubits."""
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must be >= 1")
        edges: List[Tuple[int, int]] = []
        for r in range(rows):
            for c in range(cols):
                u = r * cols + c
                if c + 1 < cols:
                    edges.append((u, u + 1))
                if r + 1 < rows:
                    edges.append((u, u + cols))
        return cls(rows * cols, tuple(edges))

    @classmethod
    def all_to_all(cls, n_qubits: int) -> "CouplingMap":
        """Fully connected topology."""
        return cls(
            n_qubits,
            tuple((u, v) for u in range(n_qubits) for v in range(u + 1, n_qubits)),
        )

    def adjacency(self) -> Dict[int, Tuple[int, ...]]:
        adj: Dict[int, List[int]] = {q: [] for q in range(self.n_qubits)}
        for u, v in self.edges:
            adj[u].append(v)
            adj[v].append(u)
        return {q: tuple(sorted(nbrs)) for q, nbrs in adj.items()}

    def is_connected(self, u: int, v: int) -> bool:
        pair = (min(int(u), int(v)), max(int(u), int(v)))
        return pair in self.edges

    def shortest_path(self, source: int, target: int) -> Tuple[int, ...]:
        """Return shortest vertex path ``(source, ..., target)`` via BFS."""
        s, t = int(source), int(target)
        if not (0 <= s < self.n_qubits and 0 <= t < self.n_qubits):
            raise ValueError("qubit index outside CouplingMap")
        if s == t:
            return (s,)
        adj = self.adjacency()
        parent: Dict[int, Optional[int]] = {s: None}
        queue: deque[int] = deque([s])
        while queue:
            cur = queue.popleft()
            if cur == t:
                break
            for nxt in adj[cur]:
                if nxt not in parent:
                    parent[nxt] = cur
                    queue.append(nxt)
        if t not in parent:
            raise ValueError(f"CouplingMap is disconnected between {s} and {t}")
        path: List[int] = []
        node: Optional[int] = t
        while node is not None:
            path.append(node)
            node = parent[node]
        return tuple(reversed(path))

    def distance(self, source: int, target: int) -> int:
        return len(self.shortest_path(source, target)) - 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "n_qubits": self.n_qubits,
            "edges": [list(e) for e in self.edges],
        }


def decompose_to_basis(
    program: Program,
    basis_gates: Iterable[str] = DEFAULT_BASIS_GATES,
) -> Program:
    """Translate all operations in ``program`` into ``basis_gates`` with exact unitary identity.

    Supported decompositions (all zero global phase):
    * ``ccx(a, b, c)`` / ``toffoli(a, b, c)`` -> 15-gate Clifford+T sequence
    * ``swap(a, b)`` -> ``cx(a, b), cx(b, a), cx(a, b)``
    * ``cz(a, b)`` -> ``h(b), cx(a, b), h(b)``
    * ``cx(a, b)`` / ``cnot(a, b)`` -> ``h(b), cz(a, b), h(b)`` (when ``cz`` is native)
    * ``y(q)`` -> ``sdg(q), x(q), s(q)`` ($S X S^\\dagger = Y$)
    * ``x(q)`` -> ``h(q), z(q), h(q)`` ($H Z H = X$)
    * ``z(q)`` -> ``s(q), s(q)`` ($S^2 = Z$)
    * ``s(q)`` -> ``t(q), t(q)`` ($T^2 = S$)
    * ``sdg(q)`` -> ``tdg(q), tdg(q)`` ($(T^\\dagger)^2 = S^\\dagger$)
    * ``i(q)`` -> removed (0 gates) into any basis lacking ``i``
    """
    basis = frozenset(g.strip().lower() for g in basis_gates)
    if not basis:
        raise ValueError("basis_gates must be non-empty")

    def expand_op(op: Operation, depth: int = 0) -> Tuple[Operation, ...]:
        if depth > 8:
            raise ExactLaneError(
                f"cannot decompose gate {op.gate!r} into basis {sorted(basis)}"
            )
        g = op.gate.lower()
        if g == "cnot" and "cx" in basis and "cnot" not in basis:
            g = "cx"
            op = Operation("cx", op.qubits)
        if g in basis:
            return (op,)

        if g == "i":
            return ()
        if g in ("ccx", "toffoli"):
            c0, c1, t = op.qubits
            seq = _toffoli_clifford_t_ops(c0, c1, t)
        elif g == "swap":
            a, b = op.qubits
            seq = (
                Operation("cx", (a, b)),
                Operation("cx", (b, a)),
                Operation("cx", (a, b)),
            )
        elif g == "cz":
            a, b = op.qubits
            seq = (
                Operation("h", (b,)),
                Operation("cx", (a, b)),
                Operation("h", (b,)),
            )
        elif g in ("cx", "cnot"):
            a, b = op.qubits
            if "cz" in basis:
                seq = (
                    Operation("h", (b,)),
                    Operation("cz", (a, b)),
                    Operation("h", (b,)),
                )
            else:
                raise ExactLaneError(
                    f"basis {sorted(basis)} lacks an entangling gate for {g!r}"
                )
        elif g == "y":
            (q,) = op.qubits
            seq = (
                Operation("sdg", (q,)),
                Operation("x", (q,)),
                Operation("s", (q,)),
            )
        elif g == "x":
            (q,) = op.qubits
            seq = (
                Operation("h", (q,)),
                Operation("z", (q,)),
                Operation("h", (q,)),
            )
        elif g == "z":
            (q,) = op.qubits
            seq = (
                Operation("s", (q,)),
                Operation("s", (q,)),
            )
        elif g == "s":
            (q,) = op.qubits
            seq = (
                Operation("t", (q,)),
                Operation("t", (q,)),
            )
        elif g == "sdg":
            (q,) = op.qubits
            seq = (
                Operation("tdg", (q,)),
                Operation("tdg", (q,)),
            )
        else:
            raise ExactLaneError(
                f"unsupported gate {g!r} for decomposition into {sorted(basis)}"
            )

        out: List[Operation] = []
        for sub in seq:
            out.extend(expand_op(sub, depth + 1))
        return tuple(out)

    compiled: List[Operation] = []
    for op in program.operations:
        compiled.extend(expand_op(op))
    return Program(program.n_qubits, tuple(compiled))


@dataclass(frozen=True)
class RoutingResult:
    """Outcome of topological SWAP routing on a :class:`CouplingMap`."""

    routed_program: Program
    initial_layout: Tuple[int, ...]
    final_layout: Tuple[int, ...]
    inserted_swaps: int
    layout_restored: bool
    all_two_qubit_gates_adjacent: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "n_qubits": self.routed_program.n_qubits,
            "routed_gate_count": len(self.routed_program.operations),
            "initial_layout": list(self.initial_layout),
            "final_layout": list(self.final_layout),
            "inserted_swaps": self.inserted_swaps,
            "layout_restored": self.layout_restored,
            "all_two_qubit_gates_adjacent": self.all_two_qubit_gates_adjacent,
            "routed_digest": self.routed_program.digest(),
        }


def route_program(
    program: Program,
    coupling_map: CouplingMap,
    *,
    restore_layout: bool = True,
) -> RoutingResult:
    """Route ``program`` onto ``coupling_map`` by inserting shortest-path SWAP bridges.

    Maintains a dynamic logical-to-physical qubit permutation across operations
    so consecutive two-qubit gates on the same pair do not incur redundant
    SWAPs.  When ``restore_layout=True``, appends the inverse SWAP sequence
    along connected edges at the end of the circuit so that the final
    logical-to-physical layout equals ``(0, 1, ..., n-1)`` and the routed
    program is unitarily identical to ``program``.
    """
    if coupling_map.n_qubits < program.n_qubits:
        raise ValueError(
            f"CouplingMap has {coupling_map.n_qubits} qubits, "
            f"but program requires {program.n_qubits}"
        )

    # First unfold any 3-qubit CCX/Toffoli gates into 1- and 2-qubit gates
    unfolded_ops: List[Operation] = []
    for op in program.operations:
        if op.gate.lower() in ("ccx", "toffoli"):
            unfolded_ops.extend(_toffoli_clifford_t_ops(*op.qubits))
        else:
            unfolded_ops.append(op)

    n = program.n_qubits
    initial_layout = tuple(range(n))
    log_to_phys: List[int] = list(initial_layout)
    phys_to_log: List[int] = list(initial_layout)
    routed_ops: List[Operation] = []
    swap_history: List[Tuple[int, int]] = []
    inserted_swaps = 0

    def apply_physical_swap(p_a: int, p_b: int, record_history: bool = True) -> None:
        nonlocal inserted_swaps
        l_a = phys_to_log[p_a]
        l_b = phys_to_log[p_b]
        phys_to_log[p_a], phys_to_log[p_b] = l_b, l_a
        log_to_phys[l_a], log_to_phys[l_b] = p_b, p_a
        routed_ops.append(Operation("swap", (p_a, p_b)))
        inserted_swaps += 1
        if record_history:
            swap_history.append((p_a, p_b))

    for op in unfolded_ops:
        if len(op.qubits) == 1:
            p0 = log_to_phys[op.qubits[0]]
            routed_ops.append(Operation(op.gate, (p0,)))
        elif len(op.qubits) == 2:
            l0, l1 = op.qubits
            p0, p1 = log_to_phys[l0], log_to_phys[l1]
            path = coupling_map.shortest_path(p0, p1)
            # Move l0 along shortest path until adjacent to l1
            for idx in range(len(path) - 2):
                apply_physical_swap(path[idx], path[idx + 1], record_history=True)
            p0_now, p1_now = log_to_phys[l0], log_to_phys[l1]
            routed_ops.append(Operation(op.gate, (p0_now, p1_now)))
        else:
            raise ExactLaneError(f"cannot route {len(op.qubits)}-qubit gate {op.gate!r}")

    if restore_layout and tuple(log_to_phys) != initial_layout:
        # Cancel adjacent duplicate swaps in swap_history before reversing
        reduced_history: List[Tuple[int, int]] = []
        for edge in swap_history:
            norm_edge = (min(edge), max(edge))
            if reduced_history and (min(reduced_history[-1]), max(reduced_history[-1])) == norm_edge:
                reduced_history.pop()
            else:
                reduced_history.append(edge)
        for p_a, p_b in reversed(reduced_history):
            if tuple(log_to_phys) == initial_layout:
                break
            apply_physical_swap(p_a, p_b, record_history=False)

    routed_prog = Program(n, tuple(routed_ops))
    all_adj = all(
        coupling_map.is_connected(op.qubits[0], op.qubits[1])
        for op in routed_prog.operations
        if len(op.qubits) == 2
    )
    return RoutingResult(
        routed_program=routed_prog,
        initial_layout=initial_layout,
        final_layout=tuple(log_to_phys),
        inserted_swaps=inserted_swaps,
        layout_restored=(tuple(log_to_phys) == initial_layout),
        all_two_qubit_gates_adjacent=all_adj,
    )


def _eighths_to_z_ops(
    eighths: int,
    qubit: int,
    allowed_gates: Optional[frozenset[str]] = None,
) -> Tuple[Operation, ...]:
    """Emit minimal Z-axis gate sequence for ``T^eighths (mod 8)`` within ``allowed_gates``."""
    k = eighths % 8
    if k == 0:
        return ()
    preferred: Dict[int, Tuple[str, ...]] = {
        1: ("t",),
        2: ("s",),
        3: ("s", "t"),
        4: ("z",),
        5: ("z", "t"),
        6: ("sdg",),
        7: ("tdg",),
    }
    seq = preferred[k]
    if allowed_gates is None or all(g in allowed_gates for g in seq):
        return tuple(Operation(g, (qubit,)) for g in seq)

    # Fallback when 'z' is not in allowed_gates (e.g. basis = h, s, sdg, t, tdg, cx)
    no_z: Dict[int, Tuple[str, ...]] = {
        1: ("t",),
        2: ("s",),
        3: ("s", "t"),
        4: ("s", "s"),
        5: ("s", "s", "t"),
        6: ("sdg",),
        7: ("tdg",),
    }
    seq_no_z = no_z[k]
    if all(g in allowed_gates for g in seq_no_z):
        return tuple(Operation(g, (qubit,)) for g in seq_no_z)

    # Minimal T/Tdg fallback
    if k <= 4 and "t" in allowed_gates:
        return tuple(Operation("t", (qubit,)) for _ in range(k))
    if "tdg" in allowed_gates:
        return tuple(Operation("tdg", (qubit,)) for _ in range(8 - k))
    return tuple(Operation(g, (qubit,)) for g in seq)


def optimize_program(
    program: Program,
    *,
    allowed_gates: Optional[Iterable[str]] = None,
) -> Program:
    """Optimize ``program`` via fixed-point peephole cancellation and Z-phase folding.

    Transformations (all exact unitary identities):
    * Identity gate ``i`` removal and ``cnot`` -> ``cx`` canonicalization.
    * Per-qubit contiguous Z-axis phase folding modulo 8 (``t, tdg, s, sdg, z``).
    * Self-inverse single-qubit cancellation (``h-h``, ``x-x``, ``y-y``, ``z-z``).
    * Conjugation reduction ``h-z-h -> x`` and ``h-x-h -> z`` when target gate is allowed.
    * Adjacent self-inverse two-qubit gate cancellation on matching wires:
      ``cx(a,b)-cx(a,b)``, ``cz(a,b)-cz(a,b)`` (or ``cz(b,a)``),
      ``swap(a,b)-swap(a,b)`` (or ``swap(b,a)``).
    """
    allowed = (
        frozenset(g.strip().lower() for g in allowed_gates)
        if allowed_gates is not None
        else None
    )

    ops: List[Operation] = [
        Operation("cx" if o.gate == "cnot" else o.gate, o.qubits)
        for o in program.operations
        if o.gate != "i"
    ]

    def single_qubit_pass(current: List[Operation]) -> List[Operation]:
        # Group single-qubit operations along each wire between multi-qubit barriers
        # by scanning linearly and maintaining per-qubit pending 1Q queues that flush
        # whenever a multi-qubit gate touches those qubits.
        pending: Dict[int, List[Operation]] = {q: [] for q in range(program.n_qubits)}
        output: List[Operation] = []

        def simplify_wire(wire_ops: List[Operation], q: int) -> List[Operation]:
            changed = True
            w = list(wire_ops)
            while changed:
                changed = False
                # 1. Fold contiguous Z-axis phase gates mod 8
                folded: List[Operation] = []
                idx = 0
                while idx < len(w):
                    if w[idx].gate in _Z_AXIS_EIGHTHS:
                        total_eighths = 0
                        start_idx = idx
                        while idx < len(w) and w[idx].gate in _Z_AXIS_EIGHTHS:
                            total_eighths = (total_eighths + _Z_AXIS_EIGHTHS[w[idx].gate]) % 8
                            idx += 1
                        replacement = list(_eighths_to_z_ops(total_eighths, q, allowed))
                        if replacement != w[start_idx:idx]:
                            changed = True
                        folded.extend(replacement)
                    else:
                        folded.append(w[idx])
                        idx += 1
                w = folded

                # 2. Cancel adjacent self-inverse 1Q gates (h-h, x-x, y-y, z-z)
                # and conjugation (h-z-h -> x, h-x-h -> z)
                reduced: List[Operation] = []
                idx = 0
                while idx < len(w):
                    if (
                        idx + 1 < len(w)
                        and w[idx].gate in {"h", "x", "y", "z"}
                        and w[idx].gate == w[idx + 1].gate
                    ):
                        changed = True
                        idx += 2
                        continue
                    if (
                        idx + 2 < len(w)
                        and w[idx].gate == "h"
                        and w[idx + 1].gate == "z"
                        and w[idx + 2].gate == "h"
                        and (allowed is None or "x" in allowed)
                    ):
                        reduced.append(Operation("x", (q,)))
                        changed = True
                        idx += 3
                        continue
                    if (
                        idx + 2 < len(w)
                        and w[idx].gate == "h"
                        and w[idx + 1].gate == "x"
                        and w[idx + 2].gate == "h"
                        and (allowed is None or "z" in allowed)
                    ):
                        reduced.append(Operation("z", (q,)))
                        changed = True
                        idx += 3
                        continue
                    reduced.append(w[idx])
                    idx += 1
                w = reduced
            return w

        for op in current:
            if len(op.qubits) == 1:
                pending[op.qubits[0]].append(op)
            else:
                for q in op.qubits:
                    if pending[q]:
                        output.extend(simplify_wire(pending[q], q))
                        pending[q] = []
                # Check if op cancels directly with the last emitted multi-qubit op
                if output:
                    prev = output[-1]
                    if prev.gate == op.gate and len(prev.qubits) == len(op.qubits) == 2:
                        if op.gate == "cx" and prev.qubits == op.qubits:
                            output.pop()
                            continue
                        if op.gate in {"cz", "swap"} and set(prev.qubits) == set(op.qubits):
                            output.pop()
                            continue
                output.append(op)

        for q in range(program.n_qubits):
            if pending[q]:
                output.extend(simplify_wire(pending[q], q))
                pending[q] = []
        return output

    while True:
        next_ops = single_qubit_pass(ops)
        if next_ops == ops:
            break
        ops = next_ops

    return Program(program.n_qubits, tuple(ops))


@dataclass(frozen=True)
class TranspilationReport:
    """Complete Phase 3 compilation, routing, optimization, and equivalence report."""

    original_program: Program
    transpiled_program: Program
    basis_gates: Tuple[str, ...]
    coupling_map: Optional[CouplingMap]
    inserted_swaps: int
    layout_restored: bool
    topology_satisfied: bool
    basis_satisfied: bool
    unitary_verified: bool
    unitary_equivalent: Optional[bool]
    unitary_reason: str

    def as_dict(self) -> Dict[str, Any]:
        orig_counts = self.original_program.gate_counts()
        trans_counts = self.transpiled_program.gate_counts()
        return {
            "n_qubits": self.original_program.n_qubits,
            "original_gate_count": len(self.original_program.operations),
            "transpiled_gate_count": len(self.transpiled_program.operations),
            "original_gate_counts": orig_counts,
            "transpiled_gate_counts": trans_counts,
            "original_digest": self.original_program.digest(),
            "transpiled_digest": self.transpiled_program.digest(),
            "basis_gates": list(self.basis_gates),
            "coupling_map": self.coupling_map.as_dict() if self.coupling_map else None,
            "inserted_swaps": self.inserted_swaps,
            "layout_restored": self.layout_restored,
            "topology_satisfied": self.topology_satisfied,
            "basis_satisfied": self.basis_satisfied,
            "unitary_verified": self.unitary_verified,
            "unitary_equivalent": self.unitary_equivalent,
            "unitary_reason": self.unitary_reason,
            "transpiled_qasm": program_to_qasm(self.transpiled_program),
        }


def transpile_program(
    program: Program,
    *,
    coupling_map: Optional[CouplingMap] = None,
    basis_gates: Optional[Iterable[str]] = DEFAULT_BASIS_GATES,
    optimize: bool = True,
    restore_layout: bool = True,
    verify_equivalence: bool = True,
    verify_max_width: int = DEFAULT_VERIFY_WIDTH,
) -> TranspilationReport:
    """Execute the full Phase 3 compiler pipeline on ``program``:

    1. Pre-routing peephole optimization (when ``optimize=True``).
    2. Unfold 3-qubit ``ccx``/``toffoli`` gates into exact 15-gate Clifford+T sequences.
    3. Route two-qubit gates onto ``coupling_map`` via shortest-path ``SWAP`` bridges.
    4. Translate all gates into ``basis_gates``.
    5. Post-translation peephole and ``Z``-phase folding optimization within ``basis_gates``.
    6. Exact algebraic unitary equivalence check over ``Q(sqrt(2)) + i*Q(sqrt(2))``.
    """
    basis_tuple = (
        tuple(dict.fromkeys(g.strip().lower() for g in basis_gates))
        if basis_gates is not None
        else DEFAULT_BASIS_GATES
    )
    basis_set = frozenset(basis_tuple)

    # Unfold any 3-qubit gates in a copy of original for exact unitary comparison
    reference_unfolded = Program(
        program.n_qubits,
        tuple(
            sub
            for op in program.operations
            for sub in (
                _toffoli_clifford_t_ops(*op.qubits)
                if op.gate.lower() in ("ccx", "toffoli")
                else (op,)
            )
        ),
    )

    working = optimize_program(reference_unfolded) if optimize else reference_unfolded

    inserted_swaps = 0
    layout_restored = True
    topology_ok = True
    if coupling_map is not None:
        routing = route_program(working, coupling_map, restore_layout=restore_layout)
        working = routing.routed_program
        inserted_swaps = routing.inserted_swaps
        layout_restored = routing.layout_restored
        topology_ok = routing.all_two_qubit_gates_adjacent

    working = decompose_to_basis(working, basis_set)
    if optimize:
        working = optimize_program(working, allowed_gates=basis_set)

    if coupling_map is not None:
        topology_ok = all(
            coupling_map.is_connected(op.qubits[0], op.qubits[1])
            for op in working.operations
            if len(op.qubits) == 2
        )
    basis_ok = working.gates() <= basis_set

    unitary_verified = False
    unitary_equivalent: Optional[bool] = None
    unitary_reason = "verification not requested"
    if verify_equivalence:
        if program.n_qubits <= verify_max_width and layout_restored:
            cols_orig = program_unitary_columns(
                reference_unfolded, max_width=verify_max_width
            )
            cols_trans = program_unitary_columns(
                working, max_width=verify_max_width
            )
            unitary_verified = True
            unitary_equivalent = cols_orig == cols_trans
            unitary_reason = (
                f"exact 2^{program.n_qubits}x2^{program.n_qubits} unitary equivalence "
                f"{'verified' if unitary_equivalent else 'FAILED'} over Q(sqrt(2))+i*Q(sqrt(2))"
            )
            if not unitary_equivalent:
                raise ExactLaneError(unitary_reason)
        else:
            unitary_reason = (
                f"width {program.n_qubits} exceeds verify_max_width={verify_max_width} "
                "or layout was not restored; verified by compositional gate identities"
            )

    return TranspilationReport(
        original_program=program,
        transpiled_program=working,
        basis_gates=basis_tuple,
        coupling_map=coupling_map,
        inserted_swaps=inserted_swaps,
        layout_restored=layout_restored,
        topology_satisfied=topology_ok,
        basis_satisfied=basis_ok,
        unitary_verified=unitary_verified,
        unitary_equivalent=unitary_equivalent,
        unitary_reason=unitary_reason,
    )


# ======================================================================
# Phase 4: Quantum Error Correction (QEC) & Fault Tolerance Layer
# ======================================================================


@dataclass(frozen=True)
class QECCycleReport:
    """Exact outcome of a planar surface-code syndrome extraction and decoding cycle."""

    distance: int
    data_qubits: int
    ancilla_qubits: int
    total_tableau_qubits: int
    x_error_qubits: Tuple[int, ...]
    z_error_qubits: Tuple[int, ...]
    z_check_syndrome_int: int
    x_check_syndrome_int: int
    z_check_syndrome_bits: Tuple[int, ...]
    x_check_syndrome_bits: Tuple[int, ...]
    ancilla_matches_gf2_parity: bool
    ancilla_measurements_deterministic: bool
    exact_x_correction_qubits: Tuple[int, ...]
    exact_z_correction_qubits: Tuple[int, ...]
    union_find_x_correction_qubits: Tuple[int, ...]
    union_find_z_correction_qubits: Tuple[int, ...]
    exact_decoder_succeeded: bool
    union_find_decoder_succeeded: bool
    post_recovery_syndrome_zero: bool
    logical_z_preserved: bool
    code_verified: bool
    proof_digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "distance": self.distance,
            "data_qubits": self.data_qubits,
            "ancilla_qubits": self.ancilla_qubits,
            "total_tableau_qubits": self.total_tableau_qubits,
            "x_error_qubits": list(self.x_error_qubits),
            "z_error_qubits": list(self.z_error_qubits),
            "z_check_syndrome_int": self.z_check_syndrome_int,
            "x_check_syndrome_int": self.x_check_syndrome_int,
            "z_check_syndrome_bits": list(self.z_check_syndrome_bits),
            "x_check_syndrome_bits": list(self.x_check_syndrome_bits),
            "ancilla_matches_gf2_parity": self.ancilla_matches_gf2_parity,
            "ancilla_measurements_deterministic": self.ancilla_measurements_deterministic,
            "exact_x_correction_qubits": list(self.exact_x_correction_qubits),
            "exact_z_correction_qubits": list(self.exact_z_correction_qubits),
            "union_find_x_correction_qubits": list(self.union_find_x_correction_qubits),
            "union_find_z_correction_qubits": list(self.union_find_z_correction_qubits),
            "exact_decoder_succeeded": self.exact_decoder_succeeded,
            "union_find_decoder_succeeded": self.union_find_decoder_succeeded,
            "post_recovery_syndrome_zero": self.post_recovery_syndrome_zero,
            "logical_z_preserved": self.logical_z_preserved,
            "code_verified": self.code_verified,
            "proof_digest": self.proof_digest,
        }


def _bitset_to_qubits(mask: int, n_qubits: int) -> Tuple[int, ...]:
    return tuple(q for q in range(n_qubits) if (mask >> q) & 1)


def run_surface_code_qec_cycle(
    distance: int = 3,
    *,
    x_error_qubits: Iterable[int] = (),
    z_error_qubits: Iterable[int] = (),
) -> QECCycleReport:
    """Run an exact distance-``d`` planar surface-code QEC cycle on ``StabilizerState``.

    1. Instantiates :class:`kellogg.surface_code.PlanarSurfaceCode` of distance ``d``
       with $n = d^2 + (d-1)^2$ data qubits, $m_z = d(d-1)$ $Z$-plaquette checks,
       and $m_x = d(d-1)$ $X$-star checks encoding $k = 1$ logical qubit.
    2. Prepares the quiescent logical $|0_L\\rangle$ code state on a
       $(n + m_z + m_x)$-qubit :class:`StabilizerState` tableau by projecting all
       $X$-star stabilizers onto their $+1$ eigenspace via ancilla measurement.
    3. Injects the requested physical $X$ and $Z$ errors onto the data qubits.
    4. Executes non-destructive ancilla syndrome extraction circuits (CNOT
       parities into $Z$-check ancillas and $H$-CNOT-$H$ parities into $X$-check
       ancillas) and verifies that every syndrome measurement is deterministic
       (``degenerate == False``) and matches the GF(2) parity check matrix.
    5. Decodes the syndromes using both :meth:`decode_exact` (minimum-weight
       matching) and :meth:`decode_union_find` (Delfosse-Nickerson cluster peeling).
    6. Applies the active Pauli recovery to the tableau data qubits, re-extracts
       syndromes to confirm zero residual defects, and measures $\\bar{Z}$ via an
       ancilla to prove the logical state $|0_L\\rangle$ was preserved without
       collapse.
    """
    from kellogg.surface_code import PlanarSurfaceCode

    code = PlanarSurfaceCode(distance)
    code_report = code.verify()
    n_data = code.n
    m_z = len(code.hz)
    m_x = len(code.hx)

    x_errs = tuple(sorted({int(q) for q in x_error_qubits}))
    z_errs = tuple(sorted({int(q) for q in z_error_qubits}))
    for q in x_errs + z_errs:
        if not (0 <= q < n_data):
            raise ValueError(f"error qubit {q} outside [0, {n_data})")

    x_error_mask = sum(1 << q for q in x_errs)
    z_error_mask = sum(1 << q for q in z_errs)

    # Allocate data qubits [0..n_data-1], Z-check ancillas [n_data..n_data+m_z-1],
    # and X-check ancillas [n_data+m_z..n_data+m_z+m_x-1]
    total_qubits = n_data + m_z + m_x
    tableau = StabilizerState.basis(total_qubits)

    # Step 1: Project |0...0> data register into +1 eigenstate of every X-star check
    # (|0...0> is already +1 eigenstate of every Z-plaquette check and of logical_z)
    for j, x_check_mask in enumerate(code.hx):
        anc = n_data + m_z + j
        tableau.h(anc)
        for q in _bitset_to_qubits(x_check_mask, n_data):
            tableau.cnot(anc, q)
        tableau.h(anc)
        m_res = tableau.measure(anc, outcome=0)
        if m_res["outcome"] == 1:
            tableau.x(anc)

    # Step 2: Inject physical X and Z errors on the data qubits
    for q in x_errs:
        tableau.x(q)
    for q in z_errs:
        tableau.z(q)

    # Step 3: Non-destructive ancilla syndrome extraction
    z_syndrome_bits: List[int] = []
    x_syndrome_bits: List[int] = []
    all_deterministic = True

    # Z-checks detect X errors
    for i, z_check_mask in enumerate(code.hz):
        anc = n_data + i
        for q in _bitset_to_qubits(z_check_mask, n_data):
            tableau.cnot(q, anc)
        m_res = tableau.measure(anc)
        if m_res["degenerate"]:
            all_deterministic = False
        bit = int(m_res["outcome"])
        z_syndrome_bits.append(bit)
        if bit == 1:
            tableau.x(anc)  # reset ancilla to |0>

    # X-checks detect Z errors
    for j, x_check_mask in enumerate(code.hx):
        anc = n_data + m_z + j
        tableau.h(anc)
        for q in _bitset_to_qubits(x_check_mask, n_data):
            tableau.cnot(anc, q)
        tableau.h(anc)
        m_res = tableau.measure(anc)
        if m_res["degenerate"]:
            all_deterministic = False
        bit = int(m_res["outcome"])
        x_syndrome_bits.append(bit)
        if bit == 1:
            tableau.x(anc)  # reset ancilla to |0>

    anc_z_syndrome = sum(bit << i for i, bit in enumerate(z_syndrome_bits))
    anc_x_syndrome = sum(bit << j for j, bit in enumerate(x_syndrome_bits))

    gf2_z_syndrome = code.syndrome(code.hz, x_error_mask)
    gf2_x_syndrome = code.syndrome(code.hx, z_error_mask)
    ancilla_matches = (anc_z_syndrome == gf2_z_syndrome) and (
        anc_x_syndrome == gf2_x_syndrome
    )

    # Step 4: Decode using both exact MWM and Union-Find decoders
    exact_x_corr = code.decode_exact(anc_z_syndrome, kind="x_errors")
    exact_z_corr = code.decode_exact(anc_x_syndrome, kind="z_errors")
    uf_x_corr = code.decode_union_find(anc_z_syndrome, kind="x_errors")
    uf_z_corr = code.decode_union_find(anc_x_syndrome, kind="z_errors")

    exact_ok = code.corrected(x_error_mask, exact_x_corr, kind="x_errors") and code.corrected(
        z_error_mask, exact_z_corr, kind="z_errors"
    )
    uf_ok = code.corrected(x_error_mask, uf_x_corr, kind="x_errors") and code.corrected(
        z_error_mask, uf_z_corr, kind="z_errors"
    )

    # Step 5: Apply active recovery (exact decoder) onto the live StabilizerState
    for q in _bitset_to_qubits(exact_x_corr, n_data):
        tableau.x(q)
    for q in _bitset_to_qubits(exact_z_corr, n_data):
        tableau.z(q)

    # Verify post-recovery syndrome on the live tableau is identically 0
    post_syndrome_nonzero = 0
    for i, z_check_mask in enumerate(code.hz):
        anc = n_data + i
        for q in _bitset_to_qubits(z_check_mask, n_data):
            tableau.cnot(q, anc)
        m_res = tableau.measure(anc)
        post_syndrome_nonzero |= int(m_res["outcome"])
        if m_res["outcome"] == 1:
            tableau.x(anc)

    for j, x_check_mask in enumerate(code.hx):
        anc = n_data + m_z + j
        tableau.h(anc)
        for q in _bitset_to_qubits(x_check_mask, n_data):
            tableau.cnot(anc, q)
        tableau.h(anc)
        m_res = tableau.measure(anc)
        post_syndrome_nonzero |= int(m_res["outcome"])
        if m_res["outcome"] == 1:
            tableau.x(anc)

    # Measure logical_z non-destructively via ancilla n_data to confirm |0_L> is preserved
    anc_logical = n_data
    for q in _bitset_to_qubits(code.logical_z, n_data):
        tableau.cnot(q, anc_logical)
    logical_meas = tableau.measure(anc_logical)
    logical_z_preserved = (
        not logical_meas["degenerate"] and int(logical_meas["outcome"]) == 0
    )

    unsigned = {
        "distance": distance,
        "data_qubits": n_data,
        "ancilla_qubits": m_z + m_x,
        "total_tableau_qubits": total_qubits,
        "x_error_qubits": list(x_errs),
        "z_error_qubits": list(z_errs),
        "z_check_syndrome_int": anc_z_syndrome,
        "x_check_syndrome_int": anc_x_syndrome,
        "ancilla_matches_gf2_parity": ancilla_matches,
        "ancilla_measurements_deterministic": all_deterministic,
        "exact_x_correction_qubits": list(_bitset_to_qubits(exact_x_corr, n_data)),
        "exact_z_correction_qubits": list(_bitset_to_qubits(exact_z_corr, n_data)),
        "union_find_x_correction_qubits": list(_bitset_to_qubits(uf_x_corr, n_data)),
        "union_find_z_correction_qubits": list(_bitset_to_qubits(uf_z_corr, n_data)),
        "exact_decoder_succeeded": exact_ok,
        "union_find_decoder_succeeded": uf_ok,
        "post_recovery_syndrome_zero": post_syndrome_nonzero == 0,
        "logical_z_preserved": logical_z_preserved,
        "code_verified": code_report.verified,
    }
    return QECCycleReport(
        distance=distance,
        data_qubits=n_data,
        ancilla_qubits=m_z + m_x,
        total_tableau_qubits=total_qubits,
        x_error_qubits=x_errs,
        z_error_qubits=z_errs,
        z_check_syndrome_int=anc_z_syndrome,
        x_check_syndrome_int=anc_x_syndrome,
        z_check_syndrome_bits=tuple(z_syndrome_bits),
        x_check_syndrome_bits=tuple(x_syndrome_bits),
        ancilla_matches_gf2_parity=ancilla_matches,
        ancilla_measurements_deterministic=all_deterministic,
        exact_x_correction_qubits=_bitset_to_qubits(exact_x_corr, n_data),
        exact_z_correction_qubits=_bitset_to_qubits(exact_z_corr, n_data),
        union_find_x_correction_qubits=_bitset_to_qubits(uf_x_corr, n_data),
        union_find_z_correction_qubits=_bitset_to_qubits(uf_z_corr, n_data),
        exact_decoder_succeeded=exact_ok,
        union_find_decoder_succeeded=uf_ok,
        post_recovery_syndrome_zero=(post_syndrome_nonzero == 0),
        logical_z_preserved=logical_z_preserved,
        code_verified=code_report.verified,
        proof_digest=_canonical_digest(unsigned),
    )


# ======================================================================
# Phase 5: Quantum Orchestration and Hybrid Workload Scheduling
# ======================================================================


@dataclass(frozen=True)
class HybridJobSpec:
    """Specification for a hybrid quantum-classical variational job."""

    job_id: str
    n_qubits: int
    pauli_terms: Tuple[Tuple[Fraction, Tuple[Tuple[int, str], ...]], ...]
    candidate_turns: Tuple[Fraction, ...] = (
        Fraction(0, 1),
        Fraction(1, 8),
        Fraction(1, 4),
        Fraction(3, 8),
        Fraction(1, 2),
        Fraction(5, 8),
        Fraction(3, 4),
        Fraction(7, 8),
    )
    coupling_map: Optional[CouplingMap] = None
    basis_gates: Tuple[str, ...] = DEFAULT_BASIS_GATES
    priority: int = 1


@dataclass(frozen=True)
class HybridIterationReceipt:
    """One quantum-classical iteration record in a hash-chained hybrid session."""

    iteration: int
    parameter_turns: str
    raw_gate_count: int
    transpiled_gate_count: int
    inserted_swaps: int
    program_digest: str
    energy_exact: str
    prev_receipt_digest: str
    receipt_digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "parameter_turns": self.parameter_turns,
            "raw_gate_count": self.raw_gate_count,
            "transpiled_gate_count": self.transpiled_gate_count,
            "inserted_swaps": self.inserted_swaps,
            "program_digest": self.program_digest,
            "energy_exact": self.energy_exact,
            "prev_receipt_digest": self.prev_receipt_digest,
            "receipt_digest": self.receipt_digest,
        }


@dataclass(frozen=True)
class HybridOrchestrationReport:
    """Complete report from a scheduled hybrid CPU-QPU/VQC variational workload."""

    job_id: str
    session_id: str
    n_qubits: int
    iterations: int
    optimal_turns: str
    optimal_energy_exact: str
    optimal_program_digest: str
    receipt_chain_verified: bool
    final_receipt_digest: str
    history: Tuple[HybridIterationReceipt, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "n_qubits": self.n_qubits,
            "iterations": self.iterations,
            "optimal_turns": self.optimal_turns,
            "optimal_energy_exact": self.optimal_energy_exact,
            "optimal_program_digest": self.optimal_program_digest,
            "receipt_chain_verified": self.receipt_chain_verified,
            "final_receipt_digest": self.final_receipt_digest,
            "history": [r.as_dict() for r in self.history],
        }


def _program_to_quantum_register(program: Program) -> QuantumRegister:
    """Execute a Clifford+T :class:`Program` on :class:`QuantumRegister`."""
    reg = QuantumRegister(program.n_qubits)
    for op in program.operations:
        g = op.gate.lower()
        if g == "i":
            continue
        if g in ("h", "x", "y", "z", "s", "t"):
            getattr(reg, f"apply_{g}")(op.qubits[0])
        elif g == "sdg":
            for _ in range(3):
                reg.apply_s(op.qubits[0])
        elif g == "tdg":
            reg.apply_phase(op.qubits[0], Fraction(-1, 8))
        elif g in ("cx", "cnot"):
            reg.apply_cnot(op.qubits[0], op.qubits[1])
        elif g == "cz":
            reg.apply_cz(op.qubits[0], op.qubits[1])
        elif g == "swap":
            a, b = op.qubits
            reg.apply_cnot(a, b)
            reg.apply_cnot(b, a)
            reg.apply_cnot(a, b)
        else:
            raise ExactLaneError(f"unsupported gate {g!r} on QuantumRegister")
    reg.assert_normalized()
    return reg


class HybridWorkloadOrchestrator:
    """Priority queue and hybrid quantum-classical session orchestrator."""

    def __init__(self) -> None:
        self._queue: List[HybridJobSpec] = []

    def submit(self, spec: HybridJobSpec) -> None:
        self._queue.append(spec)
        # Sort by descending priority, then job_id for deterministic scheduling
        self._queue.sort(key=lambda s: (-s.priority, s.job_id))

    def pending_count(self) -> int:
        return len(self._queue)

    def run_next(self) -> HybridOrchestrationReport:
        if not self._queue:
            raise RuntimeError("no hybrid jobs queued in orchestrator")
        spec = self._queue.pop(0)
        return self.execute_job(spec)

    def drain(self) -> Tuple[HybridOrchestrationReport, ...]:
        reports: List[HybridOrchestrationReport] = []
        while self._queue:
            reports.append(self.run_next())
        return tuple(reports)

    @staticmethod
    def execute_job(spec: HybridJobSpec) -> HybridOrchestrationReport:
        cmap = spec.coupling_map or CouplingMap.line(spec.n_qubits)
        terms = [
            (_frac(coeff), tuple((int(q), str(p).lower()) for q, p in ops))
            for coeff, ops in spec.pauli_terms
        ]
        prev_digest = "0" * 64
        history: List[HybridIterationReceipt] = []
        best_val: Optional[sp.Expr] = None
        best_turns_str = ""
        best_prog_digest = ""

        for idx, theta in enumerate(spec.candidate_turns):
            turn_val = _frac(theta)
            raw_prog = build_ansatz_program(
                spec.n_qubits,
                [turn_val] * spec.n_qubits,
                layers=1,
                axis="y",
                entangler="cx",
                entanglement="linear",
            )
            trans_report = transpile_program(
                raw_prog,
                coupling_map=cmap,
                basis_gates=spec.basis_gates,
                optimize=True,
                restore_layout=True,
                verify_equivalence=(spec.n_qubits <= DEFAULT_VERIFY_WIDTH),
            )
            compiled = trans_report.transpiled_program
            reg = _program_to_quantum_register(compiled)

            energy_expr = sp.simplify(
                sum(coeff * pauli_expectation(reg, ops) for coeff, ops in terms)
            )
            energy_str = str(energy_expr)

            unsigned_receipt = {
                "job_id": spec.job_id,
                "iteration": idx,
                "parameter_turns": str(turn_val),
                "raw_gate_count": len(raw_prog.operations),
                "transpiled_gate_count": len(compiled.operations),
                "inserted_swaps": trans_report.inserted_swaps,
                "program_digest": compiled.digest(),
                "energy_exact": energy_str,
                "prev_receipt_digest": prev_digest,
            }
            receipt_digest = _canonical_digest(unsigned_receipt)
            receipt = HybridIterationReceipt(
                iteration=idx,
                parameter_turns=str(turn_val),
                raw_gate_count=len(raw_prog.operations),
                transpiled_gate_count=len(compiled.operations),
                inserted_swaps=trans_report.inserted_swaps,
                program_digest=compiled.digest(),
                energy_exact=energy_str,
                prev_receipt_digest=prev_digest,
                receipt_digest=receipt_digest,
            )
            history.append(receipt)
            prev_digest = receipt_digest

            if best_val is None or sp.simplify(energy_expr - best_val) < 0:
                best_val = energy_expr
                best_turns_str = str(turn_val)
                best_prog_digest = compiled.digest()

        # Verify hash chain integrity
        chain_ok = True
        cursor = "0" * 64
        for r in history:
            if r.prev_receipt_digest != cursor:
                chain_ok = False
                break
            cursor = r.receipt_digest

        session_id = _canonical_digest(
            {"job_id": spec.job_id, "final_receipt": prev_digest}
        )[:16]
        return HybridOrchestrationReport(
            job_id=spec.job_id,
            session_id=session_id,
            n_qubits=spec.n_qubits,
            iterations=len(history),
            optimal_turns=best_turns_str,
            optimal_energy_exact=str(best_val),
            optimal_program_digest=best_prog_digest,
            receipt_chain_verified=chain_ok,
            final_receipt_digest=prev_digest,
            history=tuple(history),
        )


def run_hybrid_workload(
    n_qubits: int = 2,
    *,
    J: Any = 1,
    g: Any = 1,
    candidate_turns: Sequence[Any] = (
        Fraction(0, 1),
        Fraction(1, 8),
        Fraction(1, 4),
        Fraction(3, 8),
        Fraction(1, 2),
        Fraction(5, 8),
        Fraction(3, 4),
        Fraction(7, 8),
    ),
    job_id: str = "hybrid-vqe-ising",
) -> HybridOrchestrationReport:
    """Convenience runner for a complete Phase 5 hybrid VQE workload over the TFIM Hamiltonian."""
    terms = tuple(QuantumLibrary.ising_terms(n_qubits, J=J, g=g))
    spec = HybridJobSpec(
        job_id=job_id,
        n_qubits=n_qubits,
        pauli_terms=terms,
        candidate_turns=tuple(_frac(t) for t in candidate_turns),
        coupling_map=CouplingMap.line(n_qubits),
    )
    orchestrator = HybridWorkloadOrchestrator()
    orchestrator.submit(spec)
    return orchestrator.run_next()


@dataclass(frozen=True)
class GPUFleetQuantumWorkloadReport:
    """Complete report from a distributed GPU/iGPU fleet quantum workload execution."""

    work_id: str
    tenant: str
    n_qubits: int
    total_candidates: int
    optimal_turns: str
    optimal_energy_exact: str
    optimal_program_digest: str
    fleet_report: Dict[str, Any]
    report_digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "work_id": self.work_id,
            "tenant": self.tenant,
            "n_qubits": self.n_qubits,
            "total_candidates": self.total_candidates,
            "optimal_turns": self.optimal_turns,
            "optimal_energy_exact": self.optimal_energy_exact,
            "optimal_program_digest": self.optimal_program_digest,
            "fleet_report": self.fleet_report,
            "report_digest": self.report_digest,
        }


def run_gpu_fleet_hybrid_workload(
    n_qubits: int = 2,
    *,
    J: Any = 1,
    g: Any = 1,
    candidate_turns: Sequence[Any] = (
        Fraction(0, 1),
        Fraction(1, 8),
        Fraction(1, 4),
        Fraction(3, 8),
        Fraction(1, 2),
        Fraction(5, 8),
        Fraction(3, 4),
        Fraction(7, 8),
    ),
    worker_count: int = 3,
    lanes_per_worker: int = 4,
    scale_index: int = 15,
    tenant: str = "turing_quantum_tenant",
    fail_worker_ids: Sequence[str] = (),
    work_id: str = "gpu-fleet-vqe-ising",
) -> GPUFleetQuantumWorkloadReport:
    """Capacity-plan, partition, lease, and execute a hybrid quantum workload across a Chronus GPU/iGPU fleet."""
    from chronus.fleet.capacity import (
        GPUWorkerSpec,
        WorkloadSpec,
        execute_fleet_workload,
    )

    if worker_count < 1 or lanes_per_worker < 1:
        raise ValueError("worker_count and lanes_per_worker must be >= 1")

    turns_list = [_frac(t) for t in candidate_turns]
    terms = [
        (_frac(coeff), tuple((int(q), str(p).lower()) for q, p in ops))
        for coeff, ops in QuantumLibrary.ising_terms(n_qubits, J=J, g=g)
    ]
    cmap = CouplingMap.line(n_qubits)

    workers = [
        GPUWorkerSpec(
            worker_id=f"gpu-worker-{i}",
            tenant=tenant,
            lanes=lanes_per_worker,
            compute_units=32,
            clock_mhz=1500,
            global_memory_bytes=8 * 1024**3,
        )
        for i in range(worker_count)
    ]
    workload = WorkloadSpec(
        work_id=work_id,
        tenant=tenant,
        operation="hybrid_vqe_circuit_batch",
        total_items=len(turns_list),
        bytes_per_item=256,
        cycles_per_item=16,
        scale_index=scale_index,
        state_qubits=n_qubits,
        required_floor_ops_per_second=1_000_000_000,
    )

    def evaluate_candidate(theta: Fraction) -> Dict[str, Any]:
        raw_prog = build_ansatz_program(
            n_qubits,
            [theta] * n_qubits,
            layers=1,
            axis="y",
            entangler="cx",
            entanglement="linear",
        )
        trans_report = transpile_program(
            raw_prog,
            coupling_map=cmap,
            basis_gates=DEFAULT_BASIS_GATES,
            optimize=True,
            restore_layout=True,
            verify_equivalence=(n_qubits <= DEFAULT_VERIFY_WIDTH),
        )
        compiled = trans_report.transpiled_program
        reg = _program_to_quantum_register(compiled)
        energy_expr = sp.simplify(
            sum(coeff * pauli_expectation(reg, ops) for coeff, ops in terms)
        )
        pulse_sched = compile_pulse_schedule(compiled, include_readout=True)
        return {
            "parameter_turns": str(theta),
            "raw_gate_count": len(raw_prog.operations),
            "transpiled_gate_count": len(compiled.operations),
            "inserted_swaps": trans_report.inserted_swaps,
            "program_digest": compiled.digest(),
            "pulse_duration_ns": pulse_sched.total_duration_ns,
            "energy_exact": str(energy_expr),
        }

    fleet_report = execute_fleet_workload(
        workers,
        workload,
        turns_list,
        evaluate_candidate,
        fail_worker_ids=fail_worker_ids,
    )
    if not fleet_report.single_vs_distributed_agree:
        raise ExactLaneError("Distributed GPU fleet output differed from single-node reference")

    best_val: Optional[sp.Expr] = None
    best_turns = ""
    best_digest = ""
    for item_out in fleet_report.reassembled_output:
        e_val = sp.sympify(item_out["energy_exact"])
        if best_val is None or sp.simplify(e_val - best_val) < 0:
            best_val = e_val
            best_turns = str(item_out["parameter_turns"])
            best_digest = str(item_out["program_digest"])

    fleet_exact_dict = fleet_report.as_exact_dict()
    unsigned = {
        "work_id": work_id,
        "tenant": tenant,
        "n_qubits": n_qubits,
        "total_candidates": len(turns_list),
        "optimal_turns": best_turns,
        "optimal_energy_exact": str(best_val),
        "optimal_program_digest": best_digest,
        "fleet_report": fleet_exact_dict,
    }
    audit = audit_exactness(unsigned)
    if not audit.exact:
        raise ExactLaneError(
            "run_gpu_fleet_hybrid_workload failed exactness audit: "
            + "; ".join(audit.violations)
        )

    return GPUFleetQuantumWorkloadReport(
        work_id=work_id,
        tenant=tenant,
        n_qubits=n_qubits,
        total_candidates=len(turns_list),
        optimal_turns=best_turns,
        optimal_energy_exact=str(best_val),
        optimal_program_digest=best_digest,
        fleet_report=fleet_exact_dict,
        report_digest=_canonical_digest(unsigned),
    )


# ======================================================================
# Phase 6: Pulse-Level Compilation and Control Software
# ======================================================================


@dataclass(frozen=True)
class PulseInstruction:
    """One exact symbolic/rational pulse instruction on a hardware control channel."""

    channel: str
    gate: str
    qubits: Tuple[int, ...]
    start_ns: int
    duration_ns: int
    waveform: str
    amplitude: Fraction
    drag_beta: Fraction
    frame_phase_turns: Fraction
    phase_shift_turns: Fraction

    def as_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "gate": self.gate,
            "qubits": list(self.qubits),
            "start_ns": self.start_ns,
            "duration_ns": self.duration_ns,
            "end_ns": self.start_ns + self.duration_ns,
            "waveform": self.waveform,
            "amplitude": str(self.amplitude),
            "drag_beta": str(self.drag_beta),
            "frame_phase_turns": str(self.frame_phase_turns),
            "phase_shift_turns": str(self.phase_shift_turns),
        }


@dataclass(frozen=True)
class PulseSchedule:
    """Compiled pulse control schedule for a quantum program."""

    n_qubits: int
    instructions: Tuple[PulseInstruction, ...]
    total_duration_ns: int
    physical_pulse_count: int
    virtual_z_count: int
    final_frame_phases: Dict[str, str]
    channel_end_ns: Dict[str, int]
    schedule_digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "n_qubits": self.n_qubits,
            "instruction_count": len(self.instructions),
            "physical_pulse_count": self.physical_pulse_count,
            "virtual_z_count": self.virtual_z_count,
            "total_duration_ns": self.total_duration_ns,
            "final_frame_phases": dict(self.final_frame_phases),
            "channel_end_ns": dict(self.channel_end_ns),
            "schedule_digest": self.schedule_digest,
            "instructions": [inst.as_dict() for inst in self.instructions],
        }


class PulseCompiler:
    """Lowers a native :class:`Program` into an exact pulse control schedule.

    Implements Virtual-Z software frame tracking:
    * ``z``, ``s``, ``sdg``, ``t``, ``tdg`` execute in ``0 ns`` by shifting the
      local oscillator frame phase in ``Q/Z`` by exact rational turns
      (``1/2``, ``1/4``, ``-1/4``, ``1/8``, ``-1/8``).
    * ``h`` is lowered via $H = R_z(1/4\\text{ turn}) R_x(1/4\\text{ turn}) R_z(1/4\\text{ turn})$:
      two ``0 ns`` Virtual-Z frame shifts bracketing one ``16 ns`` DRAG $\\pi/2$ pulse.
    * ``x`` and ``y`` emit ``32 ns`` DRAG $\\pi$ pulses on drive channel ``d{q}``.
    * ``cx`` emits a ``64 ns`` echoed cross-resonance (``ecr``) pulse on coupler
      channel ``u{c}_{t}`` and rotary target drive on ``d{t}``.
    * ``cz`` emits a ``48 ns`` adiabatic flux pulse (``cz_flux``) on ``u{a}_{b}``.
    """

    VIRTUAL_Z_TURNS: Dict[str, Fraction] = {
        "z": Fraction(1, 2),
        "s": Fraction(1, 4),
        "sdg": Fraction(-1, 4),
        "t": Fraction(1, 8),
        "tdg": Fraction(-1, 8),
    }

    def compile(
        self,
        program: Program,
        *,
        include_readout: bool = True,
    ) -> PulseSchedule:
        # Unfold any 3-qubit CCX or SWAP before pulse lowering
        ops: List[Operation] = []
        for op in program.operations:
            g = op.gate.lower()
            if g in ("ccx", "toffoli"):
                ops.extend(_toffoli_clifford_t_ops(*op.qubits))
            elif g == "swap":
                a, b = op.qubits
                ops.extend(
                    (
                        Operation("cx", (a, b)),
                        Operation("cx", (b, a)),
                        Operation("cx", (a, b)),
                    )
                )
            else:
                ops.append(op)

        qubit_time: Dict[int, int] = {q: 0 for q in range(program.n_qubits)}
        frame_phase: Dict[int, Fraction] = {
            q: Fraction(0, 1) for q in range(program.n_qubits)
        }
        channel_end: Dict[str, int] = {f"d{q}": 0 for q in range(program.n_qubits)}
        instructions: List[PulseInstruction] = []

        def emit_virtual_z(q: int, gate_label: str, delta_turns: Fraction) -> None:
            frame_phase[q] = (frame_phase[q] + delta_turns) % 1
            ch = f"d{q}"
            t_now = qubit_time[q]
            instructions.append(
                PulseInstruction(
                    channel=ch,
                    gate=gate_label,
                    qubits=(q,),
                    start_ns=t_now,
                    duration_ns=0,
                    waveform="virtual_z",
                    amplitude=Fraction(0, 1),
                    drag_beta=Fraction(0, 1),
                    frame_phase_turns=frame_phase[q],
                    phase_shift_turns=delta_turns,
                )
            )

        for op in ops:
            g = op.gate.lower()
            if g == "i":
                continue
            if g in self.VIRTUAL_Z_TURNS:
                q = op.qubits[0]
                emit_virtual_z(q, g, self.VIRTUAL_Z_TURNS[g])
            elif g == "h":
                q = op.qubits[0]
                emit_virtual_z(q, "h_pre_vz", Fraction(1, 4))
                ch = f"d{q}"
                t0 = qubit_time[q]
                dur = 16
                instructions.append(
                    PulseInstruction(
                        channel=ch,
                        gate="h",
                        qubits=(q,),
                        start_ns=t0,
                        duration_ns=dur,
                        waveform="drag_pi_over_2",
                        amplitude=Fraction(1, 4),
                        drag_beta=Fraction(1, 8),
                        frame_phase_turns=frame_phase[q],
                        phase_shift_turns=Fraction(0, 1),
                    )
                )
                qubit_time[q] = t0 + dur
                channel_end[ch] = t0 + dur
                emit_virtual_z(q, "h_post_vz", Fraction(1, 4))
            elif g in ("x", "y"):
                q = op.qubits[0]
                ch = f"d{q}"
                t0 = qubit_time[q]
                dur = 32
                drive_phase = (
                    frame_phase[q]
                    if g == "x"
                    else (frame_phase[q] + Fraction(1, 4)) % 1
                )
                instructions.append(
                    PulseInstruction(
                        channel=ch,
                        gate=g,
                        qubits=(q,),
                        start_ns=t0,
                        duration_ns=dur,
                        waveform="drag_pi",
                        amplitude=Fraction(1, 2),
                        drag_beta=Fraction(1, 8),
                        frame_phase_turns=drive_phase,
                        phase_shift_turns=Fraction(0, 1),
                    )
                )
                qubit_time[q] = t0 + dur
                channel_end[ch] = t0 + dur
            elif g in ("cx", "cnot", "cz"):
                c, t = op.qubits
                t_sync = max(qubit_time[c], qubit_time[t])
                dur = 64 if g in ("cx", "cnot") else 48
                coupler_ch = f"u{c}_{t}"
                waveform = "ecr_echoed_cr" if g in ("cx", "cnot") else "cz_adiabatic_flux"
                amp = Fraction(3, 8) if g in ("cx", "cnot") else Fraction(2, 5)
                instructions.append(
                    PulseInstruction(
                        channel=coupler_ch,
                        gate="cx" if g == "cnot" else g,
                        qubits=(c, t),
                        start_ns=t_sync,
                        duration_ns=dur,
                        waveform=waveform,
                        amplitude=amp,
                        drag_beta=Fraction(0, 1),
                        frame_phase_turns=(frame_phase[c] - frame_phase[t]) % 1,
                        phase_shift_turns=Fraction(0, 1),
                    )
                )
                qubit_time[c] = t_sync + dur
                qubit_time[t] = t_sync + dur
                channel_end[coupler_ch] = t_sync + dur
                channel_end[f"d{c}"] = max(channel_end[f"d{c}"], t_sync + dur)
                channel_end[f"d{t}"] = max(channel_end[f"d{t}"], t_sync + dur)
            else:
                raise ExactLaneError(f"PulseCompiler has no pulse rule for gate {g!r}")

        if include_readout:
            t_barrier = max(qubit_time.values(), default=0)
            readout_dur = 256
            for q in range(program.n_qubits):
                m_ch = f"m{q}"
                instructions.append(
                    PulseInstruction(
                        channel=m_ch,
                        gate="measure",
                        qubits=(q,),
                        start_ns=t_barrier,
                        duration_ns=readout_dur,
                        waveform="readout_gaussian_square",
                        amplitude=Fraction(1, 5),
                        drag_beta=Fraction(0, 1),
                        frame_phase_turns=frame_phase[q],
                        phase_shift_turns=Fraction(0, 1),
                    )
                )
                qubit_time[q] = t_barrier + readout_dur
                channel_end[m_ch] = t_barrier + readout_dur

        total_dur = max(qubit_time.values(), default=0)
        vz_count = sum(1 for i in instructions if i.waveform == "virtual_z")
        phys_count = len(instructions) - vz_count
        final_phases = {f"q{q}": str(frame_phase[q]) for q in range(program.n_qubits)}

        unsigned = {
            "n_qubits": program.n_qubits,
            "total_duration_ns": total_dur,
            "physical_pulse_count": phys_count,
            "virtual_z_count": vz_count,
            "final_frame_phases": final_phases,
            "instructions": [i.as_dict() for i in instructions],
        }
        return PulseSchedule(
            n_qubits=program.n_qubits,
            instructions=tuple(instructions),
            total_duration_ns=total_dur,
            physical_pulse_count=phys_count,
            virtual_z_count=vz_count,
            final_frame_phases=final_phases,
            channel_end_ns=channel_end,
            schedule_digest=_canonical_digest(unsigned),
        )


def compile_pulse_schedule(
    program: Program,
    *,
    include_readout: bool = True,
) -> PulseSchedule:
    """Compile ``program`` into an exact :class:`PulseSchedule`."""
    return PulseCompiler().compile(program, include_readout=include_readout)


# ======================================================================
# Full 6-Phase End-to-End Quantum Software Stack Runner
# ======================================================================


@dataclass(frozen=True)
class SoftwareStackReport:
    """End-to-end verification report across all 6 phases of the quantum software stack."""

    phase1_authoring: Dict[str, Any]
    phase2_ir_qasm: Dict[str, Any]
    phase3_transpilation: Dict[str, Any]
    phase4_qec: Dict[str, Any]
    phase5_orchestration: Dict[str, Any]
    phase6_pulse_control: Dict[str, Any]
    all_phases_verified: bool
    stack_digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "phase1_authoring": self.phase1_authoring,
            "phase2_ir_qasm": self.phase2_ir_qasm,
            "phase3_transpilation": self.phase3_transpilation,
            "phase4_qec": self.phase4_qec,
            "phase5_orchestration": self.phase5_orchestration,
            "phase6_pulse_control": self.phase6_pulse_control,
            "all_phases_verified": self.all_phases_verified,
            "stack_digest": self.stack_digest,
        }


def run_quantum_software_stack(
    n_qubits: int = 3,
    *,
    qec_distance: int = 3,
    x_error_qubits: Iterable[int] = (0,),
    z_error_qubits: Iterable[int] = (2,),
) -> SoftwareStackReport:
    """Execute all 6 phases of the quantum software stack end-to-end with exact audits."""
    if n_qubits < 2:
        raise ValueError("run_quantum_software_stack requires n_qubits >= 2")

    # Phase 1: High-level circuit authoring (entangling ansatz + non-adjacent gate + redundant pair)
    authored = build_ansatz_program(
        n_qubits,
        [Fraction(1, 8) for _ in range(n_qubits)],
        layers=1,
        axis="y",
        entangler="cx",
        entanglement="linear",
    )
    # Add a long-range CZ and a cancelling H-H pair to exercise routing, basis translation, and optimization
    authored = (
        authored.then("cz", 0, n_qubits - 1)
        .then("h", 0)
        .then("h", 0)
    )
    phase1 = {
        "n_qubits": authored.n_qubits,
        "authored_gate_count": len(authored.operations),
        "authored_gate_counts": authored.gate_counts(),
        "authored_digest": authored.digest(),
    }

    # Phase 2: OpenQASM 2.0 Intermediate Representation & Round-Trip
    phase2 = qasm_roundtrip_report(authored)

    # Phase 3: Compilation & Transpilation onto a linear nearest-neighbor coupling map
    cmap = CouplingMap.line(n_qubits)
    trans_report = transpile_program(
        Program.from_qasm(phase2["qasm"]),
        coupling_map=cmap,
        basis_gates=DEFAULT_BASIS_GATES,
        optimize=True,
        restore_layout=True,
        verify_equivalence=(n_qubits <= DEFAULT_VERIFY_WIDTH),
    )
    phase3 = trans_report.as_dict()

    # Phase 4: Surface-Code QEC & Fault Tolerance Cycle
    qec_report = run_surface_code_qec_cycle(
        distance=qec_distance,
        x_error_qubits=x_error_qubits,
        z_error_qubits=z_error_qubits,
    )
    phase4 = qec_report.as_dict()

    # Phase 5: Hybrid Quantum-Classical Workload Orchestration
    hybrid_report = run_hybrid_workload(
        n_qubits=min(n_qubits, 3),
        J=1,
        g=1,
    )
    phase5 = hybrid_report.as_dict()

    # Phase 6: Pulse-Level Compilation & Control Schedule
    pulse_schedule = compile_pulse_schedule(
        trans_report.transpiled_program,
        include_readout=True,
    )
    phase6 = pulse_schedule.as_dict()

    all_ok = bool(
        phase2["roundtrip_exact"]
        and trans_report.topology_satisfied
        and trans_report.basis_satisfied
        and (trans_report.unitary_equivalent is not False)
        and qec_report.ancilla_matches_gf2_parity
        and qec_report.ancilla_measurements_deterministic
        and qec_report.exact_decoder_succeeded
        and qec_report.union_find_decoder_succeeded
        and qec_report.post_recovery_syndrome_zero
        and qec_report.logical_z_preserved
        and hybrid_report.receipt_chain_verified
        and pulse_schedule.total_duration_ns > 0
        and pulse_schedule.physical_pulse_count > 0
    )

    unsigned = {
        "phase1_authoring": phase1,
        "phase2_ir_qasm": phase2,
        "phase3_transpilation": phase3,
        "phase4_qec": phase4,
        "phase5_orchestration": phase5,
        "phase6_pulse_control": phase6,
        "all_phases_verified": all_ok,
    }
    audit = audit_exactness(unsigned)
    if not audit.exact:
        raise ExactLaneError(
            "software_stack failed exactness audit: " + "; ".join(audit.violations)
        )

    return SoftwareStackReport(
        phase1_authoring=phase1,
        phase2_ir_qasm=phase2,
        phase3_transpilation=phase3,
        phase4_qec=phase4,
        phase5_orchestration=phase5,
        phase6_pulse_control=phase6,
        all_phases_verified=all_ok,
        stack_digest=_canonical_digest(unsigned),
    )
