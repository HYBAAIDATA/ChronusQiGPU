from euclid.pythagoras.quantum.quantum_tensor import QuantumTensor, plan_hilbert_coverage
from euclid.pythagoras.quantum.hendrix import HendrixIGPUSearch


def test_full_rank_11_qubit_memory_and_data_plan():
    plan = plan_hilbert_coverage(11, available_memory_bytes=2048 * 16 + 4096, data_bytes=4096)
    assert plan.dimension == 2048
    assert plan.state_bytes == 32768
    assert plan.total_bytes == 36864
    assert plan.fits
    assert QuantumTensor(require_platform_width=True).coverage(data_bytes=4096).dimension == 2048


def test_coverage_fails_closed_when_memory_is_insufficient():
    plan = plan_hilbert_coverage(11, available_memory_bytes=32768, data_bytes=1)
    assert not plan.fits
    assert plan.total_bytes == 32769


def test_hendrix_facade_exposes_scaled_schedule():
    schedule = HendrixIGPUSearch(workers=3, scale_index=76).schedule(97)
    assert schedule.verify()
    assert schedule.scale.index == 76
    assert schedule.scale.lucas_value == 7639424778862807
