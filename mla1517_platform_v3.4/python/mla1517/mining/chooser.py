"""Measured mining-intelligence chooser for the canonical PYTHIA path.

The chooser decides a work-allocation label from live job state and observed
outcomes. It never claims a SHA256d advantage, never fabricates a quantum
result, and never admits a candidate. The solver or hardware proof path must
still check every visited header against the negotiated target.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Deque, Iterable, Mapping

from .hyba_bridge import measure_window
from .lane import FLAT_STRUCTURE_PRIOR, M32_STRUCTURE_PRIOR, SearchPolicy, build_lane_descriptor
from .structure import INV_PHI, phi_structure_strength
from .toe_decision import TOEMiningDecisionFrame
from .toe_signal import TOECausalSignal

if TYPE_CHECKING:
    from .solver import M32SearchSolver

LOG = logging.getLogger("mla1517.mining.chooser")

_SEARCH_LEADS = frozenset(("m32_structured", "flat_exhaustive"))
_HISTORY_WINDOW = 20
_HISTORY_CAP = 256
_MIN_SAMPLES_FOR_BIAS = 3
_POOR_ACCEPT_RATE = 0.20
# Windows shorter than this cannot show a stable phi-structure score.
# Two points always look perfectly regular, which would force the
# structured lane on noise.
_MIN_WINDOW_FOR_STRUCTURE = 3
_STRUCTURE_PRIOR_THRESHOLD = INV_PHI


@dataclass(frozen=True)
class SearchDecision:
    lead: str
    reason: str
    policy: SearchPolicy
    lane_descriptor: dict[str, object]
    throttle: bool
    observed_accept_rate: float | None
    # None when the window was absent or too short to score. Never 0.0 for
    # "not measured".
    structure_parameter: float | None = None
    # Production TOE provenance.  These are advisory receipts, never proof.
    toe_frame_digest: str | None = None
    toe_expansion_receipt: str | None = None
    toe_surfaces: tuple[str, ...] = ()


def _phi_structure(values: list[int]) -> float | None:
    """Score a real window. None means not measured, which selects flat."""
    if len(values) < _MIN_WINDOW_FOR_STRUCTURE:
        return None
    try:
        return float(phi_structure_strength(values))
    except (TypeError, ValueError, OverflowError, ArithmeticError):
        LOG.warning("phi-structure score failed; selecting the flat lane", exc_info=True)
        return None


class MiningIntelligenceChooser:
    """Choose only from measured, declared lane contracts."""

    def __init__(self) -> None:
        self.history: Deque[dict[str, object]] = deque(maxlen=_HISTORY_CAP)
        self._lead_history: defaultdict[str, Deque[bool]] = defaultdict(
            lambda: deque(maxlen=_HISTORY_WINDOW)
        )
        self.accepted_count = 0
        self.rejected_count = 0
        # Operator/TOE-set dispatch gate; latched True and never auto-cleared
        # here (the recovery path owns clearing via HOLD).
        self.throttle = False
        self.last_decision: SearchDecision | None = None
        self.last_hyba: dict[str, object] | None = None

    def _accept_rate(self, lead: str) -> float | None:
        outcomes = self._lead_history.get(lead)
        if outcomes is None or len(outcomes) < _MIN_SAMPLES_FOR_BIAS:
            return None
        return sum(outcomes) / len(outcomes)

    @staticmethod
    def _toe_binding_valid(
        toe_signal: TOECausalSignal | None,
        toe_frame: TOEMiningDecisionFrame | None,
    ) -> bool:
        if not isinstance(toe_signal, TOECausalSignal) or not toe_signal.is_valid():
            return False
        # Backwards-compatible unit use may supply only a signal.  The canonical
        # coordinator always supplies the full frame; when it does, identity must
        # match before TOE is allowed to steer the solver.
        if toe_frame is None:
            return True
        return (
            isinstance(toe_frame, TOEMiningDecisionFrame)
            and toe_frame.is_valid()
            and toe_signal.job_id == toe_frame.job_id
            and toe_signal.node_id == toe_frame.node_id
            and toe_signal.sequence == toe_frame.sequence
        )

    def choose(
        self,
        *,
        has_job: bool,
        error_count: int = 0,
        job_stale: bool = False,
        candidate_window: Iterable[int] | None = None,
        budget: int = 250_000,
        toe_signal: TOECausalSignal | None = None,
        toe_frame: TOEMiningDecisionFrame | None = None,
        solver: M32SearchSolver | None = None,
    ) -> SearchDecision:
        if budget <= 0:
            raise ValueError("budget must be positive")
        toe_bound = self._toe_binding_valid(toe_signal, toe_frame)
        # Feed-forward wiring only: a valid TOE binding sets the solver's
        # starting lane before the next dispatch. face_bias never changes the
        # cryptographic predicate or candidate set; an invalid binding falls
        # through to measured default behavior untouched.
        if toe_bound and solver is not None and toe_signal is not None:
            solver.set_lane_start_offset(toe_signal.face_bias)
            LOG.debug(
                "TOE face_bias=%d applied to solver start lane frame=%s",
                toe_signal.face_bias,
                toe_frame.frame_digest if toe_frame is not None else "legacy-signal-only",
            )
        candidate_window = tuple(candidate_window) if candidate_window is not None else None
        self.last_hyba = measure_window(candidate_window)
        structure_parameter: float | None = None
        if not has_job or job_stale:
            lead, reason = "safe", "no_live_job" if not has_job else "job_stale"
            policy = SearchPolicy(
                candidate_ordering="exhaustive",
                oracle_budget=budget,
                structure_prior=FLAT_STRUCTURE_PRIOR,
            )
        else:
            values = (
                [int(value) for value in candidate_window] if candidate_window is not None else []
            )
            structure_parameter = _phi_structure(values)
            structured = (
                structure_parameter is not None
                and structure_parameter >= _STRUCTURE_PRIOR_THRESHOLD
            )
            prior = M32_STRUCTURE_PRIOR if structured else FLAT_STRUCTURE_PRIOR
            lead = "m32_structured" if structured else "flat_exhaustive"
            reason = "phi_structure_observed" if structured else "no_declared_structure_observed"
            if error_count > 0:
                reason = "hardware_errors_present|" + reason
            policy = SearchPolicy(
                candidate_ordering="m32_lane_order" if structured else "exhaustive",
                oracle_budget=budget,
                structure_prior=prior,
            )
            rate = self._accept_rate(lead)
            alternate = "flat_exhaustive" if lead == "m32_structured" else "m32_structured"
            alternate_rate = self._accept_rate(alternate)
            if (
                rate is not None
                and rate <= _POOR_ACCEPT_RATE
                and alternate_rate is not None
                and alternate_rate > rate
            ):
                lead = alternate
                reason += "|observed_accept_rate_bias"
                policy = SearchPolicy(
                    candidate_ordering=(
                        "m32_lane_order" if lead == "m32_structured" else "exhaustive"
                    ),
                    oracle_budget=budget,
                    structure_prior=(
                        M32_STRUCTURE_PRIOR if lead == "m32_structured" else FLAT_STRUCTURE_PRIOR
                    ),
                )
        if toe_frame is not None and toe_frame.is_valid():
            # Full TOE is wired into the decision receipt.  Causal explanation
            # and ladder remain audit-only until their dedicated fidelity/effect
            # recovery probes are promoted; they do not select a lead here.
            reason += "|toe_frame_bound"
        if solver is not None:
            solver.set_candidate_ordering(policy.candidate_ordering)
        decision = SearchDecision(
            lead=lead,
            reason=reason,
            policy=policy,
            lane_descriptor=build_lane_descriptor(policy),
            throttle=error_count > 0 or lead == "safe" or self.throttle,
            observed_accept_rate=self._accept_rate(lead),
            structure_parameter=structure_parameter,
            toe_frame_digest=(
                toe_frame.frame_digest
                if isinstance(toe_frame, TOEMiningDecisionFrame) and toe_frame.is_valid()
                else None
            ),
            toe_expansion_receipt=(
                toe_frame.expansion_receipt_digest
                if isinstance(toe_frame, TOEMiningDecisionFrame) and toe_frame.is_valid()
                else None
            ),
            toe_surfaces=(
                toe_frame.steering_surfaces + toe_frame.audit_only_surfaces
                if isinstance(toe_frame, TOEMiningDecisionFrame) and toe_frame.is_valid()
                else ()
            ),
        )
        self.last_decision = decision
        return decision

    def learn(self, *, accepted: bool | None, lead: str, job_id: str | None = None) -> None:
        """Record only a real pool response; None means no share decision."""
        if accepted is True:
            self.accepted_count += 1
        elif accepted is False:
            self.rejected_count += 1
        if accepted is not None and lead in _SEARCH_LEADS:
            self._lead_history[lead].append(accepted)
        self.history.append({"accepted": accepted, "lead": lead, "job_id": job_id})

    def accept_rates(self) -> Mapping[str, float | None]:
        return {lead: self._accept_rate(lead) for lead in _SEARCH_LEADS}
