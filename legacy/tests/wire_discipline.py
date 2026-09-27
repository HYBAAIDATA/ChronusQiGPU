"""AST wire discipline for Lucas-wired algorithm files.

Verifies that every algorithm file in the repo carries the LUCAS WIRING
header block. The header declares the substrate route (trace/path/gap/
amplitude/step/mining) and the rule that no algorithm imports another
algorithm — only the lucas/ pool is a legal shared import.

For the fully-converted file (Intelligence/quantum_algorithms.py) we also
run the AST purity gate to confirm no sibling algorithm imports leak in.
"""

import sys
from pathlib import Path

import pytest

from lucas import gate

ROOT = Path(__file__).resolve().parent.parent

_ALLOWED_MODULES = set(sys.stdlib_module_names) | {
    "numpy",
    "pytest",
    "lucas",
    "quantum_tensor",
    "Intelligence.quantum_tensor",
    "typing_extensions",
}

# Files that have been fully converted to draw from lucas/ pool only.
# These get the strict AST purity gate.
FULLY_CONVERTED = [
    ROOT / "Intelligence" / "quantum_algorithms.py",
]

# All algorithm files that must carry the LUCAS WIRING header.
WIRED_PYTHON_FILES = [
    ROOT / "Intelligence" / "agentic_controller.py",
    ROOT / "Intelligence" / "counterfactual_intelligence.py",
    ROOT / "Intelligence" / "mining_bridge.py",
    ROOT / "Intelligence" / "predictive_solver.py",
    ROOT / "Intelligence" / "salamander.py",
    ROOT / "Intelligence" / "lucas_scales.py",
    ROOT / "Intelligence" / "causal_ladder.py",
    ROOT / "Intelligence" / "toe_bridge.py",
    ROOT / "Intelligence" / "pde_substrate.py",
    ROOT / "Intelligence" / "orchestrator.py",
    ROOT / "Intelligence" / "pythia_knowledge.py",
    ROOT / "Intelligence" / "pythia_learning.py",
    ROOT / "Intelligence" / "pythia_memory.py",
    ROOT / "Intelligence" / "pythia_tools.py",
    ROOT / "Intelligence" / "skill_loader.py",
    ROOT / "Intelligence" / "registry.py",
    ROOT / "Intelligence" / "requirements.py",
    ROOT / "Intelligence" / "safety_constraints.py",
    ROOT / "Intelligence" / "hardware_config.py",
    ROOT / "Intelligence" / "self_test.py",
    ROOT / "Intelligence" / "quantum_tensor.py",
    ROOT / "Intelligence" / "quantum_algorithms.py",
    ROOT / "Intelligence" / "meta_evolution.py",
    ROOT / "Intelligence" / "intelligence_integration.py",
    ROOT / "core_engine" / "agi_substrate.py",
    ROOT / "core_engine" / "enhanced_agi_interface.py",
    ROOT / "core_engine" / "enhanced_metrics_engine.py",
    ROOT / "core_engine" / "enhanced_powerhouse_mining_system.py",
    ROOT / "core_engine" / "enhanced_quantum_entanglement.py",
    ROOT / "core_engine" / "enhanced_quantum_math.py",
    ROOT / "core_engine" / "enhanced_resilience_layer.py",
    ROOT / "core_engine" / "enhanced_time_crystal.py",
    ROOT / "core_engine" / "frontend_integration.py",
    ROOT / "core_engine" / "governance_explainability.py",
    ROOT / "core_engine" / "layered_intelligence_substrate.py",
    ROOT / "core_engine" / "multi_agent_execution_graph.py",
    ROOT / "core_engine" / "multi_agent_intelligence.py",
    ROOT / "core_engine" / "nobel_fields_intelligence.py",
    ROOT / "core_engine" / "nobel_fields_quantum_entanglement.py",
    ROOT / "core_engine" / "nobel_fields_time_crystal.py",
    ROOT / "core_engine" / "quantum_consciousness_system.py",
    ROOT / "core_engine" / "quantum_cuda.py",
    ROOT / "core_engine" / "quantum_geometric_interface.py",
    ROOT / "core_engine" / "quantum_metal_integration.py",
    ROOT / "core_engine" / "unified_api_layer.py",
    ROOT / "core_engine" / "unified_data_model.py",
    ROOT / "core_engine" / "unified_integration_bridge.py",
    ROOT / "core_engine" / "unified_nobel_fields_integration.py",
    ROOT / "core_engine" / "unified_platform_engine.py",
]

