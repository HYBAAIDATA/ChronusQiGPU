"""
PYTHAGORAS — CIRCUIT DOMAIN
Quantum/classical circuit evolution domain.

- Representation: OPENQASM 2.0 subset source / parsed circuit record.
- Coherence: gate coherence — entanglement balance, depth efficiency
  (parallelism), and register coverage, φ-composed.
- CGP primitives: merge_gates, commute_gates, cancel_gates, reorder_gates.
- Mutation primitives: ADD:Gate, ADD:Ancilla, REFACTOR:Cancel,
  REFACTOR:Merge, ADVERSARIAL:Perturb.
- Tests: structural validity plus exact unitarity verification
  (U†U = I) for circuits of up to 4 qubits; structural unitarity
  (all ops drawn from the unitary gate set) beyond that.
- Features: the abstract 8-dimensional basis instantiated on circuits.

No external quantum SDK is required; the parser and the unitary builder are
substrate-agnostic linear algebra over ℂ (see AGENTS.md §1).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

import numpy as np

from ..domain import Domain, MutationPrimitive, WeightedPrimitive
from ..phi_resonance import PHI


# =============================================================================
# Gate set
# =============================================================================

_ONE_QUBIT_FIXED = {"h", "x", "y", "z", "s", "t", "id"}
_ONE_QUBIT_PARAM = {"rx", "ry", "rz"}
_TWO_QUBIT = {"cx", "cz", "swap"}
_SELF_INVERSE = {"h", "x", "y", "z", "cx", "cz", "swap"}
_UNITARY_GATES = _ONE_QUBIT_FIXED | _ONE_QUBIT_PARAM | _TWO_QUBIT
_NON_UNITARY = {"measure", "barrier"}


def _gate_matrix_1q(name: str, params: List[float]) -> np.ndarray:
    """Exact 2x2 unitary for a single-qubit gate."""
    if name == "h":
        return np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2.0)
    if name == "x":
        return np.array([[0, 1], [1, 0]], dtype=complex)
    if name == "y":
        return np.array([[0, -1j], [1j, 0]], dtype=complex)
    if name == "z":
        return np.array([[1, 0], [0, -1]], dtype=complex)
    if name == "s":
        return np.array([[1, 0], [0, 1j]], dtype=complex)
    if name == "t":
        return np.array([[1, 0], [0, np.exp(1j * math.pi / 4.0)]], dtype=complex)
    if name == "id":
        return np.eye(2, dtype=complex)

    theta = float(params[0]) if params else 0.0
    c = math.cos(theta / 2.0)
    s = math.sin(theta / 2.0)
    if name == "rx":
        return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
    if name == "ry":
        return np.array([[c, -s], [s, c]], dtype=complex)
    if name == "rz":
        return np.array(
            [[np.exp(-1j * theta / 2.0), 0], [0, np.exp(1j * theta / 2.0)]],
            dtype=complex,
        )
    raise ValueError(f"unknown 1q gate: {name}")


def _lift_1q(g: np.ndarray, qubit: int, n_qubits: int) -> np.ndarray:
    """Lift a 2x2 gate to the full 2^n space (little-endian qubit order)."""
    ident = np.eye(2, dtype=complex)
    pos = n_qubits - 1 - qubit
    factors = [g if i == pos else ident for i in range(n_qubits)]
    u = factors[0]
    for f in factors[1:]:
        u = np.kron(u, f)
    return u


def _two_qubit_matrix(name: str, qa: int, qb: int, n_qubits: int) -> np.ndarray:
    """Exact 2^n x 2^n matrix for cx/cz/swap on little-endian qubits."""
    dim = 1 << n_qubits
    if name == "cz":
        u = np.eye(dim, dtype=complex)
        for b in range(dim):
            if (b >> qa) & 1 and (b >> qb) & 1:
                u[b, b] = -1.0
        return u

    u = np.zeros((dim, dim), dtype=complex)
    for b in range(dim):
        out = b
        if name == "cx":
            if (b >> qa) & 1:
                out = b ^ (1 << qb)
        elif name == "swap":
            bit_a = (b >> qa) & 1
            bit_b = (b >> qb) & 1
            out = b & ~(1 << qa) & ~(1 << qb) | (bit_a << qb) | (bit_b << qa)
        else:
            raise ValueError(f"unknown 2q gate: {name}")
        u[out, b] = 1.0
    return u


def _circuit_unitary(rep: Dict[str, Any]) -> np.ndarray:
    """Compose the exact unitary of all unitary ops in execution order."""
    n = rep["qubits"]
    u = np.eye(1 << n, dtype=complex)
    for op in rep["ops"]:
        name = op["gate"]
        if name in _NON_UNITARY:
            continue
        qs = op["qubits"]
        if name in _ONE_QUBIT_FIXED or name in _ONE_QUBIT_PARAM:
            g = _lift_1q(_gate_matrix_1q(name, op["params"]), qs[0], n)
        else:
            g = _two_qubit_matrix(name, qs[0], qs[1], n)
        u = g @ u
    return u


def _circuit_depth(rep: Dict[str, Any]) -> int:
    """Greedy layer depth: each op lands on the earliest layer freeing its qubits."""
    last_layer: Dict[int, int] = {}
    depth = 0
    for op in rep["ops"]:
        qs = op["qubits"] if op["gate"] != "barrier" else list(range(rep["qubits"]))
        layer = max((last_layer.get(q, -1) for q in qs), default=-1) + 1
        for q in qs:
            last_layer[q] = layer
        depth = max(depth, layer + 1)
    return depth


# =============================================================================
# Parsing / serialization (OPENQASM 2.0 subset)
# =============================================================================

_QREG_RE = re.compile(r"^qreg\s+(\w+)\[(\d+)\];?$")
_CREG_RE = re.compile(r"^creg\s+(\w+)\[(\d+)\];?$")
_MEASURE_RE = re.compile(r"^measure\s+(\w+)\[(\d+)\]\s*->\s*(\w+)\[(\d+)\];?$")
_GATE_RE = re.compile(r"^(\w+)(?:\(([^)]*)\))?\s+(.+);?$")


def _parse_qargs(args_text: str, n_qubits: int) -> List[int]:
    """Parse 'q[0],q[1]' or 'q' (whole register) into qubit indices."""
    out: List[int] = []
    for part in args_text.split(","):
        part = part.strip()
        m = re.match(r"^(\w+)\[(\d+)\]$", part)
        if m:
            out.append(int(m.group(2)))
        elif re.match(r"^\w+$", part):
            out.extend(range(n_qubits))
        else:
            raise ValueError(f"malformed qubit argument: {part}")
    return out


def _parse_circuit(source: str) -> Dict[str, Any]:
    qubits = 0
    clbits = 0
    ops: List[Dict[str, Any]] = []

    for raw in source.splitlines():
        line = raw.split("//")[0].strip()
        if not line or line.startswith("OPENQASM") or line.startswith("include"):
            continue

        m = _QREG_RE.match(line)
        if m:
            qubits += int(m.group(2))
            continue
        m = _CREG_RE.match(line)
        if m:
            clbits += int(m.group(2))
            continue
        m = _MEASURE_RE.match(line)
        if m:
            ops.append(
                {
                    "gate": "measure",
                    "qubits": [int(m.group(2))],
                    "clbits": [int(m.group(4))],
                    "params": [],
                }
            )
            continue
        if line.startswith("barrier"):
            ops.append({"gate": "barrier", "qubits": [], "clbits": [], "params": []})
            continue

        m = _GATE_RE.match(line)
        if not m:
            raise ValueError(f"unparseable line: {line}")
        name = m.group(1).lower()
        params = []
        if m.group(2):
            params = [float(p) for p in m.group(2).split(",")]
        qs = _parse_qargs(m.group(3), qubits)
        if name not in _UNITARY_GATES:
            raise ValueError(f"unknown gate: {name}")
        arity = 2 if name in _TWO_QUBIT else 1
        if len(qs) != arity:
            raise ValueError(f"gate {name} expects {arity} qubits, got {len(qs)}")
        ops.append({"gate": name, "qubits": qs, "clbits": [], "params": params})

    if qubits <= 0:
        raise ValueError("circuit declares no qreg")

    for op in ops:
        for q in op["qubits"]:
            if q < 0 or q >= qubits:
                raise ValueError(f"qubit index {q} out of range ({qubits})")
        for c in op["clbits"]:
            if c < 0 or c >= max(1, clbits):
                raise ValueError(f"clbit index {c} out of range ({clbits})")

    return {"qubits": qubits, "clbits": clbits, "ops": ops}


def _unparse_circuit(rep: Dict[str, Any]) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    lines.append(f"qreg q[{rep['qubits']}];")
    if rep["clbits"]:
        lines.append(f"creg c[{rep['clbits']}];")
    for op in rep["ops"]:
        name = op["gate"]
        if name == "barrier":
            lines.append("barrier q;")
            continue
        if name == "measure":
            lines.append(f"measure q[{op['qubits'][0]}] -> c[{op['clbits'][0]}];")
            continue
        param_str = ""
        if op["params"]:
            param_str = "(" + ",".join(f"{p:.6g}" for p in op["params"]) + ")"
        qargs = ",".join(f"q[{q}]" for q in op["qubits"])
        lines.append(f"{name}{param_str} {qargs};")
    return "\n".join(lines) + "\n"


def _transform(source: str, fn) -> str:
    """Parse -> mutate rep -> unparse, failing safely to the input."""
    try:
        rep = _parse_circuit(source)
        rep = fn(rep)
        return _unparse_circuit(rep)
    except Exception:
        return source


# =============================================================================
# CGP-layer primitives
# =============================================================================

def _op_signature(op: Dict[str, Any]) -> Tuple:
    return (op["gate"], tuple(op["qubits"]), tuple(round(p, 9) for p in op["params"]))


def prim_merge_gates(source: str, weight: float) -> str:
    """Merge adjacent same-qubit rotation gates: rx(a);rx(b) -> rx(a+b)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        ops: List[Dict[str, Any]] = []
        for op in rep["ops"]:
            if (
                ops
                and op["gate"] in _ONE_QUBIT_PARAM
                and ops[-1]["gate"] == op["gate"]
                and ops[-1]["qubits"] == op["qubits"]
            ):
                ops[-1]["params"] = [ops[-1]["params"][0] + op["params"][0]]
            else:
                ops.append(dict(op, qubits=list(op["qubits"]), params=list(op["params"])))
        rep["ops"] = ops
        return rep

    return _transform(source, go)


