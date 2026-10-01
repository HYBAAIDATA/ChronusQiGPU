"""The exact-algebra certificate gating every dispatched nonce window."""

from __future__ import annotations

import pytest

from lucas.core import fibonacci, lucas
from chronus.mla1517.mining import dispatch_algebra as da
from chronus.mla1517.mining.solver import M32SearchSolver

HEADER = bytes(80)
TARGET = (1 << 240).to_bytes(32, "little")
IDENTITY_ORDER = tuple(range(32))


def _cert(**overrides):
    args = dict(
        plan_id="plan",
        job_id="job",
        base_step=0,
        window=1344,
        lane_order=IDENTITY_ORDER,
        header=HEADER,
        target_le=TARGET,
        ceiling=lucas(20),
        nonce_order=da.ORDER_M32,
        route="cpu_reference",
    )
    args.update(overrides)
    return da.certify_dispatch(**args)


def test_every_identity_holds_exactly_along_the_ladder():
    for k in range(2, 120):
        facts = da.exact_identities(k)
        assert all(facts["checks"].values()), (k, facts["checks"])
        assert facts["L_k"] == lucas(k)
        assert facts["phi_power"] == {"a": fibonacci(k - 1), "b": fibonacci(k)}


def test_pisot_rounding_is_refused_where_it_is_false():
    # |psi| = 0.618 > 1/2, so phi does not round to L_1 = 1.
    assert da.exact_identities(1)["checks"]["pisot_rounding"] is False


def test_window_cut_from_l15_names_its_lucas_basis():
    cert = _cert(window=lucas(15) - lucas(15) % 32)
    assert cert["ok"], cert["refusal"]
    assert cert["lucas"]["k"] == 15
    assert cert["lucas"]["L_k"] == 1364
    assert cert["lucas"]["basis"] == "lucas_epoch"
    assert cert["ceiling"]["on_lucas_ladder"] is True


def test_a_window_off_the_ladder_is_bounded_not_renamed():
    cert = _cert(window=32 * 100)
    assert cert["ok"], cert["refusal"]
    assert cert["lucas"]["basis"] == "lucas_floor"
    assert lucas(cert["lucas"]["k"]) <= 3200 < lucas(cert["lucas"]["k"] + 1)


def test_m32_preview_is_the_solver_order():
    lane_order = tuple(reversed(range(32)))
    cert = _cert(base_step=4096, lane_order=lane_order)
    expected = [nonce for nonce, _lane in M32SearchSolver().candidates(4096, 8, lane_order)]
    assert cert["first_nonces"] == expected


def test_hendrix_preview_is_the_router_schedule():
    pytest.importorskip("turing_universal_quantum_computer.pisot")
    from chronus.mla1517.mining.hendrix_order import hendrix_nonces, hendrix_schedule

    window = 1344
    schedule = hendrix_schedule(window)
    cert = _cert(window=window, base_step=8192, nonce_order=da.ORDER_HENDRIX, hendrix=schedule)
    assert cert["ok"], cert["refusal"]
    assert cert["hendrix"]["coprime"] is True
    assert cert["hendrix"]["scale_matches_lucas"] is True
    assert cert["first_nonces"] == hendrix_nonces(8192, schedule, 0, 8)


def test_hendrix_without_its_schedule_is_refused():
    cert = _cert(nonce_order=da.ORDER_HENDRIX, hendrix=None)
    assert not cert["ok"]
    assert "hendrix_schedule_missing" in cert["refusal"]


def test_an_order_without_a_preview_is_recorded_not_refused():
    cert = _cert(nonce_order="golden_stride")
    assert cert["ok"]
    assert cert["first_nonces"] is None


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"window": 1000}, "window_not_whole_m32_epochs"),
        ({"lane_order": (0,) * 32}, "lane_order_not_m32_permutation"),
        ({"header": bytes(76) + b"\x01\x00\x00\x00"}, "header_nonce_not_zeroed"),
        ({"header": bytes(79)}, "header_length"),
        ({"target_le": bytes(32)}, "share_target_invalid"),
        ({"window": 32 * 400, "ceiling": 32 * 399}, "window_exceeds_lucas_ceiling"),
        ({"base_step": (1 << 32) - 32, "window": 64}, "nonce_range_outside_uint32"),
    ],
)
def test_malformed_dispatch_is_refused(overrides, reason):
    cert = _cert(**overrides)
    assert not cert["ok"]
    assert reason in cert["refusal"]
    assert cert["first_nonces"] is None


def test_certificate_names_the_header_it_certified():
    header = bytearray(80)
    header[0:4] = (0x20000000).to_bytes(4, "little")
    header[72:76] = bytes.fromhex("1d00ffff")[::-1]
    cert = _cert(header=bytes(header))
    assert cert["header"]["version"] == 0x20000000
    assert cert["header"]["nbits"] == "1d00ffff"
    assert cert["share_target_be"] == TARGET[::-1].hex()


def test_phase1_reference_runtime_cross_checks_every_dispatch():
    facts = da.exact_identities(34)
    assert facts["phase1_reference"]["available"], facts["phase1_reference"]
    for name in (
        "phase1_cassini",
        "phase1_q_matrix_trace",
        "phase1_pisot_fold_lossless",
        "phase1_m32_fabric",
    ):
        assert facts["checks"][name] is True, name
