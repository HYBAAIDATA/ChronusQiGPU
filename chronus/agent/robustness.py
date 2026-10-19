"""Registered perturbation defenses are evaluation plans, not measured robustness."""

from ._contracts import ContractError

DEFENCES = {
    "NOISE": "observation_filtering",
    "ADVERSARIAL": "origin_isolation",
    "CONTRADICTORY": "contradiction_retention",
    "DISTRIBUTION_SHIFT": "shift_evaluation",
    "TOOL_FAILURE": "fallback_and_rollback",
}


def harden_against(perturbation):
    if perturbation not in DEFENCES:
        raise ContractError("unknown perturbation")
    return {"defence": DEFENCES[perturbation], "tested": False, "required_evidence": perturbation}