WIRED_TS_FILES = [
    ROOT / "src" / "lib" / "first_principles_quantum.ts",
    ROOT / "src" / "lib" / "quantum_engine.ts",
    ROOT / "src" / "lib" / "quantum_walker_aqo.ts",
    ROOT / "src" / "lib" / "m3_igpu_scaler.ts",
    ROOT / "src" / "lib" / "kellogg_operator.ts",
    ROOT / "src" / "lib" / "kellogg_full_stack.ts",
    ROOT / "src" / "lib" / "grand_unified_tensor.ts",
    ROOT / "src" / "lib" / "lucas_quantum_algorithms.ts",
    ROOT / "src" / "lib" / "exact_math.ts",
    ROOT / "src" / "lib" / "q5_reference.ts",
    ROOT / "src" / "lib" / "q5_coprocessor.ts",
    ROOT / "src" / "lib" / "q5_rtl_specs.ts",
    ROOT / "src" / "lib" / "cortex_intelligence.ts",
    ROOT / "src" / "lib" / "blockchain_consciousness.ts",
    ROOT / "src" / "lib" / "bitcoin_header.ts",
    ROOT / "src" / "lib" / "mining_service.ts",
    ROOT / "src" / "lib" / "mempool_service.ts",
    ROOT / "src" / "lib" / "mempool_nonce_analyzer.ts",
    ROOT / "src" / "lib" / "difficulty_retargeting.ts",
    ROOT / "src" / "lib" / "stratum_protocol.ts",
    ROOT / "src" / "lib" / "simple_event_emitter.ts",
    ROOT / "src" / "lib" / "mclaren_homeostasis.ts",
    ROOT / "src" / "lib" / "hodge_bridge.ts",
    ROOT / "src" / "lib" / "adversarial_checks.ts",
    ROOT / "src" / "lib" / "audit_matrix.ts",
    ROOT / "src" / "lib" / "verification_suite.ts",
]


def _existing(files):
    return [f for f in files if f.exists()]


@pytest.mark.parametrize("file", _existing(WIRED_PYTHON_FILES))
def test_python_file_has_lucas_wiring_header(file):
    """Every wired Python algorithm file must carry the LUCAS WIRING block."""
    text = file.read_text(encoding="utf-8")
    assert "LUCAS WIRING:" in text, f"{file.name} missing LUCAS WIRING header"
    assert (
        "MUST NOT import from any sibling algorithm" in text
    ), f"{file.name} missing sibling-import prohibition"


@pytest.mark.parametrize("file", _existing(WIRED_TS_FILES))
def test_ts_file_has_lucas_wiring_header(file):
    """Every wired TypeScript algorithm file must carry the LUCAS WIRING block."""
    text = file.read_text(encoding="utf-8")
    assert "LUCAS WIRING:" in text, f"{file.name} missing LUCAS WIRING header"
    assert (
        "MUST NOT import from any sibling algorithm" in text
    ), f"{file.name} missing sibling-import prohibition"


@pytest.mark.parametrize("file", _existing(FULLY_CONVERTED))
def test_fully_converted_no_sibling_imports(file):
    """Fully converted files must pass the strict AST purity gate."""
    result = gate.purity_check(file, _ALLOWED_MODULES)
    assert result["passed"], f"{file} has forbidden imports: {result['forbidden']}"


@pytest.mark.parametrize("file", _existing(WIRED_PYTHON_FILES))
def test_python_file_calls_pool(file):
    """Every wired Python file must define a real pool call, not just a header."""
    text = file.read_text(encoding="utf-8")
    if file.name == "quantum_algorithms.py":
        # Fully converted file: methods call lucas_pool.get(...) directly.
        assert "lucas_pool" in text, f"{file.name} missing pool import"
    else:
        assert "def lucas_bound" in text, f"{file.name} missing lucas_bound()"
        assert "lucas.pool" in text, f"{file.name} lucas_bound does not reach the pool"
        assert '_lucas_get("' in text, f"{file.name} lucas_bound does not call a pool kernel"


@pytest.mark.parametrize("file", _existing(WIRED_TS_FILES))
def test_ts_file_calls_pool(file):
    """Every wired TS file must define a real lucasBound() call."""
    text = file.read_text(encoding="utf-8")
    assert "lucasBound" in text, f"{file.name} missing lucasBound()"
    assert (
        "ExactSequenceMath.lucas" in text
    ), f"{file.name} lucasBound does not call the Lucas substrate"


def test_no_subsystem_imports_sibling():
    """AST gate over every mining subsystem file.

    Walks the AST of each subsystem file (lucas/, Intelligence/ minus the
    wiring layer, mining/, core_engine mining substrates, src mining
    substrates, turing_core.py) and fails on any import of a sibling
    subsystem. The only legal shared imports are lucas/, turing_core and
    the declared substrates (quantum_tensor, lucas_scales, causal_ladder).
    """
    sys.path.insert(0, str(ROOT))
    import self_test as st

    result = st.check_wire_discipline()
    assert result["checked"] > 0
    assert result["passed"], f"subsystem->subsystem imports: {result['failures']}"


def test_wiring_layer_is_the_only_composer():
    """Only declared wiring-layer files may import subsystem modules."""
    sys.path.insert(0, str(ROOT))
    import self_test as st

    wiring = {p.resolve() for p in st.WIRING_FILES}
    for path in st.subsystem_files():
        assert path.resolve() not in wiring
