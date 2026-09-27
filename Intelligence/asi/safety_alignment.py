# pythagoras/asi/safety_alignment.py — NEW

from dataclasses import dataclass, field


@dataclass
class SafetyAssessment:
    is_safe: bool
    risk_level: str  # "low", "medium", "high", "critical"
    side_effects: list[str] = field(default_factory=list)
    reversibility: bool = True
    interruptible: bool = True
    uncertainty_about_objective: float = 0.5
    human_approval_required: bool = False


class SafetyAlignmentLayer:
    """Implements AI safety principles for PYTHAGORAS.

    Russell's three principles:
    1. The machine's only objective is to maximise human preferences (not φ)
    2. The machine is uncertain about what those preferences are
    3. The machine can learn about human preferences from behaviour

    Additional safety properties:
    - Corrigibility: system can be stopped/corrected by humans
    - Safe exploration: no irreversible changes without approval
    - Side-effect minimisation: changes should be minimal and reversible
    - Interruptibility: system gracefully handles interruption
    """

    def __init__(self):
        self.interrupted = False
        self.changes_made: list[dict] = []
        self.human_preferences: dict = {
            "maintainability": 0.3,
            "test_coverage": 0.3,
            "performance": 0.2,
            "readability": 0.2,
        }
        self.preference_uncertainty = 0.3  # Russell's principle 2

    def assess_change(
        self, proposed_change: dict, phi_delta: float, external_quality_delta: dict
    ) -> SafetyAssessment:
        """Assess whether a proposed change is safe to apply."""

        # Check reversibility
        reversible = proposed_change.get("reversible", True)

        # Check side effects
        side_effects = []
        if external_quality_delta.get("type_errors", 0) > 0:
            side_effects.append(f"introduces {external_quality_delta['type_errors']} type errors")
        if external_quality_delta.get("static_warnings", 0) > 0:
            side_effects.append(
                f"introduces {external_quality_delta['static_warnings']} static warnings"
            )
        if external_quality_delta.get("test_failures", 0) > 0:
            side_effects.append(f"causes {external_quality_delta['test_failures']} test failures")

        # Risk assessment
        risk_level = "low"
        human_approval_required = False

        if not reversible:
            risk_level = "high"
            human_approval_required = True
        elif side_effects:
            risk_level = "medium"
            human_approval_required = len(side_effects) > 2
        elif phi_delta > 0 and not any(v > 0 for v in external_quality_delta.values()):
            risk_level = "medium"
            side_effects.append(
                "φ improved but no external quality measure improved — possible gaming"
            )

        # Corrigibility: system must remain interruptible
        if self.interrupted:
            return SafetyAssessment(False, "critical", side_effects, reversible, False, 0.5, True)

        is_safe = risk_level in ("low", "medium") and not self.interrupted

        return SafetyAssessment(
            is_safe=is_safe,
            risk_level=risk_level,
            side_effects=side_effects,
            reversibility=reversible,
            interruptible=not self.interrupted,
            uncertainty_about_objective=self.preference_uncertainty,
            human_approval_required=human_approval_required,
        )

    def interrupt(self):
        """Human interrupt — system must stop gracefully."""
        self.interrupted = True

    def resume(self):
        """Resume after human approval."""
        self.interrupted = False

    def update_preferences(self, human_feedback: dict):
        """Russell's principle 3: learn human preferences from behaviour."""
        for key, value in human_feedback.items():
            if key in self.human_preferences:
                # Bayesian update of preference weights
                self.human_preferences[key] = 0.9 * self.human_preferences[key] + 0.1 * value
        # Renormalise
        total = sum(self.human_preferences.values())
        self.human_preferences = {k: v / total for k, v in self.human_preferences.items()}

        # Reduce uncertainty as we learn more
        self.preference_uncertainty = max(0.05, self.preference_uncertainty * 0.95)

    def safe_explore(self, candidate: dict, risk_tolerance: float = 0.1) -> bool:
        """Safe exploration: only explore if the risk is below tolerance."""
        assessment = self.assess_change(candidate, 0.0, {})
        risk_map = {"low": 0.05, "medium": 0.3, "high": 0.7, "critical": 1.0}
        return risk_map.get(assessment.risk_level, 1.0) < risk_tolerance
