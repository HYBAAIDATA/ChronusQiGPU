"""Verification gates shared by the PYTHAGORAS v12 integration."""

from __future__ import annotations

import ast
from typing import Callable, Dict, Optional

from .core.euclid_intelligence import EuclidIntelligenceEngine
from .core.phi_metric import PhiResonanceCalculator

CandidateTestRunner = Callable[[str], bool]


def evaluate_candidate(
    code_content: str,
    calculator: PhiResonanceCalculator,
    intelligence: EuclidIntelligenceEngine,
    external_test_runner: Optional[CandidateTestRunner] = None,
) -> Dict[str, object]:
    """Evaluate syntax, compilation, optional behavioural tests, phi and EUCLID."""
    try:
        tree = ast.parse(code_content)
    except (SyntaxError, ValueError, TypeError):
        return {
            "parse_valid": False,
            "compile_valid": False,
            "runtime_valid": False,
            "runtime_gate": "PARSE_FAILED",
            "phi_score": 0.1000,
            "euclid_intelligence_score": 0.0,
        }

    try:
        compile(tree, filename="<pythagoras-candidate>", mode="exec")
    except (SyntaxError, ValueError, TypeError):
        return {
            "parse_valid": True,
            "compile_valid": False,
            "runtime_valid": False,
            "runtime_gate": "COMPILE_FAILED",
            "phi_score": calculator.compute_phi(code_content),
            "euclid_intelligence_score": 0.0,
        }

    runtime_valid: Optional[bool] = None
    runtime_gate = "NOT_RUN"
    if external_test_runner is not None:
        runtime_gate = "EXTERNAL_TEST_RUNNER"
        try:
            runtime_valid = bool(external_test_runner(code_content))
        except Exception:
            runtime_valid = False

    intel = intelligence.compute_intelligence_scale(code_content, 0.0)
    return {
        "parse_valid": True,
        "compile_valid": True,
        "runtime_valid": runtime_valid,
        "runtime_gate": runtime_gate,
        "phi_score": calculator.compute_phi(code_content),
        "euclid_intelligence_score": intel["intelligence_score"],
    }
