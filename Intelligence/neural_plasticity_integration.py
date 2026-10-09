"""Plastic wiring over the unified punch runtime.

Subsystems that co-activate during useful work strengthen their
connection; reward comes from the execution provenance (did the
classical punches run? is a real QPU attached?).

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: trace
"""

from __future__ import annotations

from typing import Any, Dict

from .neural_plasticity import NeuralPlasticity
from Intelligence._born import born_evidence

try:
    from .unified_punch import UnifiedPhiRuntime, MTheoryManifold
except ImportError:  # unified_punch retired; canonical OpenCL is chronus/mla1517_platform
    UnifiedPhiRuntime = None  # type: ignore[assignment]
    MTheoryManifold = None  # type: ignore[assignment]


class PlasticUnifiedRuntime:
    """Unified punch runtime with neural plasticity wiring."""

    def __init__(self):
        if UnifiedPhiRuntime is None or MTheoryManifold is None:
            raise RuntimeError(
                "PlasticUnifiedRuntime requires unified_punch, which was retired; "
                "the canonical OpenCL payload is chronus/mla1517_platform"
            )
        self.classical = UnifiedPhiRuntime()
        self.manifold = MTheoryManifold()
        self.plasticity = NeuralPlasticity(
            learning_rate=0.05,
            trace_decay=0.9,
            weight_decay=0.02,
            sprout_threshold=3,
            prune_threshold=0.02,
            crystallize_threshold=0.8,
        )
        self._register_subsystems()

    def _register_subsystems(self):
        for name in [
            "cassini_power",
            "zeckendorf_encode",
            "pisot_schedule",
            "diophantine_check",
            "golden_angle",
            "fold_topology",
            "spectral_gap",
            "poincare_fold",
            "poincare_unfold",
            "geodesic_distance",
            "mint_certificate",
            "salamander_alloc",
            "beatty_partition",
            "cassini_det",
            "decoupling_mask",
            "millennium_verify",
            "schema_split",
            "manifold_compute",
            "millennium_all",
            "hard_gate",
            "schema_enforce",
            "immutable_proof",
            "sector_P_vs_NP",
            "sector_Yang_Mills",
            "sector_Riemann",
            "sector_Navier_Stokes",
            "sector_BSD",
            "sector_Hodge",
            "sector_Poincare",
        ]:
            self.plasticity.register_subsystem(name)

    def execute_with_plasticity(self, N: int = 1024) -> Dict[str, Any]:
        # Co-activate punches that run together.
        self.plasticity.co_activate("cassini_power", "zeckendorf_encode")
        self.plasticity.co_activate("cassini_power", "pisot_schedule")
        self.plasticity.co_activate("zeckendorf_encode", "diophantine_check")
        self.plasticity.co_activate("poincare_fold", "geodesic_distance")
        self.plasticity.co_activate("poincare_fold", "mint_certificate")
        self.plasticity.co_activate("mint_certificate", "salamander_alloc")
        self.plasticity.co_activate("millennium_verify", "millennium_all")
        self.plasticity.co_activate("hard_gate", "decoupling_mask")

        result = self.classical.compute_all_punches(N)

        reward = self._compute_reward(result)
        self.plasticity.deliver_reward(reward)

        self.plasticity.decay()
        pruned = self.plasticity.prune()
        crystallized = self.plasticity.crystallize()

        result["plasticity"] = {
            "reward": reward,
            "pruned": pruned,
            "crystallized": crystallized,
            "report": self.plasticity.report(),
        }
        return result

    def _compute_reward(self, result: Dict[str, Any]) -> float:
        """Reward = Born evidence over measured provenance checks —
        the invented +1.0/+0.5/+0.3 additive weights are gone."""
        prov = result.get("provenance", {})
        checks = [
            bool(prov.get("is_real_qpu")),
            prov.get("quantum_claim") == "REAL_QUANTUM",
            bool(result.get("classical")),
        ]
        passed = sum(1 for c in checks if c)
        return born_evidence(passed, len(checks) - passed)

    def mature_cycle(self):
        self.plasticity.mature(factor=0.95)

    def report(self) -> Dict[str, Any]:
        return self.plasticity.report()
