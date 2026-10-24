"""
EUCLID Enterprise ROI & Governance Engine
=============================================
Provides clean separation between MEASURED execution telemetry (wall-time, pass rates, delta_phi)
and MODELLED engineering effort / financial ROI estimates based on explicit configuration parameters.
"""

from typing import Dict, Any

class EnterpriseROIGovernanceEngine:
    """
    Enterprise Governance Engine.
    Strictly separates empirical execution measurements from financial models.
    """
    DEFAULT_HOURLY_LABOR_RATE = 125.0  # Configurable labor rate ($/hour)
    DEFAULT_HOURS_PER_PHI_SHIFT = 85.0  # Configurable effort coefficient

    @classmethod
    def calculate_governance_report(
        self,
        total_evaluations: int,
        valid_evaluations: int,
        initial_phi: float,
        final_phi: float,
        wall_time_ms: float,
        hourly_rate: float = DEFAULT_HOURLY_LABOR_RATE,
        hours_per_phi_coefficient: float = DEFAULT_HOURS_PER_PHI_SHIFT
    ) -> Dict[str, Any]:
        """
        Generates governance report with strict boundary separation:
        1. MEASURED_TELEMETRY (Empirical facts)
        2. MODELLED_ESTIMATES (Financial & labor projections)
        """
        net_gain = round(final_phi - initial_phi, 6)
        validity_ratio = round(valid_evaluations / max(total_evaluations, 1), 4)

        # 1. Measured Empirical Telemetry
        measured_telemetry = {
            "initial_phi_coherence": initial_phi,
            "final_phi_coherence": final_phi,
            "net_phi_gain": net_gain,
            "total_evaluations_attempted": total_evaluations,
            "valid_evaluations_passed": valid_evaluations,
            "validity_survival_ratio": validity_ratio,
            "execution_wall_time_ms": wall_time_ms
        }

        # 2. Modelled Financial & Labor Projections
        modelled_hours_saved = round(max(0.0, net_gain * hours_per_phi_coefficient), 2)
        modelled_dollar_roi = round(modelled_hours_saved * hourly_rate, 2)

        modelled_estimates = {
            "modelled_dev_hours_saved": modelled_hours_saved,
            "modelled_dollar_value_roi": modelled_dollar_roi,
            "assumptions": {
                "hourly_labor_rate": hourly_rate,
                "hours_per_phi_shift_coefficient": hours_per_phi_coefficient
            }
        }

        return {
            "MEASURED_TELEMETRY": measured_telemetry,
            "MODELLED_ESTIMATES": modelled_estimates
        }

    # Backward compatibility alias
    @classmethod
    def calculate_technical_debt_reduction(cls, **kwargs) -> Dict[str, Any]:
        return cls.calculate_governance_report(**kwargs)

    @classmethod
    def get_Governance_Summary(cls, **kwargs) -> Dict[str, Any]:
        return cls.calculate_governance_report(
            total_evaluations=kwargs.get("total_evaluations", 1),
            valid_evaluations=kwargs.get("valid_evaluations", 1),
            initial_phi=kwargs.get("initial_phi", 0.5),
            final_phi=kwargs.get("final_phi", 1.0),
            wall_time_ms=kwargs.get("wall_time_ms", 10.0),
        )

    def get_governance_summary(self, **kwargs) -> Dict[str, Any]:
        return self.get_Governance_Summary(**kwargs)
