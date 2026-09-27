"""One-shot Lucas wiring pass — adds the LUCAS WIRING header and a single
pool call to every algorithm file listed in ALGORITHM_FILES.

Idempotent: skips files that already contain the wiring marker.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WIRING_HEADER = (
    "# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel\n"
    "# inline below. MUST NOT import from any sibling algorithm.\n"
    "# Substrate route: {route}\n"
)

# (file, route, pool_call)
ALGORITHM_FILES = [
    # Intelligence/
    ("Intelligence/agentic_controller.py", "step", "step_kernel"),
    ("Intelligence/counterfactual_intelligence.py", "path", "path_kernel"),
    ("Intelligence/mining_bridge.py", "mining", "mining_kernel"),
    ("Intelligence/predictive_solver.py", "mining", "mining_kernel"),
    ("Intelligence/salamander.py", "trace", "trace_kernel"),
    ("Intelligence/lucas_scales.py", "trace", "trace_kernel"),
    ("Intelligence/causal_ladder.py", "path", "path_kernel"),
    ("Intelligence/toe_bridge.py", "gap", "gap_kernel"),
    ("Intelligence/pde_substrate.py", "gap", "gap_kernel"),
    ("Intelligence/orchestrator.py", "step", "step_kernel"),
    ("Intelligence/pythia_knowledge.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/pythia_learning.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/pythia_memory.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/pythia_tools.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/skill_loader.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/registry.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/requirements.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/safety_constraints.py", "gap", "gap_kernel"),
    ("Intelligence/hardware_config.py", "step", "step_kernel"),
    ("Intelligence/self_test.py", "trace", "trace_kernel"),
    ("Intelligence/quantum_tensor.py", "trace", "trace_kernel"),
    ("Intelligence/meta_evolution.py", "amplitude", "amplitude_kernel"),
    ("Intelligence/intelligence_integration.py", "path", "path_kernel"),
    # core_engine/
    ("core_engine/agi_substrate.py", "amplitude", "amplitude_kernel"),
    ("core_engine/enhanced_agi_interface.py", "amplitude", "amplitude_kernel"),
    ("core_engine/enhanced_metrics_engine.py", "gap", "gap_kernel"),
    ("core_engine/enhanced_powerhouse_mining_system.py", "mining", "mining_kernel"),
    ("core_engine/enhanced_quantum_entanglement.py", "amplitude", "amplitude_kernel"),
    ("core_engine/enhanced_quantum_math.py", "trace", "trace_kernel"),
    ("core_engine/enhanced_resilience_layer.py", "gap", "gap_kernel"),
    ("core_engine/enhanced_time_crystal.py", "gap", "gap_kernel"),
    ("core_engine/frontend_integration.py", "amplitude", "amplitude_kernel"),
    ("core_engine/governance_explainability.py", "gap", "gap_kernel"),
    ("core_engine/layered_intelligence_substrate.py", "step", "step_kernel"),
    ("core_engine/multi_agent_execution_graph.py", "path", "path_kernel"),
    ("core_engine/multi_agent_intelligence.py", "step", "step_kernel"),
    ("core_engine/nobel_fields_intelligence.py", "amplitude", "amplitude_kernel"),
    ("core_engine/nobel_fields_quantum_entanglement.py", "amplitude", "amplitude_kernel"),
    ("core_engine/nobel_fields_time_crystal.py", "gap", "gap_kernel"),
    ("core_engine/quantum_consciousness_system.py", "amplitude", "amplitude_kernel"),
    ("core_engine/quantum_cuda.py", "mining", "mining_kernel"),
    ("core_engine/quantum_geometric_interface.py", "gap", "gap_kernel"),
    ("core_engine/quantum_metal_integration.py", "mining", "mining_kernel"),
    ("core_engine/unified_api_layer.py", "amplitude", "amplitude_kernel"),
    ("core_engine/unified_data_model.py", "amplitude", "amplitude_kernel"),
    ("core_engine/unified_integration_bridge.py", "amplitude", "amplitude_kernel"),
    ("core_engine/unified_nobel_fields_integration.py", "amplitude", "amplitude_kernel"),
    ("core_engine/unified_platform_engine.py", "step", "step_kernel"),
]


def wire_file(rel_path: str, route: str, kernel: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return f"SKIP (missing): {rel_path}"
    text = path.read_text(encoding="utf-8")
    if "LUCAS WIRING:" in text:
        return f"SKIP (already wired): {rel_path}"
    header = WIRING_HEADER.format(route=route)
    # Insert the wiring header right after the module docstring (if any).
    if text.startswith('"""'):
        end = text.find('"""', 3)
        if end != -1:
            end += 3
            # Skip trailing newline if present
            while end < len(text) and text[end] in "\r\n":
                end += 1
            new_text = text[:end] + "\n" + header + "\n" + text[end:]
        else:
            new_text = header + "\n" + text
    else:
        new_text = header + "\n" + text
    path.write_text(new_text, encoding="utf-8")
    return f"WIRED: {rel_path} ({route} -> {kernel})"


def main() -> None:
    for rel, route, kernel in ALGORITHM_FILES:
        print(wire_file(rel, route, kernel))


if __name__ == "__main__":
    main()
