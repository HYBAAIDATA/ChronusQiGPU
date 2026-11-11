"""
AL HARAS (HYBA Security): the five-qubit [[5,1,3]] stabilizer code, computed exactly.

Historical name in the product notes: "holographic quantum error correction"
(HaPPY pentagon code). One pentagon of the HaPPY {5,4} construction is a
single perfect tensor, and that tensor is the [[5,1,3]] code implemented here.
Larger tilings are not built, and no AdS/CFT or bulk/boundary physics is
simulated beyond this one tensor. Class names are kept for import
compatibility.

Classification (AGENTS.md, docs/system-update/quantum-package-taxonomy.md):
an exact classical simulation of a finite-dimensional quantum stabilizer code.
Pauli operators use GF(2) symplectic arithmetic with an exact phase in
{1, i, -1, -i}; code words are exact state vectors over the 32 basis states
with rational amplitudes. This is not TURING, not a hardware, device or noise
model, and it establishes nothing about physical fidelity.

What is computed
* Generators XZZXI, IXZZX, XIXZZ, ZXIXZ: pairwise commutation, GF(2) rank 4,
  logical operators X_L = XXXXX and Z_L = ZZZZZ (commuting with every
  generator, anticommuting with each other), and the code distance 3 by
  exhaustive search over all 4^5 Pauli operators.
* Syndromes: the 15 single-qubit errors have 15 distinct non-zero 4-bit
  syndromes (1 + 15 = 2^4: the code is perfect); decoding uses that table.
* Code words: |0_L> is the projection of |00000> onto the code space,
  normalised exactly (16 amplitudes of +-1/4); |1_L> = X_L |0_L>.
* Erasures: erased qubits are traced out exactly and the logical bit is read
  from the survivors' reduced density matrix with a logical-Z representative
  supported on the survivors. Such a representative exists iff no non-trivial
  logical operator is supported on the erased set; for this code that means at
  most 2 of the 5 qubits are erased. With 3 or more erased, the survivors'
  reduced states for |0_L> and |1_L> are computed and are identical: the
  survivors carry no information about the logical bit.
"""

import hashlib
import time
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations
from math import isqrt
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chronus.security.al_haras.cyclotomic import CyclotomicZ5

N_QUBITS = 5
FULL_MASK = (1 << N_QUBITS) - 1
GENERATOR_STRINGS: Tuple[str, ...] = ("XZZXI", "IXZZX", "XIXZZ", "ZXIXZ")
LOGICAL_X_STRING = "XXXXX"
LOGICAL_Z_STRING = "ZZZZZ"
GEOMETRY = (
    "single perfect tensor (one pentagon of the HaPPY {5,4} construction); "
    "larger tilings are not built"
)

Complex = Tuple[Fraction, Fraction]
ZERO_C: Complex = (Fraction(0), Fraction(0))
ONE_C: Complex = (Fraction(1), Fraction(0))
State = Dict[int, Complex]


def _popcount(value: int) -> int:
    return bin(value).count("1")


def _c_add(a: Complex, b: Complex) -> Complex:
    return (a[0] + b[0], a[1] + b[1])


def _c_mul(a: Complex, b: Complex) -> Complex:
    return (a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0])


def _c_conj(a: Complex) -> Complex:
    return (a[0], -a[1])


def _i_power(k: int, a: Complex) -> Complex:
    k %= 4
    if k == 0:
        return a
    if k == 1:
        return (-a[1], a[0])
    if k == 2:
        return (-a[0], -a[1])
    return (a[1], -a[0])


def _exact(value: Complex) -> Any:
    """Exact JSON-friendly form: int or 'p/q' string for real values, else a pair of strings."""
    re, im = value
    if im != 0:
        return [str(re), str(im)]
    return re.numerator if re.denominator == 1 else str(re)


def _bits(index: int) -> str:
    return "".join("1" if index >> j & 1 else "0" for j in range(N_QUBITS))


