from pathlib import Path


def test_production_default_selects_scaled_execution_path():
    source = Path("mining/production_miner.py").read_text(encoding="utf-8")
    assert 'os.getenv("PYTHIA_EXECUTION_PATH", "aethel_hendrix")' in source
    assert "LucasScaledAethelExecutionAdapter" in source
    assert "PYTHIA_VQC_QUBITS" in source
    assert 'os.getenv("PYTHIA_TURING_QUBITS", "10000")' not in source


def test_production_wiring_contains_all_execution_layers():
    source = Path("mining/scaled_execution.py").read_text(encoding="utf-8")
    for required in ("TOESystem", "QuantumTensor", "HendrixStructuredSearch", "FourLayerMiningStack", "stack.igpu.mine", "verify_provenance"):
        assert required in source


def test_live_submission_remains_explicitly_gated():
    source = Path("mining/production_miner.py").read_text(encoding="utf-8")
    assert "HYBA_ENABLE_LIVE_SHARE_SUBMIT" in source
    assert "HYBA_LIVE_SHARE_APPROVAL_ID" in source
    assert "HYBA_AUTONOMOUS_EXTERNAL_ACTIONS" in source
