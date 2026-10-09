"""Adversarial receipts and fail-closed tests for the Hendrix schedule.

QC requirement: every execution receipt must name the implementation module,
bind the schedule by digest, declare its execution mode and whether a
fallback ran — and disabling or degrading the intended path must fail closed
rather than silently substitute a scheduler/simulator/classical fallback.
"""

from __future__ import annotations

import pytest

from turing_universal_quantum_computer.canonical_serialization import (
    canonical_sha256,
)
from turing_universal_quantum_computer.hendrix import HendrixChronusSearch
from turing_universal_quantum_computer.pisot import (
    HENDRIX_EXECUTION_MODE,
    HENDRIX_IMPLEMENTATION_MODULE,
    HendrixStructuredSearch,
    LucasScaleError,
    require_lucas_execution_scale,
)


def _search(workers=2):
    return HendrixStructuredSearch(workers=workers).search(64, lambda n: n == 42)


def test_receipt_binds_module_mode_and_schedule_digest():
    result = _search()
    receipt = result["execution_receipt"]
    assert receipt["implementation_module"] == HENDRIX_IMPLEMENTATION_MODULE
    assert receipt["execution_mode"] == HENDRIX_EXECUTION_MODE
    assert result["execution_mode"] == HENDRIX_EXECUTION_MODE
    # Digest binds the whole schedule manifest minus the digest key itself.
    manifest = dict(result["schedule"])
    emitted = manifest.pop("schedule_digest")
    assert emitted == receipt["schedule_digest"]
    assert canonical_sha256(manifest) == emitted


def test_receipt_never_reports_fallback_or_quantum():
    result = _search()
    assert result["execution_receipt"]["fallback_used"] is False
    assert result["quantum_claim"] is False
    assert "quantum" not in result["execution_mode"]


def test_evaluate_failure_propagates_no_substitution():
    search = HendrixStructuredSearch(workers=1)

    def broken(_nonce):
        raise RuntimeError("oracle unavailable")

    with pytest.raises(RuntimeError, match="oracle unavailable"):
        search.search(32, broken)


def test_off_ladder_scale_fails_closed_before_any_work():
    with pytest.raises((LucasScaleError, ValueError)):
        HendrixStructuredSearch(scale_index=13)
    with pytest.raises((LucasScaleError, ValueError)):
        HendrixStructuredSearch(scale_index=0)


def test_physical_execution_gate_fails_closed_below_l10():
    # L_7 is algebra-valid but below the physical-execution floor; the gate
    # must refuse rather than silently admit a smaller physical scale.
    with pytest.raises((LucasScaleError, ValueError)):
        require_lucas_execution_scale(7)
    assert require_lucas_execution_scale(10) == 10


def test_schedule_is_a_complete_disjoint_cover():
    for nonce_count in (17, 64, 257):
        for workers in (1, 3, 8):
            search = HendrixStructuredSearch(workers=workers)
            schedule = search.plan(nonce_count)
            seen = [
                nonce
                for worker in range(schedule.workers)
                for nonce in schedule.worker_nonces(worker)
            ]
            assert sorted(seen) == list(range(nonce_count))


def test_manifest_digest_is_tamper_sensitive():
    schedule = HendrixStructuredSearch().plan(64)
    manifest = schedule.manifest()
    emitted = manifest["schedule_digest"]
    tampered = dict(manifest)
    tampered.pop("schedule_digest")
    tampered["stride"] = tampered["stride"] + 1
    assert canonical_sha256(tampered) != emitted


def test_chronus_search_receipt_declares_classical_plane():
    result = HendrixChronusSearch().search(32, lambda n: False)
    assert result["execution_mode"] == "iGPU_classical_structured_search"
    assert result["execution_receipt"]["execution_mode"] == (
        "iGPU_classical_structured_search"
    )
    assert result["schedule"]["execution_mode"] == (
        "iGPU_classical_structured_search"
    )
    assert result["quantum_claim"] is False


def test_search_evaluates_every_candidate_until_hit():
    # Completeness guarantee: a target at any position still gets found, and
    # a no-hit window probes every position — the schedule prunes nothing.
    result = HendrixStructuredSearch(workers=1).search(50, lambda n: n == 49)
    assert result["winner"] == 49
    assert 1 <= result["evaluated"] <= 50
    miss = HendrixStructuredSearch(workers=1).search(50, lambda n: False)
    assert miss["winner"] is None
    assert miss["evaluated"] == 50
