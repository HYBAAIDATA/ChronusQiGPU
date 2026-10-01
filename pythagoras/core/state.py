"""
Measured 11D state of a module (axes documented in agents.manifold.STATE_AXES).
"""
from typing import Any, Dict

from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core.sandbox import al_haras_audit
from pythagoras.core.structure import analyze_structure
from pythagoras.core.tononi_penrose import graph_integration


def measure_state(code_str: str, calculator: PhiResonanceCalculator = None,
                  euclid: EuclidIntelligenceEngine = None) -> Dict[str, Any]:
    calculator = calculator or PhiResonanceCalculator()
    euclid = euclid or EuclidIntelligenceEngine()
    report = analyze_structure(code_str)
    comps = calculator.components(code_str, report)
    if not report.parse_ok:
        return {"axes": {}, "vector": [0.0] * 11, "parse_ok": False}
    _, x = euclid.calculate_lucas_index(code_str, report)
    audit = al_haras_audit(code_str)
    integ = graph_integration(code_str).get("integration") or 0.0
    axes = {
        "phi_score": comps["phi_score"],
        "golden_growth_resonance": comps["golden_growth_resonance"],
        "annotation_coherence": comps["annotation_coherence"],
        "depth_balance": comps["depth_balance"],
        "complexity_balance": comps["complexity_balance"],
        "function_balance": comps["function_balance"],
        "integrity": comps["integrity"],
        "lucas_x_normalised": round(x / (1.0 + x), 6),
        "lucas_lock": euclid.lucas_lock(x),
        "integration": integ,
        "audit_clearance": round(1.0 - min(1.0, len(audit.violations) / 3.0), 6),
    }
    return {"axes": axes, "vector": list(axes.values()), "parse_ok": True}
