"""Seam v2 deltas — P4, S1, F4, Bennett, MIT families, bench, standard."""

from __future__ import annotations

from chronus.seam import store
from chronus.seam.attest_compose import attest_compose, attest_verify, merkle_root
from chronus.seam.capability import (
    MIN_SAMPLES,
    declared_policy_hps,
    distribution_from_samples,
    is_unstable,
)
from chronus.seam.contract import seam_guard
from chronus.seam.invariants import score
from chronus.seam.probe import probe_devices
from chronus.seam.reversible import (
    AdiabaticFamily,
    FAMILY_NOTES,
    bennett_uncompute,
    claim_for_kernel,
    landauer_cost,
    modeled_switch_energy,
    reversible_matmul,
    reversible_qfi,
)
from chronus.seam.types import (
    Err,
    KernelName,
    Ok,
    RoutingPolicy,
    SeamError,
    ThresholdPolicy,
    attest,
)


def setup_function() -> None:
    store.reset()


def test_p4_distribution_requires_thirty_two_samples():
    short = distribution_from_samples([100.0] * 8)
    assert isinstance(short, Err)
    long = distribution_from_samples([100.0 + (i % 3) for i in range(MIN_SAMPLES)])
    assert isinstance(long, Ok)
    assert long.value.samples >= MIN_SAMPLES
    assert long.value.p50 > 0.0
    assert long.value.p95 >= long.value.p50


def test_p4_routing_names_a_policy():
    dist = distribution_from_samples(list(range(80, 80 + MIN_SAMPLES))).value
    conservative = declared_policy_hps(dist, RoutingPolicy.conservative)
    aggressive = declared_policy_hps(dist, RoutingPolicy.aggressive)
    balanced = declared_policy_hps(dist, RoutingPolicy.balanced)
    assert conservative <= balanced <= aggressive or is_unstable(dist)


def test_s1_seam_guard_converts_exceptions():
    def boom():
        raise RuntimeError("nope")

    out = seam_guard(boom)
    assert isinstance(out, Err)
    assert out.error is SeamError.unknown

    def already():
        return Ok(3)

    assert seam_guard(already).value == 3


def test_attestation_composition_is_order_independent():
    a = attest("alpha", issuer="a")
    b = attest("beta", issuer="b")
    left = attest_compose([a, b], ThresholdPolicy.majority)
    right = attest_compose([b, a], ThresholdPolicy.majority)
    assert isinstance(left, Ok) and isinstance(right, Ok)
    assert left.value.root == right.value.root
    assert merkle_root(["alpha", "beta"]) == merkle_root(["beta", "alpha"])
    assert attest_verify(left.value) is True


def test_bennett_uncompute_wipes_garbage():
    def compute():
        return [b"live"], [b"garbage"]

    def uncompute(live, garbage):
        assert garbage == [b"garbage"]
        return live

    out = bennett_uncompute(compute, uncompute)
    assert isinstance(out, Ok)
    live, claim = out.value
    assert live == [b"live"]
    assert claim.inverse_scheduled is True
    assert claim.charge_recovered is False
    assert claim.landauer_bits_erased == 0


def test_reversible_matmul_restores_zero_target():
    out = reversible_matmul([[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]])
    assert isinstance(out, Ok)
    matrix, claim = out.value
    assert matrix[0][0] == 19.0
    assert claim.logically_injective is True
    assert claim.family is AdiabaticFamily.none


def test_reversible_qfi_is_non_negative():
    out = reversible_qfi([1.0, 0.0], [0.5, -0.5])
    assert isinstance(out, Ok)
    qfi, claim = out.value
    assert qfi >= 0.0
    assert claim.inverse_scheduled is True


def test_mit_families_are_named_and_modeled():
    assert AdiabaticFamily.mit_scrl in FAMILY_NOTES
    assert AdiabaticFamily.mit_s2lal in FAMILY_NOTES
    irreversible = modeled_switch_energy(AdiabaticFamily.none, switches=10)
    scrl = modeled_switch_energy(AdiabaticFamily.mit_scrl, switches=10)
    assert scrl < irreversible
    assert landauer_cost(1) > 0.0
    claim = claim_for_kernel(KernelName.sha256d_scan, AdiabaticFamily.none)
    assert claim.logically_injective is False
    assert claim.landauer_bits_erased == 1


def test_probe_exposes_percentiles():
    probed = probe_devices()
    assert isinstance(probed, Ok)
    for cap in probed.value:
        assert cap.measured_hps.samples >= 1
        assert "p50" in cap.measured_hps.as_dict()


def test_conformance_score_is_named():
    report = score()
    assert report["level"] in {"partial", "core", "extended", "full"}
    assert "K5" in report["gaps"]
