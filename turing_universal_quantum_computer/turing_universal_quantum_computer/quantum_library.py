"""The first-principles quantum library — one surface, exact lanes only.

This module is a *facade*, not a reimplementation: every entry point
delegates to the canonical owner (``hilbert``, ``stabilizer``,
``quantum_walk``, ``grover_exact_scale`` via ``hilbert.GroverExact``, and
the ``backends`` registry).  What it adds is the contract the substrate
thesis actually promises:

* **Exact only.**  Every family below executes in an exact
  representation — the sparse ``QuantumRegister`` over Q(zeta_8) extended
  by exact sympy cyclotomics, the Clifford tableau, the closed-form
  Grover/Q(sqrt(N)) recurrence, or the backend registry's exact lanes.
  No float statevector simulation, no approximation, no heuristic
  relabelled as quantum.  The only float anywhere is the classical
  wall-clock in ``wall_ms`` (and the seeded ``measure()`` boundary,
  which is post-quantum classical sampling of the exact distribution).

* **Angles are rational turns.**  Phases are declared as
  ``fractions.Fraction`` numbers of turns ``t`` meaning
  ``e^{2*pi*i*t}`` — the exact cyclotomic.  Denominators dividing 8 stay
  inside Q(zeta_8) as ``ExactComplex``; all other rationals become exact
  sympy cyclotomics.  An irrational angle cannot be requested — the type
  of the argument refuses it.

* **Refusal is a result.**  Where no exact lane can answer, the call
  raises ``ExactLaneError`` or the registry's own refusal — the honest
  boundary.  "Slower" is a lane-selection fact, not a property of the
  maths: stabilizer programs run exact at n = 10,000 in O(n^2) bits,
  closed-form walks evaluate at any n, and dense-register programs are
  admitted only while the amplitude support fits the declared budget.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import sympy as sp

from .hilbert import (
    ExactComplex,
    QuantumRegister,
    _e_abs2,
    _e_mul,
    _phase_factor,
    qft,
    von_neumann_entropy_exact,
)
from .quantum_walk import CoinedCycleWalk, HypercubeWalk
from .stabilizer import StabilizerState

__all__ = [
    "ExactLaneError",
    "ExactnessAuditError",
    "ExactnessReport",
    "LibraryResult",
    "QuantumLibrary",
    "TRUTH_EXACT",
    "audit_exactness",
]

TRUTH_EXACT = "exact"

_CLIFFORD_T_GATES = frozenset(
    {"i", "x", "y", "z", "h", "s", "sdg", "t", "cx", "cnot", "cz", "swap"}
)

# A bare decimal literal is the signature of a float leak in an exact
# payload (the QSqrt2->sympify defect produced "1.00000000000000").
# Exact serialisations are fractions ("15/8"), radicals ("-sqrt(5)"),
# integers, or symbolic text — never a decimal point.
_FLOAT_LITERAL = re.compile(r"^-?\d+\.\d+([eE][-+]?\d+)?$")


class ExactLaneError(ValueError):
    """A request that no exact lane can answer was refused."""


class ExactnessAuditError(ValueError):
    """An exact-labelled result contained a floating-point atom."""


@dataclass(frozen=True)
class ExactnessReport:
    """The audited exactness verdict for one payload tree."""

    exact: bool
    arithmetic_domain: str
    violations: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _expr_has_float_atom(expr: sp.Basic) -> bool:
    if isinstance(expr, sp.Float):
        return True
    return any(_expr_has_float_atom(arg) for arg in expr.args)


def _expr_domain(expr: sp.Basic) -> str:
    if expr.is_Rational or expr.is_integer:
        return "rational"
    if expr.atoms(sp.exp) or expr.atoms(sp.Function):
        return "cyclotomic"
    if expr.atoms(sp.Pow):
        return "algebraic"
    return "symbolic"


def audit_exactness(tree: Any) -> ExactnessReport:
    """Walk a payload tree and verify every numeric leaf is exact.

    Forbidden: Python ``float``, ``sp.Float`` atoms anywhere inside a
    sympy expression, and bare decimal-literal strings in value position
    (the serialised signature of a coercion leak).  ``wall_ms`` lives
    outside the payload and is the only permitted float in a result.

    Returns an :class:`ExactnessReport`; the caller decides whether a
    violation raises (the facade raises :class:`ExactnessAuditError`).
    """
    violations: List[str] = []
    domains: List[str] = []

    def walk(v: Any, path: str) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, float):
            violations.append(f"{path}: python float {v!r}")
            return
        if isinstance(v, sp.Basic):
            if _expr_has_float_atom(v):
                violations.append(f"{path}: sympy Float atom in {v!r}")
            domains.append(_expr_domain(v))
            return
        if isinstance(v, str):
            if _FLOAT_LITERAL.match(v):
                violations.append(f"{path}: decimal-literal string {v!r}")
            return
        if isinstance(v, (int, Fraction)):
            domains.append("rational")
            return
        if isinstance(v, dict):
            for k, item in v.items():
                walk(item, f"{path}.{k}")
            return
        if isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                walk(item, f"{path}[{i}]")
            return
        if hasattr(v, "to_sympy"):
            walk(v.to_sympy(), path)
            return
        # enums, backend labels, None, and other non-numeric leaves pass

    walk(tree, "payload")
    if not domains:
        domain = "label_only"
    elif any(d == "cyclotomic" for d in domains):
        domain = "cyclotomic"
    elif any(d == "algebraic" for d in domains):
        domain = "algebraic"
    elif any(d == "symbolic" for d in domains):
        domain = "symbolic"
    else:
        domain = "rational"
    return ExactnessReport(
        exact=not violations,
        arithmetic_domain=domain,
        violations=tuple(violations),
    )


def _strip_approx(tree: Any) -> Any:
    """Drop the registry's display-only ``*_approx`` leaves from a payload.

    Backend amplitude tables carry ``amplitude_approx``/``probability_approx``
    floats for human rendering.  The facade admits no float atom in an exact
    result, so those keys are removed at the boundary; the ``*_exact`` siblings
    remain the auditable evidence.  The ``state`` key — a live backend object
    for in-process callers — is likewise removed: it serialises to a
    nondeterministic ``<object at 0x…>`` repr, while ``amplitudes``, ``dirac``
    and ``norm_sq_exact`` already carry the exact state deterministically.
    """
    def keep(k: Any, v: Any) -> bool:
        if not isinstance(k, str):
            return True
        if k.endswith("_approx"):
            return False
        # ``state`` maps to a live backend object in the algebraic lane; a
        # string/bool leaf of the same name (e.g. stage labels) is kept.
        return k != "state" or isinstance(v, (str, int, bool, dict, list, tuple, type(None)))

    if isinstance(tree, dict):
        return {k: _strip_approx(v) for k, v in tree.items() if keep(k, v)}
    if isinstance(tree, list):
        return [_strip_approx(v) for v in tree]
    if isinstance(tree, tuple):
        return tuple(_strip_approx(v) for v in tree)
    return tree


@dataclass(frozen=True)
class LibraryResult:
    """One library call with the lane that executed it and its evidence.

    ``truth_class`` is ``"exact"`` for every family this facade exposes —
    and that claim is *enforced*: the payload is audited before the
    result is returned, so a float atom anywhere in the value tree raises
    :class:`ExactnessAuditError` instead of shipping an approximate
    result under an exact label.  ``wall_ms`` is classical elapsed wall
    time — measurement metadata, never a claim about the arithmetic.
    """

    family: str
    lane: str
    payload: Dict[str, Any]
    truth_class: str = TRUTH_EXACT
    wall_ms: float = 0.0
    arithmetic_domain: str = "unknown"
    lane_owner: str = ""
    sampled: bool = False

    def verify_exactness(self) -> ExactnessReport:
        """Re-audit the payload; the verifier is callable independently."""
        return audit_exactness(self.payload)

    def to_dict(self) -> Dict[str, Any]:
        """Canonical JSON-ready form for receipts and hashing.

        Sympy/algebraic values serialize as tagged exact expressions;
        non-string mapping keys are normalized to strings.  ``wall_ms``
        stays a plain float in the envelope — it is classical metadata,
        and the canonical serializer would rightly reject it inside the
        exact payload.
        """
        from .canonical_serialization import canonical_value

        def canon(v: Any) -> Any:
            if isinstance(v, dict):
                return {str(k): canon(item) for k, item in v.items()}
            if isinstance(v, (list, tuple)):
                return [canon(item) for item in v]
            if isinstance(v, sp.Basic) or hasattr(v, "to_sympy"):
                expr = v if isinstance(v, sp.Basic) else v.to_sympy()
                return {"$exact": str(expr)}
            return v

        return {
            "family": self.family,
            "lane": self.lane,
            "lane_owner": self.lane_owner,
            "truth_class": self.truth_class,
            "arithmetic_domain": self.arithmetic_domain,
            "sampled": self.sampled,
            "wall_ms": self.wall_ms,
            "payload": canonical_value(canon(self.payload)),
        }


def _now() -> float:
    return time.perf_counter()


def _timed(family: str, lane: str, fn, owner: str = "") -> LibraryResult:
    t0 = _now()
    payload = fn()
    report = audit_exactness(payload)
    if not report.exact:
        raise ExactnessAuditError(
            f"{family} result failed the exactness audit: "
            + "; ".join(report.violations)
        )
    return LibraryResult(
        family=family,
        lane=lane,
        payload=payload,
        wall_ms=(_now() - t0) * 1e3,
        arithmetic_domain=report.arithmetic_domain,
        lane_owner=owner,
    )


def _turns(value: Any, name: str) -> Fraction:
    """Validate an angle declared as a rational number of turns."""
    if isinstance(value, bool):
        raise ExactLaneError(f"{name} must be a rational number of turns")
    try:
        t = Fraction(value)
    except (TypeError, ValueError):
        raise ExactLaneError(
            f"{name}={value!r} is not a rational number of turns; "
            "exact lanes accept e^{2*pi*i*t} for t in Q only"
        ) from None
    return t


def _pauli_image(j: int, ops: Sequence[Tuple[int, str]]):
    """Return (image_index, factor) with P|j> = factor * |image>."""
    image = j
    factor = sp.Integer(1)
    for q, p in ops:
        mask = 1 << q
        if p == "x":
            image ^= mask
        elif p == "z":
            if j & mask:
                factor = -factor
        elif p == "y":
            image ^= mask
            factor *= -sp.I if (j & mask) else sp.I
        elif p == "i":
            pass
        else:
            raise ExactLaneError(f"unknown Pauli {p!r}")
    return image, factor


def pauli_expectation(
    register: QuantumRegister, ops: Sequence[Tuple[int, str]]
) -> Any:
    """Exact <psi|P|psi> for a Pauli string — signed permutation contraction.

    ``ops`` is a sequence of ``(qubit, 'x'|'y'|'z'|'i')``.  Returns a
    sympy-exact value (rational/radical/log expression, never a float).
    """
    total = sp.Integer(0)
    for j, a in register.amplitudes.items():
        image, factor = _pauli_image(j, ops)
        b = register.amplitudes.get(image)
        if b is None:
            continue
        total += factor * sp.conjugate(_amp_sympy(b)) * _amp_sympy(a)
    return sp.simplify(total)


def _amp_sympy(v):
    return v.to_sympy() if hasattr(v, "to_sympy") else v


def _real_exact(v):
    """Reduce an exact probability/energy value to a comparable real form.

    Cyclotomic amplitudes expand to exp(i*theta) products whose modulus
    squares are real by construction but only become orderable once the
    exponentials are split into trig and simplified.  This stays exact
    throughout — the result is a sympy algebraic number, never a Float.
    """
    return sp.simplify(sp.expand_complex(sp.sympify(_amp_sympy(v))))


def _apply_prep(reg: QuantumRegister, ops: Sequence[Tuple]) -> None:
    """Apply an ansatz/prep operation list to the exact register.

    Supported ops (all exact on this register):
      ("h"|"x"|"z"|"s"|"t", q)
      ("cnot", c, t)
      ("phase", q, turns)   turns: Fraction -> exact cyclotomic e^{2*pi*i*t}
      ("mixer", q, turns)   H . P(turns) . H  ==  e^{-i*pi*t*X} up to a
                            physically irrelevant global phase e^{i*pi*t}
    """
    for op in ops:
        name = op[0]
        if name in ("h", "x", "z", "s", "t", "sdg"):
            if name == "sdg":
                for _ in range(3):
                    reg.apply_s(op[1])
            else:
                getattr(reg, f"apply_{name}")(op[1])
        elif name == "cnot":
            reg.apply_cnot(op[1], op[2])
        elif name == "phase":
            reg.apply_phase(op[1], _turns(op[2], "phase turns"))
        elif name == "mixer":
            t = _turns(op[2], "mixer turns")
            reg.apply_h(op[1])
            reg.apply_phase(op[1], t)
            reg.apply_h(op[1])
        elif name == "yrot":
            # e^{-i*pi*t*Y} up to global phase: S . H . P(t) . H . Sdg
            t = _turns(op[2], "yrot turns")
            reg.apply_s(op[1])
            reg.apply_h(op[1])
            reg.apply_phase(op[1], t)
            reg.apply_h(op[1])
            for _ in range(3):
                reg.apply_s(op[1])
        else:
            raise ExactLaneError(
                f"prep op {name!r} is outside the exact gate set"
            )


class QuantumLibrary:
    """One import surface for the exact quantum library.

    Every method returns a :class:`LibraryResult` recording the family,
    the exact lane that executed, and measured wall time.  Nothing here
    simulates; if a call cannot be answered exactly it raises.
    """

    # ------------------------------------------------------------------
    # catalogue
    # ------------------------------------------------------------------

    @staticmethod
    def catalog() -> Dict[str, Dict[str, str]]:
        """The families this library exposes, their owner, and their lane."""
        return {
            "entanglement": {
                "owner": "stabilizer.StabilizerState + hilbert.von_neumann_entropy_exact",
                "lane": "clifford_tableau / exact_register",
                "scale": "exact at arbitrary n (GHZ verified to n=10000)",
            },
            "quantum_walk": {
                "owner": "quantum_walk.CoinedCycleWalk / HypercubeWalk",
                "lane": "exact_register / closed_form",
                "scale": "cycle: sparse-exact; hypercube: symbolic any n",
            },
            "grover": {
                "owner": "hilbert.GroverExact",
                "lane": "closed_form Q(sqrt(N)) amplitudes",
                "scale": "any n; no state materialised",
            },
            "qpe": {
                "owner": "hilbert.QuantumRegister + qft",
                "lane": "exact_register cyclotomic",
                "scale": "counting register bounded by amplitude budget",
            },
            "qaoa": {
                "owner": "hilbert.QuantumRegister (rational-turn angles)",
                "lane": "exact_register cyclotomic",
                "scale": "bounded dense; refuses beyond amplitude budget",
            },
            "vqe": {
                "owner": "pauli_expectation + sympy diagonalization",
                "lane": "exact_register cyclotomic",
                "scale": "bounded dense; refuses beyond amplitude budget",
            },
            "execute": {
                "owner": "backends.execute (registry)",
                "lane": "exact_algebraic | stabilizer | sparse | mps_exact | closed_form",
                "scale": "fail-closed admission per lane",
            },
        }

    @staticmethod
    def lanes() -> List[Dict[str, Any]]:
        """Live capability matrix of the exact backend lanes."""
        from .backends import backend_matrix

        return backend_matrix()

    # ------------------------------------------------------------------
    # entanglement — Clifford tableau lane, exact at arbitrary n
    # ------------------------------------------------------------------

    @staticmethod
    def bell_pair() -> LibraryResult:
        """(H on q0, CNOT 0->1) on the tableau; entropy across 0|1 is 1 e-bit."""

        def run():
            s = StabilizerState.basis(2).h(0).cnot(0, 1)
            return {
                "stabilizers": s.stabilizer_strings(),
                "entropy_ebits": s.entanglement_entropy({0}),
            }

        return _timed("entanglement", "clifford_tableau", run, owner="stabilizer.StabilizerState")

    @staticmethod
    def ghz(n_qubits: int, subset: Iterable[int] = (0,)) -> LibraryResult:
        """GHZ_n on the stabilizer tableau — exact at n=10,000.

        Returns the exact entanglement entropy across ``subset``|rest in
        e-bits (exactly 1 for any proper nonempty subset).
        """
        if not isinstance(n_qubits, int) or n_qubits < 2:
            raise ExactLaneError("ghz requires n_qubits >= 2")
        sub = set(subset)

        def run():
            s = StabilizerState.ghz(n_qubits)
            return {
                "n_qubits": n_qubits,
                "entropy_ebits": s.entanglement_entropy(sub),
                "stabilizers": s.stabilizer_strings() if n_qubits <= 8 else None,
            }

        return _timed("entanglement", "clifford_tableau", run, owner="stabilizer.StabilizerState")

    @staticmethod
    def entanglement_entropy(
        n_qubits: int,
        ops: Sequence[Tuple],
        subset: Iterable[int],
    ) -> LibraryResult:
        """Exact von Neumann entropy of a prepared state.

        Clifford-only op lists take the tableau lane at any n; op lists
        containing ``t``/``phase``/``mixer`` take the exact register lane
        (bounded support) and a sympy-symbolic eigenspectrum.
        """
        clifford_only = all(
            op[0] in _CLIFFORD_T_GATES and op[0] != "t" for op in ops
        )
        sub = set(subset)

        def run():
            if clifford_only:
                s = StabilizerState.basis(n_qubits)
                for op in ops:
                    name = op[0]
                    if name == "sdg":
                        s = s.s(op[1]).s(op[1]).s(op[1])
                    elif name in ("cx", "cnot"):
                        s = s.cnot(op[1], op[2])
                    else:
                        s = getattr(s, name)(op[1]) if len(op) > 1 else s
                return {
                    "entropy": s.entanglement_entropy(sub),
                    "units": "e-bits (exact integer)",
                }
            reg = QuantumRegister(n_qubits)
            _apply_prep(reg, ops)
            return {
                "entropy": str(von_neumann_entropy_exact(reg, sub)),
                "units": "bits (exact symbolic)",
            }

        lane = "clifford_tableau" if clifford_only else "exact_register"
        return _timed("entanglement", lane, run, owner="stabilizer.StabilizerState/hilbert.von_neumann_entropy_exact")

    # ------------------------------------------------------------------
    # quantum walks — exact register (cycle) and closed form (hypercube)
    # ------------------------------------------------------------------

    @staticmethod
    def quantum_walk_cycle(
        num_positions: int, steps: int, start: Optional[int] = None
    ) -> LibraryResult:
        """Hadamard-coin walk on a cycle — exact distribution and variance."""

        def run():
            w = CoinedCycleWalk(num_positions, start=start).run(steps)
            return {
                "distribution": {
                    k: str(sp.simplify(_amp_sympy(v)))
                    for k, v in w.position_distribution().items()
                },
                "variance": str(sp.simplify(_amp_sympy(w.variance()))),
            }

        return _timed("quantum_walk", "exact_register", run, owner="quantum_walk.CoinedCycleWalk")

    @staticmethod
    def quantum_walk_hypercube(n_qubits: int, t) -> LibraryResult:
        """Continuous-time walk on the n-cube — exact closed form at any n."""

        def run():
            w = HypercubeWalk(n_qubits)
            return {
                "hamming_distribution": w.hamming_distribution(t),
                "expected_hamming_weight": str(w.expected_hamming_weight(t)),
                "hamming_variance": str(w.hamming_variance(t)),
            }

        return _timed("quantum_walk", "closed_form", run, owner="quantum_walk.HypercubeWalk")

    # ------------------------------------------------------------------
    # Grover — closed-form exact amplitudes in Q(sqrt(N))
    # ------------------------------------------------------------------

    @staticmethod
    def grover(
        n_qubits: int, marked: int, iterations: Optional[int] = None
    ) -> LibraryResult:
        """Exact amplitude amplification; amplitudes are exact elements of Q(sqrt(N))."""

        def run():
            from .hilbert import GroverExact

            g = GroverExact(n_qubits, marked)
            k = g.optimal_iterations() if iterations is None else int(iterations)
            a, b = g.iterate(k)
            pa, pb = a.square(), b.square()
            return {
                "n_qubits": n_qubits,
                "marked": marked,
                "iterations": k,
                "marked_amplitude": str(a),
                "marked_probability": pa.to_sympy(),
                "total_marked_probability": pa.to_sympy(),
                "unmarked_probability_each": pb.to_sympy(),
            }

        return _timed("grover", "closed_form", run, owner="hilbert.GroverExact")

    # ------------------------------------------------------------------
    # QPE — exact circuit lane (register + exact inverse QFT)
    # ------------------------------------------------------------------

    @staticmethod
    def qpe(phase_turns: Any, counting_qubits: int = 3) -> LibraryResult:
        """Exact phase estimation of U|1> = e^{2*pi*i*phi}|1>.

        ``phase_turns`` is the eigenphase phi as a rational number of
        turns (Fraction).  The counting register gets H^c, then for each
        counting qubit j a controlled U^{2^j} — an exact cyclotomic
        diagonal — followed by the exact inverse QFT on the counting
        register.  Returns the exact Born distribution over readouts and
        the argmax phase estimate index/2^c.  When phi*2^c is an integer
        the readout concentrates exactly (probability 1).
        """
        phi = _turns(phase_turns, "phase_turns")
        if not isinstance(counting_qubits, int) or counting_qubits < 1:
            raise ExactLaneError("counting_qubits must be >= 1")
        c = counting_qubits
        target = c

        def run():
            reg = QuantumRegister(c + 1)
            for q in range(c):
                reg.apply_h(q)
            reg.apply_x(target)  # eigenstate |1>
            # controlled-U^{2^j}: exact diagonal factor e^{2*pi*i*2^j*phi}
            # applied to amplitudes carrying counting-bit j AND target bit.
            factors = {
                j: _phase_factor((Fraction(1 << j) * phi))
                for j in range(c)
            }
            tmask = 1 << target
            new: Dict[int, Any] = {}
            for idx, amp in reg.amplitudes.items():
                acc = amp
                if idx & tmask:
                    for j in range(c):
                        if idx & (1 << j):
                            acc = _e_mul(acc, factors[j])
                new[idx] = acc
            reg.amplitudes = new
            qft(reg, tuple(range(c)), inverse=True)
            dist = reg.distribution()
            counting_probs: Dict[int, Any] = {}
            for idx, p in dist.items():
                key = idx & ((1 << c) - 1)
                counting_probs[key] = _real_exact(
                    counting_probs.get(key, 0) + _amp_sympy(p)
                )
            best = max(counting_probs, key=lambda k: counting_probs[k])
            return {
                "phase_turns": str(phi),
                "counting_qubits": c,
                "readout_distribution": {
                    str(k): str(sp.simplify(v)) for k, v in sorted(counting_probs.items())
                },
                "estimated_phase": str(Fraction(best, 1 << c)),
                "readout_probability": str(sp.simplify(counting_probs[best])),
                "exact_dyadic": (phi * (1 << c)).denominator == 1,
            }

        return _timed("qpe", "exact_register_cyclotomic", run, owner="hilbert.QuantumRegister+qft")

    # ------------------------------------------------------------------
    # QAOA — exact MaxCut over rational-turn angles
    # ------------------------------------------------------------------

    @staticmethod
    def _qaoa_state(n_qubits: int, edges, layers) -> QuantumRegister:
        reg = QuantumRegister(n_qubits)
        for q in range(n_qubits):
            reg.apply_h(q)
        edge_list = [(int(u), int(v)) for u, v in edges]
        for gamma, beta in layers:
            # cost layer: |x> -> e^{2*pi*i*gamma*C(x)} |x>, C(x) = cut size
            costs: Dict[int, int] = {}
            for idx in reg.amplitudes:
                c = sum(((idx >> u) ^ (idx >> v)) & 1 for u, v in edge_list)
                costs.setdefault(c, c)
            factors = {c: _phase_factor(gamma * c) for c in costs}
            reg.amplitudes = {
                idx: _e_mul(
                    amp,
                    factors[
                        sum(((idx >> u) ^ (idx >> v)) & 1 for u, v in edge_list)
                    ],
                )
                for idx, amp in reg.amplitudes.items()
            }
            # mixer layer: per qubit H . P(beta) . H  ==  e^{-i*pi*beta*X}
            for q in range(n_qubits):
                reg.apply_h(q)
                reg.apply_phase(q, beta)
                reg.apply_h(q)
        return reg

    @staticmethod
    def qaoa_maxcut(
        edges: Sequence[Sequence[int]],
        layers: Sequence[Tuple[Any, Any]],
    ) -> LibraryResult:
        """Exact QAOA MaxCut state for declared rational-turn angles.

        ``layers`` is a sequence of ``(gamma_turns, beta_turns)`` —
        fractions of a turn.  The cost layer multiplies each basis
        amplitude by e^{2*pi*i*gamma*C(x)} exactly; the mixer layer is
        H.P(beta).H per qubit, which is e^{-i*pi*beta*X} up to global
        phase.  Returns the exact Born distribution aggregated by cut
        value plus the argmax bitstring.
        """
        parsed = [(int(u), int(v)) for u, v in edges]
        if not parsed or any(u == v or u < 0 or v < 0 for u, v in parsed):
            raise ExactLaneError("edges must be distinct non-negative pairs")
        n_qubits = max(max(u, v) for u, v in parsed) + 1
        parsed_layers = [
            (_turns(g, "gamma_turns"), _turns(b, "beta_turns"))
            for g, b in layers
        ]
        if not parsed_layers:
            raise ExactLaneError("at least one (gamma, beta) layer is required")

        def run():
            reg = QuantumLibrary._qaoa_state(n_qubits, parsed, parsed_layers)
            dist = reg.distribution(include_zeros=True)
            costs = {
                i: sum(((i >> u) ^ (i >> v)) & 1 for u, v in parsed)
                for i in range(reg.dim)
            }
            by_cut: Dict[int, Any] = {}
            expected = sp.Integer(0)
            real_dist = {i: _real_exact(p) for i, p in dist.items()}
            for i, pv in real_dist.items():
                by_cut[costs[i]] = by_cut.get(costs[i], 0) + pv
                expected += pv * costs[i]
            best_state = max(real_dist, key=lambda i: real_dist[i])
            return {
                "n_qubits": n_qubits,
                "edges": parsed,
                "layers": [(str(g), str(b)) for g, b in parsed_layers],
                "optimal_cut": max(costs.values()),
                "expected_cut": str(sp.simplify(expected)),
                "probability_by_cut": {
                    k: str(sp.simplify(v)) for k, v in sorted(by_cut.items())
                },
                "argmax_state": best_state,
                "argmax_state_cut": costs[best_state],
                "argmax_state_probability": str(
                    sp.simplify(real_dist[best_state])
                ),
            }

        return _timed("qaoa", "exact_register_cyclotomic", run, owner="hilbert.QuantumRegister")

    @staticmethod
    def qaoa_maxcut_grid(
        edges: Sequence[Sequence[int]],
        p_layers: int = 1,
        grid: int = 8,
    ) -> LibraryResult:
        """Layer-wise exact sweep of a declared rational-turn grid.

        For each layer the (gamma, beta) pair is chosen by exact
        argmax of the expected cut over ``grid`` x ``grid`` candidates
        in {j/grid : j = 0..grid-1} turns.  The sweep is deterministic
        classical bookkeeping over exact evaluations — no floats in the
        quantum part.
        """
        if grid < 2:
            raise ExactLaneError("grid must be >= 2")
        parsed = [(int(u), int(v)) for u, v in edges]
        n_qubits = max(max(u, v) for u, v in parsed) + 1
        candidates = [Fraction(j, grid) for j in range(grid)]

        def run():
            chosen: List[Tuple[Fraction, Fraction]] = []
            history = []
            for _ in range(p_layers):
                best = None
                for g in candidates:
                    for b in candidates:
                        reg = QuantumLibrary._qaoa_state(
                            n_qubits, parsed, chosen + [(g, b)]
                        )
                        dist = reg.distribution(include_zeros=True)
                        expected = sum(
                            _real_exact(p)
                            * sum(((i >> u) ^ (i >> v)) & 1 for u, v in parsed)
                            for i, p in dist.items()
                        )
                        se = sp.simplify(expected)
                        if best is None or se > best[0]:
                            best = (se, g, b)
                assert best is not None
                chosen.append((best[1], best[2]))
                history.append(
                    {"expected_cut": str(best[0]), "gamma": str(best[1]), "beta": str(best[2])}
                )
            final = QuantumLibrary.qaoa_maxcut(parsed, chosen).payload
            final["search_history"] = history
            return final

        return _timed("qaoa", "exact_register_cyclotomic", run, owner="hilbert.QuantumRegister")

    # ------------------------------------------------------------------
    # VQE — exact expectation lane
    # ------------------------------------------------------------------

    @staticmethod
    def ising_terms(n_qubits: int, J=1, g=1) -> List[Tuple[Any, Tuple[Tuple[int, str], ...]]]:
        """Transverse-field Ising H = J * sum ZZ_i,i+1 + g * sum X_i as Pauli terms.

        Coefficients must be rational (exact).  Open chain.
        """
        Jf, gf = _turns(J, "J") , _turns(g, "g")
        terms: List[Tuple[Any, Tuple[Tuple[int, str], ...]]] = []
        for i in range(n_qubits - 1):
            terms.append((Jf, ((i, "z"), (i + 1, "z"))))
        for i in range(n_qubits):
            terms.append((gf, ((i, "x"),)))
        return terms

    @staticmethod
    def vqe_evaluate(
        n_qubits: int,
        prep_ops: Sequence[Tuple],
        pauli_terms: Sequence[Tuple[Any, Sequence[Tuple[int, str]]]],
    ) -> LibraryResult:
        """Exact <psi|H|psi> for an ansatz expressed in the exact gate set.

        ``pauli_terms`` is a sequence of ``(coeff, ((qubit, pauli), ...))``
        with rational coefficients.  The returned energy is a sympy-exact
        value — a real expectation value, not a sampled estimate.
        """
        terms = [
            (_turns(c, "term coefficient"), tuple(ops)) for c, ops in pauli_terms
        ]

        def run():
            reg = QuantumRegister(n_qubits)
            _apply_prep(reg, ops=prep_ops)
            reg.assert_normalized()
            energy = sum(
                coeff * pauli_expectation(reg, ops) for coeff, ops in terms
            )
            return {
                "n_qubits": n_qubits,
                "energy": str(sp.simplify(energy)),
                "support": len(reg.amplitudes),
            }

        return _timed("vqe", "exact_register_cyclotomic", run, owner="quantum_library.pauli_expectation")

    @staticmethod
    def vqe_ising_scan(
        n_qubits: int,
        J=1,
        g=1,
        grid: int = 16,
    ) -> LibraryResult:
        """Exact variational scan for the TFIM chain over a turn grid.

        Ansatz: per-qubit exact Y-rotation ("yrot", q, theta) with theta
        sweeping the declared grid {j/grid} turns — an exact e^{-i*pi*theta*Y}
        layer up to global phase, so product states can reach both Z and X
        expectation components.  A product ansatz cannot reach the entangled
        ground state of the TFIM; the gap to ``exact_ground_energy`` is a
        property of the ansatz family, not of the arithmetic.  Reports the exact
        argmin energy and, for 2 qubits, the exact symbolic ground energy
        from sympy diagonalization of the Pauli Hamiltonian for
        comparison.  No optimizer noise: every evaluation is exact.
        """
        terms = QuantumLibrary.ising_terms(n_qubits, J=J, g=g)

        def run():
            candidates = [Fraction(j, grid) for j in range(grid)]
            best = None
            for t in candidates:
                e = QuantumLibrary.vqe_evaluate(
                    n_qubits, [("yrot", q, t) for q in range(n_qubits)], terms
                ).payload["energy"]
                val = sp.sympify(e)
                if best is None or val < best[0]:
                    best = (val, t)
            out = {
                "grid": grid,
                "min_energy": str(best[0]),
                "argmin_turns": str(best[1]),
            }
            if n_qubits == 2:
                Jv = sp.nsimplify(Fraction(J))
                gv = sp.nsimplify(Fraction(g))
                H = (
                    Jv * sp.kronecker_product(sp.Matrix([[1, 0], [0, -1]]), sp.Matrix([[1, 0], [0, -1]]))
                    + gv * sp.kronecker_product(sp.Matrix([[0, 1], [1, 0]]), sp.eye(2))
                    + gv * sp.kronecker_product(sp.eye(2), sp.Matrix([[0, 1], [1, 0]]))
                )
                out["exact_ground_energy"] = str(min(H.eigenvals()))
            return out

        return _timed("vqe", "exact_register_cyclotomic", run, owner="quantum_library.pauli_expectation")

    # ------------------------------------------------------------------
    # general circuits — the backend registry's exact lanes
    # ------------------------------------------------------------------

    @staticmethod
    def execute_ops(
        n_qubits: int,
        ops: Sequence[Tuple],
        prefer: Optional[str] = None,
        **options: Any,
    ) -> LibraryResult:
        """Build a ``Program`` and run it through the certified registry.

        The registry selects the cheapest lane that answers exactly:
        stabilizer for Clifford at arbitrary n, mps_exact under a static
        Schmidt bound, sparse or exact_algebraic within the amplitude
        budget — and refuses what none of them can answer.
        """
        from .backends import Operation, Program, execute

        program = Program(n_qubits)
        for op in ops:
            program = Program(
                program.n_qubits,
                program.operations + (Operation(str(op[0]).lower(), tuple(op[1:])),),
            )

        def run():
            result = execute(program, prefer=prefer, **options)
            d = result.as_dict()
            return {
                "backend": d["backend"],
                "execution_class": d["execution_class"],
                "n_qubits": n_qubits,
                "program_digest": d["program_digest"],
                "materialised": d["materialised"],
                "payload": _strip_approx(d["payload"]),
                "truth_class": d["truth_class"],
            }

        res = _timed("execute", "registry", run, owner="backends.execute")
        return LibraryResult(
            family=res.family,
            lane=res.payload["backend"],
            payload=res.payload,
            truth_class=res.payload["truth_class"],
            wall_ms=res.wall_ms,
            arithmetic_domain=res.arithmetic_domain,
            lane_owner=res.lane_owner,
        )
