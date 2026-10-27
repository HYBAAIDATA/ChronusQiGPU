"""EUCLID emergence-criterion capability."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from .common import SkillError

SKILL_ID = "proof.emergence_verify"
TITLE = "Evaluate the EUCLID emergence criterion"
SOURCE = (
    "recovery.hyba_data.source.hyba_data.euclid.intelligence_assessment."
    "compute_emergence_criterion(spectral_gap, betti_1, phi_resonance)"
)
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "spectral_gap": {"type": "number"},
        "betti_1": {"type": "number"},
        "phi_resonance": {"type": "number"},
    },
    "required": ["spectral_gap", "betti_1", "phi_resonance"],
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "emerged": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"},
        "diagnostics": {"type": "object"},
        "confidence_measure": {"type": "string"},
    },
    "required": ["emerged", "confidence", "reasoning"],
}
COST_ESTIMATE = 1
RISK_LEVEL = 0.05
TIME_ESTIMATE = 1.0
EXAMPLES = (
    {
        "input": {"spectral_gap": 0.2, "betti_1": 1, "phi_resonance": 0.7},
        "output": {
            "emerged": True,
            "confidence": 1.0,
            "reasoning": "All three source criteria passed.",
        },
    },
)
LIMITATIONS = (
    "Confidence is criterion satisfaction (0 or 1), not a calibrated probability.",
    "No 100-system benchmark dataset or executable benchmark is checked in.",
    "This advisory classification does not establish consciousness, proof, or authority.",
)


def run(spectral_gap: float, betti_1: float, phi_resonance: float) -> dict[str, Any]:
    """Call EUCLID's declared criterion and return its exact predicate diagnostics."""
    try:
        source = (
            Path(__file__).resolve().parents[2]
            / "recovery"
            / "hyba_data"
            / "source"
            / "hyba_data"
            / "euclid"
            / "intelligence_assessment.py"
        )
        if source.is_file():
            module_name = "_hyba_recovered_intelligence_assessment"
            module = sys.modules.get(module_name)
            if module is None:
                spec = importlib.util.spec_from_file_location(module_name, source)
                if spec is None or spec.loader is None:
                    raise ImportError("unable to load the checked-in EUCLID source file")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            compute_emergence_criterion = module.compute_emergence_criterion
        else:
            from euclid.intelligence_assessment import compute_emergence_criterion
    except ImportError as exc:
        raise SkillError("EUCLID emergence criterion is unavailable") from exc

    emerged, diagnostics = compute_emergence_criterion(spectral_gap, betti_1, phi_resonance)
    return {
        "emerged": bool(emerged),
        "confidence": 1.0 if emerged else 0.0,
        "reasoning": (
            "All three source criteria passed."
            if emerged
            else "At least one source criterion failed."
        ),
        "diagnostics": diagnostics,
        "confidence_measure": "binary predicate agreement; not a calibrated probability",
    }
