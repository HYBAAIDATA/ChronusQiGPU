"""Integration tests: plasticity over the unified punch runtime."""

from Intelligence.neural_plasticity_integration import PlasticUnifiedRuntime
from Intelligence.neural_plasticity_quantum import QuantumPlasticity


def test_plastic_runtime_init():
    rt = PlasticUnifiedRuntime()
    assert rt.plasticity is not None
    assert len(rt.plasticity.subsystems) > 0


def test_plastic_runtime_execute():
    rt = PlasticUnifiedRuntime()
    result = rt.execute_with_plasticity(N=32)
    assert "plasticity" in result
    assert "report" in result["plasticity"]


def test_plastic_runtime_reward_positive():
    rt = PlasticUnifiedRuntime()
    result = rt.execute_with_plasticity(N=32)
    assert "reward" in result["plasticity"]
    # Classical punches ran -> reward >= 0.3
    assert result["plasticity"]["reward"] >= 0.3


def test_quantum_plasticity_init():
    qp = QuantumPlasticity()
    assert qp.plasticity is not None


def test_quantum_plasticity_record():
    qp = QuantumPlasticity()
    # sprout_threshold=2 -> the same chain must be recorded twice.
    qp.record_quantum_operation(["qpe", "hamiltonian", "grover"], fidelity=0.95)
    qp.record_quantum_operation(["qpe", "hamiltonian", "grover"], fidelity=0.95)
    assert len(qp.plasticity.synapses) > 0


def test_quantum_plasticity_report():
    qp = QuantumPlasticity()
    for _ in range(3):
        qp.record_quantum_operation(["qpe", "hamiltonian"], fidelity=0.9)
    report = qp.report()
    assert "synapses" in report
    assert "strongest" in report
    assert report["synapses"] > 0
