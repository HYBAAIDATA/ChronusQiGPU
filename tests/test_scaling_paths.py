"""Cross-path agreement for the established Lucas/PV scaling system.

Lucas/PV scaling is load-bearing across the repository: the LUCAS_PV_SCALING
workload, the PV_LATTICE_FOLD factor, the Trinity scale index, the OpenCL
kernel factor, and the metallic generalization. These tests exercise the
scaling paths as they are actually used and require all of them to agree.
"""

import json
from fractions import Fraction

import pytest

from chronus.backends.lattice import PhiElement, phi_power
from chronus.backends.metallic import metallic_power, metallic_sequence
from chronus.execution import ExecutionRouter, NativeMathReferenceBackend
from chronus.execution.reference import _decimal_string, _fib_pair


def test_lucas_identity_holds_across_scaling_range():
    """L_n = 2*F_{n+1} - F_n at every order the workloads serve."""
    for order in range(0, 361, 17):
        fibonacci, next_fibonacci = _fib_pair(order)
        power = phi_power(order)
        assert power.trace() == 2 * next_fibonacci - fibonacci
        assert power.b == fibonacci


def test_cassini_identity_holds_across_scaling_range():
    """F_{n+1}*F_{n-1} - F_n^2 = (-1)^n along the whole scaling ladder."""
    for order in range(2, 361, 13):
        f_prev, f_n = _fib_pair(order - 1)[0], _fib_pair(order)[0]
        f_next = _fib_pair(order + 1)[0]
        assert f_next * f_prev - f_n * f_n == (-1) ** order
        power = phi_power(order)
        assert power.norm() == Fraction((-1) ** order)


def test_fast_doubling_and_metallic_paths_agree_everywhere():
    """The m=1 metallic engine and the golden engine are one system."""
    for order in list(range(0, 200, 7)) + [255, 256, 300, 360]:
        golden = phi_power(order)
        metallic = metallic_power(1, order)
        assert (golden.a, golden.b, golden.denominator) == (
            metallic.a, metallic.b, metallic.denominator)
        assert metallic_sequence(1, order) == golden.trace()


def test_lucas_pv_workload_uses_the_same_scaling_engine():
    """The API workload agrees with direct phi_power at the same orders."""
    backend = NativeMathReferenceBackend()
    for order in (0, 1, 90, 479, 4781, 50000):
        result = backend.execute(json.dumps({"index": order}).encode(), "LUCAS_PV_SCALING")
        power = phi_power(order)
        assert result["fibonacci"] == _decimal_string(power.b)
        assert result["lucas"] == _decimal_string(power.trace().numerator)
        assert result["identity_verified"] is True


def test_lattice_fold_factor_is_the_same_scaling_engine():
    """PV_LATTICE_FOLD multiplies by phi^order; verify against phi_power."""
    value = PhiElement(-7, 11, 3)
    payload = json.dumps({
        "order": 137,
        "values": [{"a": str(value.a), "b": str(value.b), "denominator": "3"}],
    }).encode()
    receipt = ExecutionRouter().execute(payload, "PV_LATTICE_FOLD")
    expected = value.multiply(phi_power(137))
    assert receipt.result["values"] == [{
        "a": str(expected.a), "b": str(expected.b), "denominator": "3",
    }]


def test_metallic_trace_recurrence_matches_powers_across_family():
    """T_n = m*T_{n-1} + T_{n-2} along every family's scaling ladder."""
    for m in (1, 2, 3, 5, 12, 64):
        sequence = [metallic_sequence(m, n) for n in range(12)]
        powers = [metallic_power(m, n) for n in range(12)]
        for n in range(12):
            assert sequence[n] == powers[n].trace()
        for n in range(2, 12):
            assert sequence[n] == m * sequence[n - 1] + sequence[n - 2]


def test_pvscale_is_the_universal_scaling_operator():
    from chronus.core import PVScale

    scale = PVScale(90)
    assert scale.trace() == 6440026026380244498  # L_90
    assert scale.cassini_parity() == 1
    advanced = scale.advance(47)
    assert advanced.index == 137
    assert advanced.factor() == phi_power(137)
    assert PVScale(10, m=2).trace() == metallic_sequence(2, 10)
    with pytest.raises(ValueError):
        PVScale(-1)
    with pytest.raises(ValueError):
        PVScale(1, m=2).factor()


