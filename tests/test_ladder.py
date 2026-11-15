"""The Lucas ladder proves arithmetic identities. It does not scale qubits."""

from chronus.ladder import (
    INT64_CROSSING,
    INT64_LIMIT,
    LUCAS_LADDER,
    QuantumPass,
    lucas,
    run,
    verify,
    _self_test,
)


def test_self_test_passes():
    _self_test()


def test_console_index_is_the_known_lucas_value():
    assert lucas(10) == 123
    assert verify(10) == 123


def test_index_zero_holds_without_a_negative_fibonacci():
    assert lucas(0) == 2
    assert verify(0) == 2


def test_shipped_ladder_stays_under_int64_and_names_the_crossing():
    assert max(verify(index).bit_length() for index in LUCAS_LADDER) <= 53
    assert verify(INT64_CROSSING - 1) < INT64_LIMIT < verify(INT64_CROSSING)
    assert verify(INT64_CROSSING) == 10_420_180_999_117_162_549


def test_quantum_pass_count_is_constant_across_rungs():
    workload = QuantumPass()
    rungs = run(workload)
    assert workload.amplitude_updates == 10_000 * (1 << 11) * 100
    assert [rung.index for rung in rungs] == list(LUCAS_LADDER)
    assert not any(rung.crossed_int64 for rung in rungs)
    assert all(rung.quantum_ms >= 0 for rung in rungs)