def prim_commute_gates(source: str, weight: float) -> str:
    """Commute the first adjacent pair acting on disjoint qubit sets."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        ops = rep["ops"]
        for i in range(len(ops) - 1):
            a, b = ops[i], ops[i + 1]
            if a["gate"] in _NON_UNITARY or b["gate"] in _NON_UNITARY:
                continue
            if not set(a["qubits"]) & set(b["qubits"]):
                ops[i], ops[i + 1] = b, a
                break
        return rep

    return _transform(source, go)


def prim_cancel_gates(source: str, weight: float) -> str:
    """Cancel adjacent self-inverse gate pairs (h h, x x, cx cx, ...)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        ops: List[Dict[str, Any]] = []
        for op in rep["ops"]:
            if op["gate"] == "id":
                continue
            if (
                ops
                and op["gate"] in _SELF_INVERSE
                and _op_signature(ops[-1]) == _op_signature(op)
            ):
                ops.pop()
                continue
            ops.append(dict(op, qubits=list(op["qubits"]), params=list(op["params"])))
        rep["ops"] = ops
        return rep

    return _transform(source, go)


def prim_reorder_gates(source: str, weight: float) -> str:
    """Canonical reorder: hoist all measurements to the end of the circuit."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        unitary = [op for op in rep["ops"] if op["gate"] != "measure"]
        measured = [op for op in rep["ops"] if op["gate"] == "measure"]
        rep["ops"] = unitary + measured
        return rep

    return _transform(source, go)


# =============================================================================
# Mutation-layer primitives
# =============================================================================

def _least_used_qubit(rep: Dict[str, Any]) -> int:
    counts = [0] * rep["qubits"]
    for op in rep["ops"]:
        for q in op["qubits"]:
            counts[q] += 1
    return int(np.argmin(counts))


def _insert_before_measure(rep: Dict[str, Any], op: Dict[str, Any]) -> Dict[str, Any]:
    idx = len(rep["ops"])
    for i, existing in enumerate(rep["ops"]):
        if existing["gate"] == "measure":
            idx = i
            break
    rep["ops"].insert(idx, op)
    return rep


def mut_add_gate(source: str) -> str:
    """ADD:Gate — append an h gate on the least-used qubit."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        q = _least_used_qubit(rep)
        return _insert_before_measure(
            rep, {"gate": "h", "qubits": [q], "clbits": [], "params": []}
        )

    return _transform(source, go)


