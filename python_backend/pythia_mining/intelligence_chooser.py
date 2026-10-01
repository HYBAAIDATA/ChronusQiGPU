"""intelligence_chooser -- the SOLVE gate.

Chooses which lobe leads the cycle from real state (job availability, error
count, instability, phi-best) and, crucially, picks the lane from DETECTED
structure: when the candidate window shows phi-structure (s >= INV_PHI ~=
0.618) it uses the structured phi-Grover lane (truncated_icosahedron_32f),
our primary solve path; otherwise it falls back to the unstructured Grover
lane (flat). Structure selects the lane only -- SHA256d validity is never
gated by it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from python_backend.pythia_mining.search_lane_descriptor import (
    DEFAULT_STRUCTURE_PRIOR,
    FLAT_STRUCTURE_PRIOR,
)


@dataclass
class SearchPolicy:
    candidate_region: int = 0
    candidate_ordering: str = "quantum_lucas"
    oracle_budget: int = 250000
    exploration_ratio: float = 0.0
    structure_prior: str = DEFAULT_STRUCTURE_PRIOR


JOB_KIND = "sha256d_share"
PROOF = "sha256d"
DEFAULT_SEARCH_LABEL = "quantum_lucas"

# SEARCH-LANES-003: the structure gate. Structured phi-Grover lane when the
# structure parameter s >= INV_PHI (~0.618, conservative bias); else flat.
_PHI = (1.0 + 5.0**0.5) / 2.0
_STRUCTURE_PRIOR_THRESHOLD = 1.0 / _PHI


class MiningIntelligenceChooser:
    def __init__(self) -> None:
        self.last_choice: Optional[Dict[str, Any]] = None
        self.degraded_count = 0
        self._structure_analyzer = None
        self._phi_engine = None

    def choose(
        self,
        *,
        has_job,
        error_count,
        predictive=None,
        causal=None,
        job_stale=False,
        search_label=DEFAULT_SEARCH_LABEL,
        job_difficulty=1e6,
        job_age_seconds=0.0,
        hardware_cpu_available=True,
        hardware_chronus_available=False,
        memory_pressure_pct=50.0,
        current_hashrate=1000.0,
        phi_best=None,
        candidate_window=None,
    ):
        """Last-known-good shell over _choose_impl."""
        try:
            return self._choose_impl(
                has_job=has_job,
                error_count=error_count,
                predictive=predictive,
                causal=causal,
                job_stale=job_stale,
                search_label=search_label,
                job_difficulty=job_difficulty,
                job_age_seconds=job_age_seconds,
                hardware_cpu_available=hardware_cpu_available,
                hardware_chronus_available=hardware_chronus_available,
                memory_pressure_pct=memory_pressure_pct,
                current_hashrate=current_hashrate,
                phi_best=phi_best,
                candidate_window=candidate_window,
            )
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logging.error("[CHOOSER] decision fault, using last-known-good policy: %s", reason)
            self.degraded_count += 1
            return self._last_known_good_choice(
                reason=reason,
                has_job=bool(has_job),
                job_stale=bool(job_stale),
                search_label=search_label,
            )

    def _last_known_good_choice(self, *, reason, has_job, job_stale, search_label):
        from python_backend.pythia_mining.search_lane_descriptor import build_lane_descriptor

        policy = SearchPolicy()
        lead = "quantum_lucas" if (has_job and not job_stale) else "salamander"
        return {
            "lead": lead,
            "reason": f"chooser_fault_deterministic_default|{reason}",
            "search": search_label if has_job and not job_stale else None,
            "policy": policy,
            "lane_descriptor": build_lane_descriptor(
                ordering=policy.candidate_ordering,
                structure_prior=policy.structure_prior,
                budget=policy.oracle_budget,
            ),
            "proof": PROOF,
            "job_kind": JOB_KIND,
            "throttle": True,
            "phi_score": None,
            "phi_best": None,
            "structure_parameter": None,
            "structure_detected": None,
            "structure_prior": DEFAULT_STRUCTURE_PRIOR,
            "degraded": True,
            "degraded_reason": reason,
        }

    def _choose_impl(
        self,
        *,
        has_job,
        error_count,
        predictive=None,
        causal=None,
        job_stale=False,
        search_label=DEFAULT_SEARCH_LABEL,
        job_difficulty=1e6,
        job_age_seconds=0.0,
        hardware_cpu_available=True,
        hardware_chronus_available=False,
        memory_pressure_pct=50.0,
        current_hashrate=1000.0,
        phi_best=None,
        candidate_window=None,
    ):
        predictive = predictive or {}
        causal = causal or {}
        dampen = bool(predictive.get("dampen_lanes")) or causal.get("action") == "nack_slice"

        # SEARCH-LANES-003: adaptive structure detection -- the SOLVE gate.
        structure_parameter: Optional[float] = None
        structure_detected: Optional[bool] = None
        structure_prior: str = DEFAULT_STRUCTURE_PRIOR
        if self._structure_analyzer is None:
            try:
                from python_backend.mathematical_foundation.phi_complexity_theory import (
                    PhiStructureAnalyzer,
                )

                self._structure_analyzer = PhiStructureAnalyzer()
            except ImportError:
                self._structure_analyzer = None
        if self._structure_analyzer is not None and candidate_window:
            try:
                structure_parameter = float(
                    self._structure_analyzer.compute_structure_parameter(
                        candidate_window, candidate_window
                    )
                )
                structure_detected = structure_parameter >= _STRUCTURE_PRIOR_THRESHOLD
                structure_prior = (
                    DEFAULT_STRUCTURE_PRIOR if structure_detected else FLAT_STRUCTURE_PRIOR
                )
            except Exception as exc:
                logging.error(
                    "[CHOOSER] structure detection failed: %s -- keeping structured default", exc
                )
                structure_parameter = None
                structure_detected = None
                structure_prior = DEFAULT_STRUCTURE_PRIOR

        if not has_job or job_stale:
            lead, reason, search = (
                ("salamander", "no_live_job", False)
                if not has_job
                else ("salamander", "job_stale", False)
            )
        elif error_count > 0 or dampen:
            lead, reason, search = "predictive_causal", "instability", True
        else:
            lead, reason, search = "quantum_lucas", "agent_policy_execution_cpu", True

        policy = SearchPolicy(
            candidate_ordering="quantum_lucas",
            oracle_budget=250000,
            exploration_ratio=0.1 if dampen else 0.0,
            structure_prior=structure_prior,
        )
        from python_backend.pythia_mining.search_lane_descriptor import build_lane_descriptor

        lane_descriptor = build_lane_descriptor(
            ordering=policy.candidate_ordering,
            structure_prior=policy.structure_prior,
            budget=policy.oracle_budget,
        )
        choice = {
            "lead": lead,
            "reason": reason,
            "search": search_label if search else None,
            "policy": policy,
            "lane_descriptor": lane_descriptor,
            "proof": PROOF,
            "job_kind": JOB_KIND,
            "throttle": not has_job or job_stale or dampen or error_count > 0,
            "phi_score": float(phi_best) if phi_best is not None else None,
            "phi_best": phi_best,
            "structure_parameter": structure_parameter,
            "structure_detected": structure_detected,
            "structure_prior": structure_prior,
        }
        self.last_choice = choice
        return choice
