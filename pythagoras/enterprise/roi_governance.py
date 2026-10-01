"""PYTHAGORAS v12 governance and ROI analytics.

Measured execution fields are always returned. Economic values are calculated
only when the caller explicitly supplies modelling coefficients; no modelled
ROI is allowed to masquerade as Mining operational telemetry.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class EnterpriseROIGovernanceEngine:
    """Calculate measured coherence/validity deltas and optional ROI models."""

    @staticmethod
    def calculate_technical_debt_reduction(
        total_evaluations: Optional[int],
        valid_evaluations: Optional[int],
        initial_phi: float,
        final_phi: float,
        wall_time_ms: float,
        hours_per_phi_per_10k_loc: Optional[float] = None,
        blended_engineering_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        delta_phi = round(float(final_phi) - float(initial_phi), 6)
        validity_ratio: Optional[float]
        if total_evaluations is None or valid_evaluations is None:
            validity_ratio = None
        else:
            validity_ratio = round(valid_evaluations / max(total_evaluations, 1), 4)

        result: Dict[str, Any] = {
            "initial_phi_coherence": float(initial_phi),
            "final_phi_coherence": float(final_phi),
            "net_coherence_gain": delta_phi,
            "validity_survival_ratio": validity_ratio,
            "execution_wall_time_ms": float(wall_time_ms),
            "economic_model_applied": False,
            "estimated_dev_hours_saved": None,
            "estimated_dollar_value_roi": None,
        }

        if hours_per_phi_per_10k_loc is not None:
            estimated_hours = round(delta_phi * float(hours_per_phi_per_10k_loc), 2)
            result["economic_model_applied"] = True
            result["estimated_dev_hours_saved"] = estimated_hours
            if blended_engineering_rate is not None:
                result["estimated_dollar_value_roi"] = round(
                    estimated_hours * float(blended_engineering_rate),
                    2,
                )

        return result