def mut_add_ancilla(source: str) -> str:
    """ADD:Ancilla — append a parameterized ry on the least-used qubit."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        q = _least_used_qubit(rep)
        return _insert_before_measure(
            rep, {"gate": "ry", "qubits": [q], "clbits": [], "params": [PHI]}
        )

    return _transform(source, go)


def mut_cancel(source: str) -> str:
    """REFACTOR:Cancel — remove self-inverse pairs."""
    return prim_cancel_gates(source, 1.0)


def mut_merge(source: str) -> str:
    """REFACTOR:Merge — merge adjacent rotations."""
    return prim_merge_gates(source, 1.0)


def mut_adversarial(source: str) -> str:
    """ADVERSARIAL:Perturb — duplicate the first unitary op (redundancy injection)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        for i, op in enumerate(rep["ops"]):
            if op["gate"] in _UNITARY_GATES:
                dup = dict(op, qubits=list(op["qubits"]), params=list(op["params"]))
                rep["ops"].insert(i, dup)
                break
        return rep

    return _transform(source, go)


# =============================================================================
# The Circuit Domain
# =============================================================================

class CircuitDomain(Domain):
    """
    CircuitDomain: quantum/classical circuit evolution.

    Optimizes gate coherence — the structural resonance of a circuit's
    entanglement balance, depth efficiency, and register coverage.
    """

    name = "circuit"
    file_extensions = (".qasm", ".qasm2", ".qc")

    #: Maximum qubit count for exact unitarity verification (2^n matrix).
    max_exact_qubits = 4

    def __init__(self):
        self._primitives: Dict[str, WeightedPrimitive] = {
            "merge_gates": prim_merge_gates,
            "commute_gates": prim_commute_gates,
            "cancel_gates": prim_cancel_gates,
            "reorder_gates": prim_reorder_gates,
        }
        self._mutation_primitives: Dict[str, MutationPrimitive] = {
            "ADD:Gate": mut_add_gate,
            "ADD:Ancilla": mut_add_ancilla,
            "REFACTOR:Cancel": mut_cancel,
            "REFACTOR:Merge": mut_merge,
            "ADVERSARIAL:Perturb": mut_adversarial,
        }
        self._mutation_weights: Dict[str, float] = {
            "ADD:Gate": 0.500,
            "ADD:Ancilla": 0.400,
            "REFACTOR:Cancel": 0.600,
            "REFACTOR:Merge": 0.550,
            "ADVERSARIAL:Perturb": 0.100,
        }

    # -- representation -----------------------------------------------------

    def parse(self, source: str) -> Dict[str, Any]:
        return _parse_circuit(source)

    def unparse(self, rep: Dict[str, Any]) -> str:
        return _unparse_circuit(rep)

    def is_valid(self, source: str) -> bool:
        try:
            _parse_circuit(source)
            return True
        except Exception:
            return False

    # -- coherence ----------------------------------------------------------

    def coherence(self, source: str) -> float:
        comps = self.compute_components(source)
        return comps["composite"]

    def compute_components(self, source: str) -> Dict[str, float]:
        try:
            rep = _parse_circuit(source)
        except Exception:
            return {
                "entanglement_balance": 0.0,
                "depth_efficiency": 0.0,
                "register_coverage": 0.0,
                "composite": 0.0,
            }

        unitary_ops = [op for op in rep["ops"] if op["gate"] in _UNITARY_GATES]
        n_q = rep["qubits"]
        n_ops = len(unitary_ops)
        n_2q = sum(1 for op in unitary_ops if op["gate"] in _TWO_QUBIT)

        if n_ops == 0 or n_q == 0:
            return {
                "entanglement_balance": 0.0,
                "depth_efficiency": 0.0,
                "register_coverage": 0.0,
                "composite": 0.0,
            }

        # Component 1: entangling-op ratio proximity to 1 - φ.
        r2q = n_2q / n_ops
        entanglement_balance = max(0.0, 1.0 - abs(r2q - (1.0 - PHI)) / (1.0 - PHI))

        # Component 2: depth efficiency — ops per (depth x qubits) slot.
        depth = _circuit_depth(rep)
        depth_efficiency = min(1.0, n_ops / max(1, depth * n_q))

        # Component 3: register coverage — fraction of qubits acted upon.
        used = {q for op in unitary_ops for q in op["qubits"]}
        register_coverage = len(used) / n_q

        composite = float(
            np.clip(
                (entanglement_balance + depth_efficiency + register_coverage) / 3.0,
                0.0,
                1.0,
            )
        )
        return {
            "entanglement_balance": float(entanglement_balance),
            "depth_efficiency": float(depth_efficiency),
            "register_coverage": float(register_coverage),
            "composite": composite,
        }

    # -- primitives ---------------------------------------------------------

    def primitives(self) -> Dict[str, WeightedPrimitive]:
        return self._primitives

    def mutation_primitives(self) -> Dict[str, MutationPrimitive]:
        return self._mutation_primitives

    def mutation_weights(self) -> Dict[str, float]:
        return dict(self._mutation_weights)

    # -- tests --------------------------------------------------------------

    def tests(self, source: str) -> bool:
        """
        verify_unitarity: structural validity, unitary gate set membership,
        canonical measurement ordering, and — for n <= max_exact_qubits —
        exact numerical verification that U†U = I.
        """
        try:
            rep = _parse_circuit(source)
        except Exception:
            return False

        seen_measure = False
        for op in rep["ops"]:
            if op["gate"] == "measure":
                seen_measure = True
            elif seen_measure and op["gate"] in _UNITARY_GATES:
                return False  # unitary op after measurement violates ordering
            if op["gate"] not in _UNITARY_GATES and op["gate"] not in _NON_UNITARY:
                return False

        if rep["qubits"] > self.max_exact_qubits:
            return True  # all ops are unitary by construction

        try:
            u = _circuit_unitary(rep)
            ident = np.eye(u.shape[0], dtype=complex)
            err = float(np.linalg.norm(u.conj().T @ u - ident))
            return err < 1e-6
        except Exception:
            return False

    # -- features -----------------------------------------------------------

    def features(self, source: str) -> np.ndarray:
        """
        8-dimensional circuit feature basis:
        log op count, depth, qubits, 2q gates, param gates,
        density, 1q ratio, coherence.
        """
        try:
            rep = _parse_circuit(source)
            unitary_ops = [op for op in rep["ops"] if op["gate"] in _UNITARY_GATES]
            n_ops = len(unitary_ops)
            n_q = rep["qubits"]
            n_2q = sum(1 for op in unitary_ops if op["gate"] in _TWO_QUBIT)
            n_param = sum(1 for op in unitary_ops if op["gate"] in _ONE_QUBIT_PARAM)
            depth = _circuit_depth(rep)
            density = n_ops / max(1, depth * n_q)
            ratio_1q = (n_ops - n_2q) / max(1, n_ops)
            return np.array(
                [
                    math.log1p(len(rep["ops"])),
                    float(depth),
                    float(n_q),
                    float(n_2q),
                    float(n_param),
                    min(1.0, density),
                    ratio_1q,
                    self.coherence(source),
                ],
                dtype=float,
            )
        except Exception:
            return np.zeros(8, dtype=float)

    # -- hooks --------------------------------------------------------------

    def normalize(self, source: str) -> str:
        """Strip comments/blank lines; canonicalize header ordering."""
        try:
            rep = _parse_circuit(source)
            return _unparse_circuit(rep)
        except Exception:
            lines = [
                l.split("//")[0].strip()
                for l in source.splitlines()
                if l.split("//")[0].strip()
            ]
            return "\n".join(lines) + "\n" if lines else source

    def sample_source(self) -> str:
        return (
            "OPENQASM 2.0;\n"
            'include "qelib1.inc";\n'
            "qreg q[3];\n"
            "creg c[3];\n"
            "h q[0];\n"
            "cx q[0],q[1];\n"
            "rz(0.5) q[2];\n"
            "ry(0.618) q[1];\n"
            "cx q[1],q[2];\n"
            "measure q[0] -> c[0];\n"
            "measure q[1] -> c[1];\n"
            "measure q[2] -> c[2];\n"
        )
