"""
PYTHAGORAS Platform Verification Runner v12.2
Executes Adapter Façade API, EUCLID Intelligence Engine, Multi-Agent Coordination, and V6.5 Engine.
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.enterprise.roi_governance import EnterpriseROIGovernanceEngine


def main():
    print("==========================================================================")
    print("PYTHAGORAS: Meta-Evolutionary Code Intelligence Platform v12.2")
    print("Embedded Computational Engine Payload & Host Integration Façade API Active")
    print("==========================================================================")

    adapter = PythagorasEngineAdapter()

    # 1. Analyze Sample Target with EUCLID Intelligence
    sample_code = """
class DataPipeline:
    def process(self, items: list, threshold, scale) -> list:
        res = []
        for i in items:
            if i is not None:
                if i > threshold:
                    res.append(i * 0.618034)
        return res

    def summarise(self, data):
        total = 0
        count = 0
        for d in data:
            total += d
            count += 1
        mean = total / count if count else 0.0
        spread = max(data) - min(data) if data else 0.0
        label = f"{mean:.2f}"
        return {"mean": mean, "spread": spread, "label": label}
"""
    analysis_res = adapter.analyze("data_pipeline.py", sample_code, topological_time=1.0)
    print("\n=== 1. ADAPTER ANALYSIS & EUCLID INTELLIGENCE RESULT ===")
    print(json.dumps(analysis_res, indent=2))

    # 2. Evolve Sample Target
    evolution_res = adapter.evolve(
        file_path="data_pipeline.py",
        code_content=sample_code,
        generations=10,
        seed=42
    )
    print("\n=== 2. UNCONSTRAINED EVOLUTIONARY SEARCH RESULT ===")
    print(json.dumps({
        "target": evolution_res["target"],
        "initial_phi": evolution_res["initial_phi"],
        "final_phi": evolution_res["final_phi"],
        "total_delta_phi": evolution_res["total_delta_phi"],
        "accepted_steps_count": evolution_res["accepted_steps_count"],
        "evaluations_valid": evolution_res["total_evals_valid"],
        "evaluations_attempted": evolution_res["total_evals_attempted"],
        "euclid_intelligence_telemetry": evolution_res["euclid_intelligence_telemetry"]
    }, indent=2))

    # 3. Property Invariants Verification Check
    inv_res = adapter.verify_property_invariants(sample_code, evolution_res.get("final_code", sample_code), topological_time=1.0)
    print("\n=== 3. PROPERTY INVARIANTS VERIFICATION ===")
    print(json.dumps(inv_res, indent=2))

    # 4. Enterprise ROI Governance Calculation
    roi_res = EnterpriseROIGovernanceEngine.calculate_technical_debt_reduction(
        total_evaluations=evolution_res["total_evals_attempted"],
        valid_evaluations=evolution_res["total_evals_valid"],
        initial_phi=evolution_res["initial_phi"],
        final_phi=evolution_res["final_phi"],
        wall_time_ms=evolution_res["wall_time_ms"]
    )
    print("\n=== 4. ENTERPRISE ROI & GOVERNANCE METRICS ===")
    print(json.dumps(roi_res, indent=2))

    # 5. Multi-Agent Orchestration on the adapter's shared manifold
    orchestration_res = adapter.orchestrate([{"name": "data_pipeline.py", "code_str": sample_code}], generations=10)
    print("\n=== 5. MULTI-AGENT CYCLE & 11D MANIFOLD SNAPSHOT ===")
    for fname, r in orchestration_res["session_results"].items():
        print(json.dumps({k: v for k, v in r.items() if k != "final_code"}, indent=2))
    print(json.dumps(adapter.snapshot()["manifold_snapshot"], indent=2))

    # 6. Evolved code
    print("\n=== 6. EVOLVED CODE ===")
    print(evolution_res["final_code"])

    print("\n==========================================================================")
    print("PYTHAGORAS v12.2 RUN COMPLETE")
    print("==========================================================================")


if __name__ == "__main__":
    main()
