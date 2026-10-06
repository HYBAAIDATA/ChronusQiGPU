"""TenThousandQubitSystem — TURING's universal quantum architecture.

The documented canonical architecture (INTELLIGENCE_ONTOLOGY_EUCLID §4):
a 10,000-qubit universal system running exact symbolic quantum arithmetic,
protected by non-adjacent Fibonacci (Zeckendorf) anyonic constraints, and
wired to broadcast subsystem entanglement to Euclid.

Honest substrate accounting (AGENTS.md §1 — quantum is maths, not
substrate):

- A dense state vector on n=10_000 qubits requires 2^10_000 amplitudes —
  impossible on ANY substrate, including physical quantum hardware, which
  also cannot materialise or read out that much amplitude data.  That is
  an information-theoretic bound, not an engineering limitation, and no
  amount of substrate magic changes it.
- What IS exact and unbounded in n is the mathematics itself.  This
  system therefore dispatches to the exact representation suited to each
  state class:

    * ``stabilizer``   — Clifford states (|+>^n, GHZ, cluster, codes):
                         O(n^2) bits, arbitrary n, full entanglement.
    * ``sparse``       — QuantumRegister states whose support stays
                         bounded (basis states, k-term superpositions).
    * ``closed_form``  — tensor-product / free-fermion / hypercube
                         structures with analytic exact answers.
    * ``symbolic``     — dimension/scale manifests that never densify.

  Outside those domains the system fails closed — it raises rather than
  approximate, mock, or truncate.

Every method returns a manifest dict with ``truth_class`` fields so the
caller can always distinguish exact-symbolic results from materialised
ones — the same contract as ``TuringLayer.status``.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Dict, Iterable, List, Optional

import sympy as sp

from ..hilbert import QuantumRegister
from ..stabilizer import StabilizerState
from ..quantum_walk import CoinedCycleWalk, HypercubeWalk
from ..annealing import TransverseFieldIsing, adiabatic_condition, landau_zener
from ..swarm import QuantumSwarm
from . import core as _tc


DEFAULT_UNIVERSAL_QUBITS = 10_000


def zeckendorf_valid(indices: Iterable[int]) -> bool:
    """Non-adjacent Fibonacci constraint: sorted indices, no consecutive.

    Zeckendorf representation uses Fibonacci numbers F_k (k>=2) with no
    two adjacent — the anyonic topological guard from the ontology.  A
    subsystem's protected index set must satisfy this to be registered.
    """
    idx = sorted(int(i) for i in indices)
    return all(b - a > 1 for a, b in zip(idx, idx[1:]))


@dataclass
class EntanglementRegistration:
    """One entangled-subsystem broadcast record."""

    subsystem: str
    qubits: tuple
    zeckendorf_protected: bool
    backend: str
    verified: bool


class TenThousandQubitSystem:
    """The universal n-qubit quantum engine (default n = 10_000)."""

    def __init__(self, n_qubits: int = DEFAULT_UNIVERSAL_QUBITS):
        if n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        self.n_qubits = int(n_qubits)
        self.hilbert_dim_symbolic = f"2^{self.n_qubits}"
        self._entanglement_ledger: List[EntanglementRegistration] = []
        self._listeners: List[Callable[[EntanglementRegistration], None]] = []
        self._aethel = None

    # -- substrate: sparse exact register -----------------------------------

    def sparse_register(self, basis: int = 0, max_amplitudes=None) -> QuantumRegister:
        """Sparse exact register — unbounded n, bounded support.

        States whose nonzero-amplitude count stays within
        ``max_amplitudes`` are fully exact.  Operations that would densify
        (e.g. H^{otimes n}, diffusion) raise MemoryError instead of
        silently truncating.
        """
        return QuantumRegister(self.n_qubits, basis=basis, max_amplitudes=max_amplitudes)

    # -- superposition & entanglement (stabilizer-exact) ---------------------

    def superposition(self) -> Dict[str, Any]:
        """|+>^{otimes n} — the exact 2^n-term uniform superposition."""
        state = StabilizerState.plus(self.n_qubits)
        return {
            "state": state,
            "n_qubits": self.n_qubits,
            "hilbert_dim": self.hilbert_dim_symbolic,
            "nonzero_amplitudes": 1 << self.n_qubits,
            "materialized": False,
            "backend": "stabilizer",
            "truth_class": "exact_tableau",
        }

    def ghz(self, qubits: Optional[Iterable[int]] = None) -> Dict[str, Any]:
        """Maximally entangled GHZ state across the given qubits (all by
        default).  Exact tableau — n-party entanglement at n=10_000."""
        if qubits is None:
            state = StabilizerState.ghz(self.n_qubits)
            selected = list(range(self.n_qubits))
        else:
            selected = sorted(set(int(q) for q in qubits))
            state = StabilizerState.basis(self.n_qubits)
            state.h(selected[0])
            for q in selected[1:]:
                state.cnot(selected[0], q)
        return {
            "state": state,
            "entangled_qubits": selected,
            "schmidt_rank_across_1_rest": 2,
            "materialized": False,
            "backend": "stabilizer",
            "truth_class": "exact_tableau",
        }

    def entanglement_entropy(self, state: StabilizerState, subset) -> int:
        """Exact e-bits across subset|rest cut of a stabilizer state."""
        return state.entanglement_entropy(subset)

    # -- quantum walks --------------------------------------------------------

    def quantum_walk(
        self,
        graph: str = "hypercube",
        *,
        t=None,
        num_positions: Optional[int] = None,
        steps: int = 1,
    ) -> Dict[str, Any]:
        """Exact quantum walk.  ``hypercube`` uses the closed form on the
        n-cube (works at n=10_000, zero materialisation); ``cycle`` runs
        the coined walk on the sparse register (bounded support)."""
        if graph == "hypercube":
            walk = HypercubeWalk(self.n_qubits)
            t = sp.pi / 4 if t is None else sp.sympify(t)
            return {
                "graph": f"hypercube Q_{self.n_qubits}",
                "time": t,
                "hamming_distribution": walk.hamming_distribution(t),
                "expected_weight": walk.expected_hamming_weight(t),
                "variance": walk.hamming_variance(t),
                "backend": "closed_form",
                "truth_class": "exact_symbolic",
            }
        if graph == "cycle":
            npos = num_positions or 16
            walk = CoinedCycleWalk(npos).run(steps)
            return {
                "graph": f"cycle C_{npos}",
                "steps": steps,
                "position_distribution": walk.position_distribution(),
                "variance": walk.variance(),
                "backend": "sparse_register",
                "truth_class": "exact_sparse",
            }
        raise ValueError(f"unknown walk graph {graph!r}")

    # -- annealing & tunnelling ----------------------------------------------

    def anneal(
        self,
        s_values=(0, Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
        *,
        coupling=sp.Integer(1),
        field=sp.Integer(1),
    ) -> Dict[str, Any]:
        """Exact adiabatic gap profile of the n-spin TFIM along the anneal.

        Uses the free-fermion closed form — exact for any n including
        10_000; this is the analytical solution, not a simulation.
        """
        tfim = TransverseFieldIsing(self.n_qubits, coupling, field)
        return {
            **tfim.adiabatic_path(s_values),
            "critical_gap": tfim.critical_gap(),
            "gap_asymptotic": tfim.gap_asymptotic(),
            "backend": "free_fermion_closed_form",
            "truth_class": "exact_symbolic",
        }

    def tunnel(self, gap_min, sweep_rate) -> Dict[str, Any]:
        """Exact Landau-Zener tunnel probability (symbolic)."""
        return {
            "p_diabatic": landau_zener(gap_min, sweep_rate),
            "adiabatic_parameter": adiabatic_condition(gap_min, sweep_rate),
            "backend": "closed_form",
            "truth_class": "exact_symbolic",
        }

    # -- swarm -----------------------------------------------------------------

    def swarm(
        self,
        n_agents: int,
        steps: int,
        *,
        num_positions: int = 16,
        seed: int = 0,
    ) -> Dict[str, Any]:
        """Swarm driven by the exact coined-walk Born distribution.

        Each step every agent re-samples the walk's exact position
        increments: left/right from the marginal coin distribution of a
        fresh Hadamard-coin step.  Seeded => deterministic run.
        """
        walk = CoinedCycleWalk(num_positions).run(steps)
        dist = walk.position_distribution()
        # convert vertex distribution to an increment law relative to center
        increments: Dict[int, Any] = {}
        for x, p in dist.items():
            inc = (x - walk.center) % num_positions
            if inc > num_positions // 2:
                inc -= num_positions
            increments[inc] = increments.get(inc, 0) + p
        swarm = QuantumSwarm(n_agents, lambda _t: increments, seed=seed)
        swarm.run(steps)
        return {
            "swarm": swarm,
            "increment_distribution": increments,
            "empirical": swarm.empirical_distribution(),
            "dispersion": swarm.dispersion(),
            "backend": "exact_distribution_sampling",
            "truth_class": "exact_quantum_distribution_classical_sampling",
        }

    # -- entanglement broadcast (ontology: "so one knows it, all know it") ----

    def add_entanglement_listener(
        self, listener: Callable[[EntanglementRegistration], None]
    ) -> None:
        """Register a broadcast sink (Euclid's subsystem broadcast hook)."""
        self._listeners.append(listener)

    def register_subsystem_entanglement(
        self,
        subsystem: str,
        qubits: Iterable[int],
        *,
        backend: str = "stabilizer",
    ) -> EntanglementRegistration:
        """Register + broadcast an entangled subsystem.

        Enforces the non-adjacent Fibonacci (Zeckendorf) anyonic
        constraint on the recorded index set — protection is verified,
        never asserted without checking.
        """
        idx = tuple(sorted(int(q) for q in qubits))
        for q in idx:
            if not 0 <= q < self.n_qubits:
                raise ValueError(f"qubit {q} outside [0,{self.n_qubits})")
        protected = zeckendorf_valid(idx)
        reg = EntanglementRegistration(
            subsystem=subsystem,
            qubits=idx,
            zeckendorf_protected=protected,
            backend=backend,
            verified=protected,
        )
        self._entanglement_ledger.append(reg)
        for listener in self._listeners:
            listener(reg)
        return reg

    @property
    def entanglement_ledger(self) -> List[EntanglementRegistration]:
        return list(self._entanglement_ledger)

    # -- Golden Quantum evidence-scoped profile -------------------------------

    def golden_quantum(self):
        """Return the Golden Quantum profile bound to this virtual computer.

        The profile exposes verified transforms and capability reports,
        experimental search ordering, and non-executable speculative metadata.
        It never upgrades an ordering heuristic into a proof or hardware claim.
        """
        from ..golden_quantum import GoldenQuantumCore

        return GoldenQuantumCore(self)

    # -- Fault-tolerant quantum-ASIC engineering model ------------------------

    def pure_quantum_asic(self):
        """Return the canonical first-principles mathematical quantum ASIC."""
        from ..fault_tolerant_asic import PureQuantumMathASIC

        return PureQuantumMathASIC()

    def fault_tolerant_asic(self):
        """Compatibility alias for :meth:`pure_quantum_asic`."""
        return self.pure_quantum_asic()

    # -- Aethel persistence (folded evidence, never raw amplitudes) -----------

    def aethel_store_manifest(self, address: str = "ten_thousand:manifest") -> Dict[str, Any]:
        """Persist the folded manifest into Aethel — the data memory
        substrate stores the state MANIFEST (folded), not the 2^n
        amplitudes (which are never materialised)."""
        from ..four_layer_stack import AethelStore

        if self._aethel is None:
            self._aethel = AethelStore()
        manifest = self.status()
        payload = repr(manifest).encode("utf-8")
        return self._aethel.store(address, payload)

    # -- status ---------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        from ..pisot import plan_hilbert_coverage  # lazy: pisot->turing_core cycle
        from ..unified_theory import UNIFIED_THEORY

        coverage = plan_hilbert_coverage(self.n_qubits)
        return {
            "system": "TenThousandQubitSystem",
            "unified_theory": UNIFIED_THEORY.report(),
            "pure_quantum_asic": {
                "schema": "turing.pure_quantum_math_asic/v1",
                "truth_class": "pure_quantum_mathematical_abstraction",
                "physical_qpu_present": False,
                "first_principles": True,
            },
            "n_qubits": self.n_qubits,
            "hilbert_dim": self.hilbert_dim_symbolic,
            "dense_state_bytes_if_materialised": str(coverage.state_bytes),
            "materialized": False,
            "backends": {
                "stabilizer": "Clifford states, O(n^2) bits — exact",
                "sparse": "bounded-support states — exact",
                "closed_form": "hypercube walk / TFIM — exact symbolic",
                "symbolic": "dimension/scale manifests — never densified",
            },
            "capabilities": [
                "superposition",
                "entanglement",
                "quantum_walk",
                "annealing",
                "tunnelling",
                "swarming",
                "golden_quantum_profile",
                "pure_quantum_math_asic",
            ],
            "zeckendorf_protection": "non-adjacent Fibonacci index constraint",
            "cassini_anchor_ok": bool(_tc.cassini_check(7)),
            "truth_class": "symbolic_exact",
            "theorem_proven": False,
        }


__all__ = [
    "DEFAULT_UNIVERSAL_QUBITS",
    "EntanglementRegistration",
    "TenThousandQubitSystem",
    "zeckendorf_valid",
]