@dataclass(frozen=True)
class Pauli:
    """i^phase * X^x Z^z on five qubits; bit j of x and z acts on qubit j."""

    x: int
    z: int
    phase: int = 0

    @classmethod
    def from_string(cls, text: str) -> "Pauli":
        if len(text) != N_QUBITS:
            raise ValueError(f"Pauli strings have {N_QUBITS} characters")
        x = z = phase = 0
        for j, ch in enumerate(text):
            if ch == "X":
                x |= 1 << j
            elif ch == "Z":
                z |= 1 << j
            elif ch == "Y":
                x |= 1 << j
                z |= 1 << j
                phase += 1  # Y = i X Z
            elif ch != "I":
                raise ValueError(f"unknown Pauli letter {ch!r}")
        return cls(x, z, phase % 4)

    def __mul__(self, other: "Pauli") -> "Pauli":
        return Pauli(self.x ^ other.x, self.z ^ other.z, (self.phase + other.phase + 2 * _popcount(self.z & other.x)) % 4)

    def commutes_with(self, other: "Pauli") -> bool:
        return (_popcount(self.x & other.z) + _popcount(self.z & other.x)) % 2 == 0

    @property
    def support(self) -> int:
        return self.x | self.z

    @property
    def weight(self) -> int:
        return _popcount(self.support)

    def label(self) -> str:
        letters = []
        for j in range(N_QUBITS):
            xb, zb = self.x >> j & 1, self.z >> j & 1
            letters.append("I" if not (xb or zb) else "X" if not zb else "Z" if not xb else "Y")
        sign = {0: "+", 1: "+i", 2: "-", 3: "-i"}[(self.phase - letters.count("Y")) % 4]
        return sign + "".join(letters)

    def apply(self, state: State) -> State:
        out: State = {}
        for basis, amp in state.items():
            term = _i_power(self.phase + 2 * _popcount(self.z & basis), amp)
            key = basis ^ self.x
            out[key] = _c_add(out.get(key, ZERO_C), term)
        return {k: v for k, v in out.items() if v != ZERO_C}


def _group(generators: Sequence[Pauli]) -> List[Pauli]:
    elements = []
    for mask in range(1 << len(generators)):
        element = Pauli(0, 0, 0)
        for i, g in enumerate(generators):
            if mask >> i & 1:
                element = element * g
        elements.append(element)
    return elements


def _gf2_rank(rows: Sequence[int]) -> int:
    pivots: List[int] = []
    for row in rows:
        for p in pivots:
            row = min(row, row ^ p)
        if row:
            pivots.append(row)
    return len(pivots)


def _inner(a: State, b: State) -> Complex:
    total = ZERO_C
    for k, v in a.items():
        if k in b:
            total = _c_add(total, _c_mul(_c_conj(v), b[k]))
    return total


def reduced_density_matrix(state: State, survivors_mask: int) -> Dict[Tuple[int, int], Complex]:
    """rho_A[a, a'] = sum_e psi(a, e) conj(psi(a', e)); indices are full-width masks on A."""
    by_environment: Dict[int, List[Tuple[int, Complex]]] = {}
    for basis, amp in state.items():
        by_environment.setdefault(basis & ~survivors_mask & FULL_MASK, []).append((basis & survivors_mask, amp))
    rho: Dict[Tuple[int, int], Complex] = {}
    for entries in by_environment.values():
        for a, amp_a in entries:
            for b, amp_b in entries:
                rho[(a, b)] = _c_add(rho.get((a, b), ZERO_C), _c_mul(amp_a, _c_conj(amp_b)))
    return {k: v for k, v in rho.items() if v != ZERO_C}


def expectation_on_subsystem(rho: Dict[Tuple[int, int], Complex], operator: Pauli) -> Complex:
    """Tr(rho_A P) for a Pauli P supported inside the subsystem of rho_A."""
    total = ZERO_C
    rows = {a for a, _ in rho}
    for a in rows:
        entry = rho.get((a, a ^ operator.x), ZERO_C)
        if entry != ZERO_C:
            total = _c_add(total, _i_power(operator.phase + 2 * _popcount(operator.z & a), entry))
    return total


@dataclass
class HolographicNode:
    """A leg of the single pentagon tensor.

    ``ring_coordinate`` is the exact position of pentagon vertex i (zeta_5^i in
    Z[zeta_5]; 0 for the bulk centre). It is descriptive and is not used by the
    code computations.
    """

    node_id: str
    is_bulk: bool
    hyperbolic_depth: int
    ring_coordinate: CyclotomicZ5
    boundary_index: Optional[int] = None
    connected_neighbors: List[str] = field(default_factory=list)


