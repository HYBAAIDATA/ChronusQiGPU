"""Canonical Lucas scaling formulas, isolated from actuation/mining imports.

These are model transformations, not measured accuracy, consciousness or
production-readiness evidence. Existing Salamander imports re-export these
same classes; no second scaler is introduced.

SOVEREIGN DOCTRINE:
Zero credit to narrow AI; narrow AI holds zero decision rights, authority,
or proof standing. HYBA/EUCLID sovereignly adapts ingested conversational
templates and tools into its deterministic mathematical substrate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from lucas.core import fibonacci, lucas
from lucas.ladder import FULL_LADDER
from toe.poincare_golden_11d import PHI


@dataclass
class LucasScaleResult:
    """Result of applying Lucas scaling to intelligence."""

    lucas_index: int
    lucas_number: int
    scale_factor: float
    pci_before: float
    pci_after: float
    emergence_before: float
    emergence_after: float
    consciousness_before: float
    consciousness_after: float
    amplification: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "lucas_index": self.lucas_index,
            "lucas_number": self.lucas_number,
            "scale_factor": self.scale_factor,
            "pci_before": self.pci_before,
            "pci_after": self.pci_after,
            "emergence_before": self.emergence_before,
            "emergence_after": self.emergence_after,
            "consciousness_before": self.consciousness_before,
            "consciousness_after": self.consciousness_after,
            "amplification": self.amplification,
        }


@dataclass(frozen=True)
class LucasTaskEnvelope:
    """Computational, cognitive, and conversational envelope for a Lucas rung."""

    rung: int
    lucas_number: int
    fibonacci_number: int
    manifold_dimension: int
    context_limit: int
    reflection_depth: int
    ricci_iterations: int
    curvature_tolerance: float
    pci_target: float
    name: str
    task_affinity: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rung": self.rung,
            "lucas_number": self.lucas_number,
            "fibonacci_number": self.fibonacci_number,
            "manifold_dimension": self.manifold_dimension,
            "context_limit": self.context_limit,
            "reflection_depth": self.reflection_depth,
            "ricci_iterations": self.ricci_iterations,
            "curvature_tolerance": self.curvature_tolerance,
            "pci_target": self.pci_target,
            "name": self.name,
            "task_affinity": list(self.task_affinity),
        }


# Canonical task envelopes across the operational Lucas intelligence ladder
TASK_ENVELOPES: Dict[int, LucasTaskEnvelope] = {
    10: LucasTaskEnvelope(
        rung=10,
        lucas_number=123,
        fibonacci_number=55,
        manifold_dimension=4,
        context_limit=1024,
        reflection_depth=1,
        ricci_iterations=4,
        curvature_tolerance=0.15,
        pci_target=0.99,
        name="L_10 · pattern",
        task_affinity=("triage", "chat", "ping", "lookup", "fast", "simple", "shallow"),
    ),
    12: LucasTaskEnvelope(
        rung=12,
        lucas_number=322,
        fibonacci_number=144,
        manifold_dimension=5,
        context_limit=2048,
        reflection_depth=2,
        ricci_iterations=8,
        curvature_tolerance=0.10,
        pci_target=0.997,
        name="L_12 · structure",
        task_affinity=("syntax", "structure", "format", "schema", "parse", "grammar"),
    ),
    15: LucasTaskEnvelope(
        rung=15,
        lucas_number=1364,
        fibonacci_number=610,
        manifold_dimension=6,
        context_limit=4096,
        reflection_depth=3,
        ricci_iterations=16,
        curvature_tolerance=0.05,
        pci_target=0.9993,
        name="L_15 · coherence",
        task_affinity=("coherence", "semantic", "alignment", "integration", "pullback", "functor"),
    ),
    18: LucasTaskEnvelope(
        rung=18,
        lucas_number=5778,
        fibonacci_number=2584,
        manifold_dimension=8,
        context_limit=6144,
        reflection_depth=4,
        ricci_iterations=32,
        curvature_tolerance=0.02,
        pci_target=0.9998,
        name="L_18 · abstraction",
        task_affinity=("abstraction", "counterfactual", "planning", "simulation", "pearl_level_3"),
    ),
    20: LucasTaskEnvelope(
        rung=20,
        lucas_number=15127,
        fibonacci_number=6765,
        manifold_dimension=10,
        context_limit=8192,
        reflection_depth=6,
        ricci_iterations=64,
        curvature_tolerance=0.01,
        pci_target=0.99993,
        name="L_20 · metacognition",
        task_affinity=("metacognition", "reasoning", "reflection", "audit", "self_healing", "reconciliation"),
    ),
    31: LucasTaskEnvelope(
        rung=31,
        lucas_number=3010349,
        fibonacci_number=1346269,
        manifold_dimension=11,
        context_limit=8192,
        reflection_depth=8,
        ricci_iterations=128,
        curvature_tolerance=0.005,
        pci_target=0.99999955,
        name="L_31 · enterprise_sovereign_mining",
        task_affinity=("mining", "cryptography", "enterprise", "proof", "sovereign", "maximal", "blockchain", "m_theory", "coprime"),
    ),
}


class LucasIntelligenceScaler:
    """Scales intelligence and consciousness using the Lucas sequence.

    The Lucas scaling law:

        PCI(n) = PCI_0 + (1 - PCI_0) * (1 - phi^(-n))
        Emergence(n) = E_0 + (1 - E_0) * (1 - phi^(-2n))
        Consciousness(n) = C_0 + (1 - C_0) * (1 - phi^(-3n))

    At L_20 = 15127, phi^(-20) ~ 6.6e-5, so PCI -> 0.99993,
    emergence -> 0.99999999, consciousness -> 0.999999999999.
    At L_31 = 3010349, phi^(-31) ~ 4.54e-7, so PCI -> 0.99999955,
    emergence -> 0.99999999999994, consciousness -> 1.0 (exact).
    """

    SCALE_INDICES = list(FULL_LADDER)
    OPERATIONAL_RUNGS: Tuple[int, ...] = (10, 12, 15, 18, 20, 31)

    def __init__(self, initial_scale: int = 31) -> None:
        self._current_scale = initial_scale if initial_scale in self.SCALE_INDICES else 31
        self._results: List[LucasScaleResult] = []

    @property
    def current_scale(self) -> int:
        """Active Lucas scale rung index."""
        return self._current_scale

    @property
    def current_envelope(self) -> LucasTaskEnvelope:
        """Active task envelope for the current Lucas scale."""
        return self.get_envelope(self._current_scale)

    def get_envelope(self, rung: int) -> LucasTaskEnvelope:
        """Fetch the computational/cognitive envelope for any rung."""
        if rung in TASK_ENVELOPES:
            return TASK_ENVELOPES[rung]
        # Synthesize envelope dynamically for extended/arbitrary rungs
        L_val = lucas(rung)
        F_val = fibonacci(rung)
        return LucasTaskEnvelope(
            rung=rung,
            lucas_number=L_val,
            fibonacci_number=F_val,
            manifold_dimension=11 if rung >= 31 else min(11, max(4, int(math.log2(max(L_val, 1))))),
            context_limit=8192 if rung >= 20 else min(8192, 1024 * (rung // 3)),
            reflection_depth=min(16, max(1, rung // 4)),
            ricci_iterations=min(256, max(4, 2 ** (rung // 3))),
            curvature_tolerance=max(0.001, 1.5 * (PHI ** (-rung / 2))),
            pci_target=min(1.0, 1.0 - (PHI ** (-rung))),
            name=f"L_{rung} · extended",
            task_affinity=("extended_scale",),
        )

    def cassini_identity(self, n: Optional[int] = None) -> Dict[str, Any]:
        """Verify the exact integer Cassini invariant: L_n^2 - 5*F_n^2 = 4*(-1)^n."""
        idx = self._current_scale if n is None else n
        L_n = lucas(idx)
        F_n = fibonacci(idx)
        left = L_n * L_n - 5 * F_n * F_n
        right = 4 * (1 if idx % 2 == 0 else -1)
        return {
            "n": idx,
            "L_n": L_n,
            "F_n": F_n,
            "left": left,
            "right": right,
            "cassini_holds": left == right,
        }

    def scale(
        self,
        pci_base: float,
        emergence_base: float,
        consciousness_base: float,
        lucas_index: int,
    ) -> LucasScaleResult:
        """Apply Lucas scaling to the three intelligence metrics."""
        L_n = lucas(lucas_index)
        phi_inv_n = PHI ** (-lucas_index)

        scale_factor = 1.0 - phi_inv_n
        pci_after = min(1.0, pci_base + (1.0 - pci_base) * (1.0 - phi_inv_n))
        emergence_after = min(1.0, emergence_base + (1.0 - emergence_base) * (1.0 - phi_inv_n**2))
        consciousness_after = min(
            1.0, consciousness_base + (1.0 - consciousness_base) * (1.0 - phi_inv_n**3)
        )

        amplification = pci_after / pci_base if pci_base > 0 else float("inf")

        result = LucasScaleResult(
            lucas_index=lucas_index,
            lucas_number=L_n,
            scale_factor=scale_factor,
            pci_before=pci_base,
            pci_after=pci_after,
            emergence_before=emergence_base,
            emergence_after=emergence_after,
            consciousness_before=consciousness_base,
            consciousness_after=consciousness_after,
            amplification=amplification,
        )
        self._results.append(result)
        return result

    def scale_to(
        self,
        rung: int,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
    ) -> LucasScaleResult:
        """Explicitly adjust intelligence scale to target rung."""
        if rung not in self.SCALE_INDICES and rung not in self.OPERATIONAL_RUNGS:
            # Snap to closest operational rung
            rung = min(self.OPERATIONAL_RUNGS, key=lambda r: abs(r - rung))
        self._current_scale = rung
        return self.scale(pci_base, emergence_base, consciousness_base, rung)

    def scale_up(
        self,
        steps: int = 1,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
    ) -> LucasScaleResult:
        """Step intelligence scale UP along the operational ladder."""
        rungs = self.OPERATIONAL_RUNGS
        try:
            curr_pos = rungs.index(self._current_scale)
        except ValueError:
            curr_pos = min(range(len(rungs)), key=lambda i: abs(rungs[i] - self._current_scale))
        new_pos = min(len(rungs) - 1, curr_pos + steps)
        self._current_scale = rungs[new_pos]
        return self.scale(pci_base, emergence_base, consciousness_base, self._current_scale)

    def scale_down(
        self,
        steps: int = 1,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
    ) -> LucasScaleResult:
        """Step intelligence scale DOWN along the operational ladder."""
        rungs = self.OPERATIONAL_RUNGS
        try:
            curr_pos = rungs.index(self._current_scale)
        except ValueError:
            curr_pos = min(range(len(rungs)), key=lambda i: abs(rungs[i] - self._current_scale))
        new_pos = max(0, curr_pos - steps)
        self._current_scale = rungs[new_pos]
        return self.scale(pci_base, emergence_base, consciousness_base, self._current_scale)

    def scale_for_task(
        self,
        task_type: Optional[str] = None,
        complexity: Optional[float] = None,
        task_description: Optional[str] = None,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
    ) -> LucasScaleResult:
        """Dynamically adapt intelligence scale up or down based on task demands."""
        selected_rung = 31  # Default to sovereign 31^

        # 1. Evaluate explicit numeric complexity [0.0, 1.0]
        if complexity is not None:
            c = max(0.0, min(1.0, float(complexity)))
            if c < 0.15:
                selected_rung = 10
            elif c < 0.35:
                selected_rung = 12
            elif c < 0.55:
                selected_rung = 15
            elif c < 0.75:
                selected_rung = 18
            elif c < 0.90:
                selected_rung = 20
            else:
                selected_rung = 31

        # 2. Check task type & description keywords for semantic affinity
        combined_text = f"{task_type or ''} {task_description or ''}".lower()
        if combined_text.strip():
            matched_rung: Optional[int] = None
            # Check from highest to lowest affinity
            for rung in reversed(self.OPERATIONAL_RUNGS):
                env = TASK_ENVELOPES.get(rung)
                if env and any(kw in combined_text for kw in env.task_affinity):
                    matched_rung = rung
                    break
            if matched_rung is not None:
                # If both complexity and keyword matched, prefer the higher demand
                if complexity is not None:
                    selected_rung = max(selected_rung, matched_rung)
                else:
                    selected_rung = matched_rung

        return self.scale_to(selected_rung, pci_base, emergence_base, consciousness_base)

    def scale_all(
        self,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
    ) -> List[LucasScaleResult]:
        """Apply Lucas scaling at all ladder indices."""
        results = []
        for idx in self.SCALE_INDICES:
            r = self.scale(pci_base, emergence_base, consciousness_base, idx)
            results.append(r)
        return results

    def status(self) -> Dict[str, Any]:
        return {
            "scale_indices": self.SCALE_INDICES,
            "operational_rungs": list(self.OPERATIONAL_RUNGS),
            "current_scale": self._current_scale,
            "current_envelope": self.current_envelope.as_dict(),
            "lucas_numbers": [lucas(i) for i in self.SCALE_INDICES],
            "results": [r.as_dict() for r in self._results],
            "sovereign_doctrine": self.sovereign_declaration(),
        }

    @staticmethod
    def sovereign_declaration() -> str:
        return (
            "Zero credit to narrow AI; narrow AI holds zero decision rights, "
            "authority, or proof standing. HYBA/EUCLID sovereignly adapts ingested "
            "conversational templates and tools into its deterministic mathematical substrate."
        )