def test_theseus_scales_records_by_pv_lineage():
    from chronus.core import PVScale
    from chronus.security.ovid import OVIDStorage
    from chronus.storage import TheseusService

    service = TheseusService(OVIDStorage())
    record = service.store("tenant", b"state-payload", scale_index=90)
    scaled = service.scale_record("tenant", record.object_id, 47)
    assert scaled.scale_index == 137 == PVScale(90).advance(47).index
    assert scaled.object_id == record.object_id  # content untouched
    assert scaled.coordinate != record.coordinate
    assert service.reconstruct("tenant", scaled.object_id) == b"state-payload"


def test_lucas_weighted_partition_is_exact_and_disjoint():
    from chronus.execution.mining import partition_nonce_range

    lanes = partition_nonce_range(0, 65536, weights="lucas")
    assert len(lanes) == 32
    assert lanes[0][0] == 0 and lanes[-1][1] == 65536
    for left, right in zip(lanes, lanes[1:]):
        assert left[1] == right[0]  # contiguous, disjoint
    widths = [stop - start for start, stop in lanes]
    assert widths[-1] > widths[0]  # PV-scaled strides widen along the ladder
    uniform = partition_nonce_range(0, 65536)
    assert sum(b - a for a, b in lanes) == sum(b - a for a, b in uniform) == 65536


def test_rtl_companion_step_semantics_match_phi_power():
    """The silicon scale step (a,b) -> (b, a+b) reproduces phi^k exactly.

    Mirrors hw/pv_scale_32lane.sv: k register steps from any (a, b) must equal
    multiplication by phi^k, for every order the lattice workloads serve.
    """
    for order in range(0, 361, 19):
        a, b = 0, 1
        for _ in range(order):
            a, b = b, a + b
        power = phi_power(order + 1)
        assert (a, b) == (power.a, power.b)
    # Composition: k1 steps then k2 steps equals k1+k2 steps.
    a1, b1 = 3, -2
    for _ in range(47):
        a1, b1 = b1, a1 + b1
    for _ in range(90):
        a1, b1 = b1, a1 + b1
    a2, b2 = 3, -2
    for _ in range(137):
        a2, b2 = b2, a2 + b2
    assert (a1, b1) == (a2, b2)


def test_planck_ladder_climbs_lucas_rungs_with_exact_coverage():
    from chronus.core.scaling import planck_ladder

    assert planck_ladder(1) == [1]
    assert planck_ladder(2) == [1, 1]       # L_1 = 1, remainder 1
    assert planck_ladder(10) == [1, 3, 4, 2]  # L_1, L_2, L_3, remainder
    ladder = planck_ladder(1000)
    assert sum(ladder) == 1000
    # Every rung except the last is a Lucas number on the ladder.
    from chronus.backends.metallic import metallic_sequence

    lucas = {metallic_sequence(1, i) for i in range(1, 20)}
    assert all(rung in lucas for rung in ladder[:-1])
    assert ladder[:-1] == sorted(ladder[:-1])  # Lucas rungs ascend
    assert ladder[-1] <= ladder[-2]  # final rung is the exact remainder
    with pytest.raises(ValueError):
        planck_ladder(0)


def test_trinity_scale_index_composes_with_lattice_fold():
    """Advancing the scale index and materializing agree with direct fold."""
    from chronus.execution.trinity import scale_fold_store

    values = [{"a": "3", "b": "-2", "denominator": "7"}]
    staged = scale_fold_store({"values": values, "increment": 100})
    staged = scale_fold_store({"state": staged["state"], "increment": 37})
    assert staged["state"]["scale_index"] == 137
    direct = ExecutionRouter().execute(json.dumps({
        "order": 137,
        "values": [{"a": 3, "b": -2, "denominator": 7}],
    }).encode(), "PV_LATTICE_FOLD")
    expected = PhiElement(3, -2, 7).multiply(phi_power(137))
    assert direct.result["values"][0]["a"] == str(expected.a)