class HappyTensorNetwork:
    """One perfect tensor: a bulk leg (the logical qubit) and five boundary legs (physical qubits)."""

    def __init__(self, depth: int = 1) -> None:
        if isinstance(depth, bool) or depth != 1:
            raise ValueError("only depth=1 (a single perfect tensor) is implemented")
        self.depth = depth
        self.nodes: Dict[str, HolographicNode] = {}
        self.boundary_indices: List[int] = []
        center = HolographicNode("BULK_CENTER", True, 0, CyclotomicZ5(0, 0, 0, 0))
        self.nodes[center.node_id] = center
        for i in range(N_QUBITS):
            node = HolographicNode(
                node_id=f"BOUNDARY_{i}",
                is_bulk=False,
                hyperbolic_depth=1,
                ring_coordinate=CyclotomicZ5.zeta_power(i),
                boundary_index=i,
                connected_neighbors=["BULK_CENTER"],
            )
            self.nodes[node.node_id] = node
            center.connected_neighbors.append(node.node_id)
            self.boundary_indices.append(i)


class HolographicQECEngine:
    """Exact [[5,1,3]] code: encoding, syndromes, single-error correction and erasure recovery."""

    # Symplectic (x | z) rows of the generators XZZXI, IXZZX, XIXZZ, ZXIXZ.
    STABILIZERS_X: List[List[int]] = [
        [1, 0, 0, 1, 0],
        [0, 1, 0, 0, 1],
        [1, 0, 1, 0, 0],
        [0, 1, 0, 1, 0],
    ]
    STABILIZERS_Z: List[List[int]] = [
        [0, 1, 1, 0, 0],
        [0, 0, 1, 1, 0],
        [0, 0, 0, 1, 1],
        [1, 0, 0, 0, 1],
    ]

    def __init__(self, depth: int = 1) -> None:
        self.network = HappyTensorNetwork(depth=depth)
        self.num_boundary = len(self.network.boundary_indices)
        self.generators = [Pauli.from_string(s) for s in GENERATOR_STRINGS]
        for g, xs, zs in zip(self.generators, self.STABILIZERS_X, self.STABILIZERS_Z):
            if g.x != sum(b << j for j, b in enumerate(xs)) or g.z != sum(b << j for j, b in enumerate(zs)):
                raise RuntimeError("symplectic generator table does not match the Pauli strings")
        self.stabilizer_group = _group(self.generators)
        self.logical_x = Pauli.from_string(LOGICAL_X_STRING)
        self.logical_z = Pauli.from_string(LOGICAL_Z_STRING)
        self._stabilizer_xz = {(s.x, s.z) for s in self.stabilizer_group}
        self._logicals: Optional[List[Pauli]] = None
        self._codewords = self._build_codewords()
        self._decoder = self._build_decoder()

    # -- construction --------------------------------------------------------

    def _build_codewords(self) -> Dict[int, State]:
        projected: State = {}
        for s in self.stabilizer_group:
            for basis, amp in s.apply({0: ONE_C}).items():
                projected[basis] = _c_add(projected.get(basis, ZERO_C), amp)
        projected = {k: v for k, v in projected.items() if v != ZERO_C}
        norm_sq = _inner(projected, projected)[0]
        num, den = isqrt(norm_sq.numerator), isqrt(norm_sq.denominator)
        if num * num != norm_sq.numerator or den * den != norm_sq.denominator or num == 0:
            raise RuntimeError("code-space projection has no exact rational normalisation")
        scale = Fraction(den, num)
        zero = {k: (v[0] * scale, v[1] * scale) for k, v in projected.items()}
        return {0: zero, 1: self.logical_x.apply(zero)}

    def _build_decoder(self) -> Dict[Tuple[int, ...], Pauli]:
        table: Dict[Tuple[int, ...], Pauli] = {self.syndrome(Pauli(0, 0)): Pauli(0, 0)}
        for j in range(N_QUBITS):
            for letter in "XYZ":
                error = Pauli.from_string("I" * j + letter + "I" * (N_QUBITS - j - 1))
                table.setdefault(self.syndrome(error), error)
        return table

    def logical_operators(self) -> List[Pauli]:
        """Non-trivial logical operators (one per (x, z) class, phase 0): N(S) minus S."""
        if self._logicals is None:
            found = []
            for x in range(1 << N_QUBITS):
                for z in range(1 << N_QUBITS):
                    p = Pauli(x, z)
                    if (x, z) not in self._stabilizer_xz and all(p.commutes_with(g) for g in self.generators):
                        found.append(p)
            self._logicals = found
        return list(self._logicals)

    def erasure_correctable(self, erased_mask: int) -> bool:
        """True iff no non-trivial logical operator is supported inside the erased set."""
        return not any(p.support & ~erased_mask & FULL_MASK == 0 for p in self.logical_operators())

    # -- syndromes and correction -------------------------------------------

    def syndrome(self, error: Any) -> Tuple[int, ...]:
        p = Pauli.from_string(error) if isinstance(error, str) else error
        return tuple(0 if p.commutes_with(g) else 1 for g in self.generators)

    def correct_error(self, error: Any) -> Dict[str, Any]:
        """Decode the syndrome with the single-qubit table and report the residual."""
        p = Pauli.from_string(error) if isinstance(error, str) else error
        syndrome = self.syndrome(p)
        correction = self._decoder.get(syndrome)
        if correction is None:
            return {"error": p.label(), "syndrome": list(syndrome), "correction": None, "corrected": False, "outcome": "SYNDROME_NOT_IN_TABLE"}
        residual = correction * p
        if (residual.x, residual.z) in self._stabilizer_xz:
            outcome = "CORRECTED"
        elif all(residual.commutes_with(g) for g in self.generators):
            outcome = "LOGICAL_ERROR"
        else:
            outcome = "RESIDUAL_SYNDROME"
        return {
            "error": p.label(),
            "syndrome": list(syndrome),
            "correction": correction.label(),
            "residual": residual.label(),
            "corrected": outcome == "CORRECTED",
            "outcome": outcome,
        }

    # -- encoding and erasure recovery -------------------------------------

    def codeword(self, logical_bit: int) -> State:
        if logical_bit not in (0, 1) or isinstance(logical_bit, bool):
            raise ValueError(f"Logical bit must be 0 or 1, got {logical_bit}")
        return dict(self._codewords[logical_bit])

    def encode_bulk_logical_state(self, logical_bit: int) -> Dict[str, Any]:
        """Exact |0_L> or |1_L> as amplitudes over the 32 boundary basis states."""
        start = time.perf_counter_ns()
        state = self.codeword(logical_bit)
        amplitudes = {_bits(k): (v[0] if v[1] == 0 else v) for k, v in sorted(state.items())}
        canonical = ";".join(f"{bits}:{_exact(state[k])}" for k, bits in ((k, _bits(k)) for k in sorted(state)))
        return {
            "logical_bit": logical_bit,
            "code": "[[5,1,3]] five-qubit perfect code",
            "boundary_nodes_count": self.num_boundary,
            "boundary_amplitudes": amplitudes,
            "stabilizer_expectations": [_exact(_inner(state, g.apply(state))) for g in self.generators],
            "logical_z_expectation": _exact(_inner(state, self.logical_z.apply(state))),
            "codeword_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "encoding_duration_ns": time.perf_counter_ns() - start,
            "holographic_geometry": GEOMETRY,
        }

    @staticmethod
    def _state_from_encoded(encoded_data: Dict[str, Any]) -> State:
        state: State = {}
        for bits, value in encoded_data["boundary_amplitudes"].items():
            if len(bits) != N_QUBITS or set(bits) - {"0", "1"}:
                raise ValueError(f"basis label {bits!r} is not a {N_QUBITS}-bit string")
            index = sum(1 << j for j, ch in enumerate(bits) if ch == "1")
            if isinstance(value, tuple):
                amp = (Fraction(value[0]), Fraction(value[1]))
            else:
                amp = (Fraction(value), Fraction(0))
            if amp != ZERO_C:
                state[index] = amp
        return state

    def reconstruct_bulk_state(
        self,
        encoded_data: Dict[str, Any],
        erased_boundary_indices: List[int],
    ) -> Dict[str, Any]:
        """Recover the logical bit from the surviving qubits only (see module docstring)."""
        start = time.perf_counter_ns()
        erased_mask = 0
        for index in erased_boundary_indices:
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < N_QUBITS:
                raise ValueError(f"boundary index {index!r} is not in 0..{N_QUBITS - 1}")
            erased_mask |= 1 << index
        survivors_mask = FULL_MASK & ~erased_mask
        state = self._state_from_encoded(encoded_data)
        norm = _inner(state, state)
        if norm != ONE_C:
            raise ValueError("encoded state is not normalised")
        rho = reduced_density_matrix(state, survivors_mask)

        representatives = sorted(
            (p for p in (self.logical_z * s for s in self.stabilizer_group) if p.support & ~survivors_mask & FULL_MASK == 0),
            key=lambda p: (p.weight, p.x, p.z),
        )
        result: Dict[str, Any] = {
            "surviving_count": _popcount(survivors_mask),
            "erasure_count": _popcount(erased_mask),
            "erased_indices": [j for j in range(N_QUBITS) if erased_mask >> j & 1],
            "entanglement_wedge_intact": bool(representatives),
        }
        if representatives:
            operator = representatives[0]
            value = expectation_on_subsystem(rho, operator)
            bit = 0 if value == ONE_C else 1 if value == (Fraction(-1), Fraction(0)) else None
            result.update(
                {
                    "reconstructed": bit is not None,
                    "reconstructed_logical_bit": bit,
                    "logical_operator_on_survivors": operator.label(),
                    "logical_z_expectation": _exact(value),
                    "reconstruction_status": (
                        "BULK_LOGICAL_STATE_RECONSTRUCTED_EXACT" if bit is not None else "LOGICAL_OUTCOME_NOT_DEFINITE"
                    ),
                }
            )
        else:
            rho_zero = reduced_density_matrix(self._codewords[0], survivors_mask)
            rho_one = reduced_density_matrix(self._codewords[1], survivors_mask)
            result.update(
                {
                    "reconstructed": False,
                    "reconstructed_logical_bit": None,
                    "logical_operator_on_survivors": None,
                    "survivor_state_independent_of_logical_bit": rho_zero == rho_one,
                    "reconstruction_status": "NOT_RECOVERABLE_NO_LOGICAL_OPERATOR_ON_SURVIVORS",
                }
            )
        result["reconstruction_duration_ns"] = time.perf_counter_ns() - start
        return result

    # -- self-verification ---------------------------------------------------

    def verify_code_properties(self) -> Dict[str, Any]:
        """Recompute the code's defining properties from scratch."""
        gens = self.generators
        commute = all(a.commutes_with(b) for a, b in combinations(gens, 2))
        rank = _gf2_rank([g.x | g.z << N_QUBITS for g in gens])
        logical_ok = all(self.logical_x.commutes_with(g) and self.logical_z.commutes_with(g) for g in gens)
        anticommute = not self.logical_x.commutes_with(self.logical_z)
        logicals = self.logical_operators()
        distance = min(p.weight for p in logicals)
        singles = [
            Pauli.from_string("I" * j + letter + "I" * (N_QUBITS - j - 1)) for j in range(N_QUBITS) for letter in "XYZ"
        ]
        syndromes = [self.syndrome(e) for e in singles]
        distinct = len(set(syndromes)) == len(singles) and (0,) * len(gens) not in syndromes
        perfect = len(set(syndromes)) + 1 == 1 << len(gens)
        max_erasures = 0
        for size in range(1, N_QUBITS + 1):
            if all(self.erasure_correctable(sum(1 << j for j in subset)) for subset in combinations(range(N_QUBITS), size)):
                max_erasures = size
            else:
                break
        zero, one = self._codewords[0], self._codewords[1]
        stabilized = all(g.apply(w) == w for g in gens for w in (zero, one))
        orthonormal = _inner(zero, zero) == ONE_C and _inner(one, one) == ONE_C and _inner(zero, one) == ZERO_C
        quarter = (Fraction(1, 4), Fraction(0))
        marginals_mixed = True
        for pair in combinations(range(N_QUBITS), 2):
            mask = (1 << pair[0]) | (1 << pair[1])
            expected = {(a, a): quarter for a in (0, 1 << pair[0], 1 << pair[1], mask)}
            for w in (zero, one):
                if reduced_density_matrix(w, mask) != expected:
                    marginals_mixed = False
        checks = {
            "generators_commute": commute,
            "generator_rank_gf2": rank,
            "logicals_commute_with_stabilizers": logical_ok,
            "logicals_anticommute": anticommute,
            "code_distance": distance,
            "logical_classes_count": len(logicals),
            "single_qubit_syndromes_distinct": distinct,
            "hamming_bound_saturated": perfect,
            "max_correctable_erasures": max_erasures,
            "codewords_stabilized": stabilized,
            "codewords_orthonormal": orthonormal,
            "two_qubit_marginals_maximally_mixed": marginals_mixed,
        }
        all_ok = (
            commute and rank == 4 and logical_ok and anticommute and distance == 3 and distinct
            and perfect and max_erasures == 2 and stabilized and orthonormal and marginals_mixed
        )
        checks["generators"] = list(GENERATOR_STRINGS)
        checks["status"] = "CODE_PROPERTIES_VERIFIED" if all_ok else "CODE_PROPERTY_CHECK_FAILED"
        return checks
