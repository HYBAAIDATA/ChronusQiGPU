"""
Enterprise ROI Governance & Telemetry Analytics
===============================================
Reports measured run telemetry. Monetary estimates are produced only when the host
supplies both conversion rates; otherwise those fields are None.
"""
from typing import Any, Dict, Optional


class EnterpriseROIGovernanceEngine:
    @staticmethod
    def calculate_technical_debt_reduction(total_evaluations: int, valid_evaluations: int, initial_phi: float,
                                           final_phi: float, wall_time_ms: float,
                                           hours_saved_per_phi_point: Optional[float] = None,
                                           hourly_rate: Optional[float] = None) -> Dict[str, Any]:
        delta_phi = round(final_phi - initial_phi, 6)
        configured = hours_saved_per_phi_point is not None and hourly_rate is not None
        hours = round(delta_phi * hours_saved_per_phi_point, 2) if configured else None
        return {
            "initial_phi_coherence": initial_phi,
            "final_phi_coherence": final_phi,
            "net_coherence_gain": delta_phi,
            "validity_survival_ratio": round(valid_evaluations / max(total_evaluations, 1), 4),
            "execution_wall_time_ms": wall_time_ms,
            "rates_configured": configured,
            "estimated_dev_hours_saved": hours,
            "estimated_dollar_value_roi": round(hours * hourly_rate, 2) if configured else None,
            "note": None if configured else "monetary estimate not produced: conversion rates not configured by host",
        }
