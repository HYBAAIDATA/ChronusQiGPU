"""Canonical Lucas scaling formulas, isolated from actuation/mining imports.

These are model transformations, not measured accuracy, consciousness or
production-readiness evidence. Existing Salamander imports re-export these
same classes; no second scaler is introduced.
"""
from dataclasses import dataclass
from typing import Any, Dict, List
from lucas.core import lucas
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


class LucasIntelligenceScaler:
    """Scales intelligence and consciousness using the Lucas sequence.

    The Lucas scaling law:

        PCI(n) = PCI_0 + (1 - PCI_0) * (1 - phi^(-n))
        Emergence(n) = E_0 + (1 - E_0) * (1 - phi^(-2n))
        Consciousness(n) = C_0 + (1 - C_0) * (1 - phi^(-3n))

    At L_20 = 15127, phi^(-20) ~ 6.6e-5, so PCI -> 0.99993,
    emergence -> 0.99999999, consciousness -> 0.999999999999.
    """

    SCALE_INDICES = list(FULL_LADDER)

    def __init__(self) -> None:
        self._results: List[LucasScaleResult] = []

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

    def scale_all(
        self,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
    ) -> List[LucasScaleResult]:
        """Apply Lucas scaling at all requested indices (10, 12, 15, 18, 20)."""
        results = []
        for idx in self.SCALE_INDICES:
            r = self.scale(pci_base, emergence_base, consciousness_base, idx)
            results.append(r)
        return results

    def status(self) -> Dict[str, Any]:
        return {
            "scale_indices": self.SCALE_INDICES,
            "lucas_numbers": [lucas(i) for i in self.SCALE_INDICES],
            "results": [r.as_dict() for r in self._results],
        }
