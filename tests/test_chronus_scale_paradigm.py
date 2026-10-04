"""Rule 7 tests for Chronus Lucas/Pisot scale + effective-capacity paradigm.

Locks the iGPU doctrine that landed in chronus/PARADIGM.md:

- Ladder stops are scale contracts, never measured hashrate.
- effective_capacity is a Lucas-ratio envelope over unchanged physical census.
- M3 witness class: 80 physical at a mid rung sits in the ~800 effective band
  under the default ref (L_10), maths-bounded — not a fake GPU count.
- Public seam re-exports the scale surface so product code need not deep-import.
"""

from __future__ import annotations

from kellogg.scales import lucas

from chronus.seam import (
    CHRONUS_SCALE_RUNGS,
    REF_LUCAS_N,
    RULE7_NOTE,
    EffectiveCapacity,
    compute_effective_capacity,
    effective_capacity,
    memory_budget_bytes,
    scale_job,
    scale_report,
    snap_work_items,
)
from chronus.seam.scale import ChronusScale


def test_rule7_note_forbids_hashrate_cosplay():
    assert "hashrate" in RULE7_NOTE.lower() or "TH/s" in RULE7_NOTE
    assert "not" in RULE7_NOTE.lower()


def test_ref_rung_is_l10():
    assert REF_LUCAS_N == 10
    assert lucas(REF_LUCAS_N) == 123


def test_physical_census_never_rewritten():
    cap = compute_effective_capacity(80, ladder_index=15)
    assert isinstance(cap, EffectiveCapacity)
    assert cap.physical == 80
    assert cap.ladder_index == 15
    assert cap.lucas_L == lucas(15) == 1364


def test_m3_witness_80_to_800_class_envelope():
    """M3 test-bed witness: 80 physical → ~800-class effective at L_15 / L_10.

    effective = physical * L_n // L_ref
              = 80 * 1364 // 123
              = 887
    That is the maths-bounded ~800-class band. Not 800 invented GPUs.
    """
    cap = compute_effective_capacity(80, ladder_index=15)
    expected = 80 * lucas(15) // lucas(REF_LUCAS_N)
    assert expected == 887
    assert cap.effective == expected
    # ~800-class band (Rule 7: envelope, not SKU press release)
    assert 700 <= cap.effective <= 1000
    d = cap.as_dict()
    assert d["physical"] == 80
    assert d["effective"] == 887
    assert d["kind"] == "scale_contract_envelope"
    assert "hashrate" in d["note"].lower() or "TH/s" in d["note"]


def test_effective_capacity_dict_alias_matches_structured():
    structured = compute_effective_capacity(16, ladder_index=12)
    as_dict = effective_capacity(16, ladder_index=12)
    assert as_dict == structured.as_dict()
    assert as_dict["physical"] == 16
    assert as_dict["effective"] == 16 * lucas(12) // lucas(REF_LUCAS_N)


def test_zero_physical_stays_zero():
    cap = compute_effective_capacity(0, ladder_index=31)
    assert cap.physical == 0
    assert cap.effective == 0


def test_memory_budget_scales_by_lucas_ratio():
    base = 1024
    at_ref = memory_budget_bytes(base, REF_LUCAS_N)
    at_15 = memory_budget_bytes(base, 15)
    assert at_ref >= base
    assert at_15 == base * lucas(15) // lucas(REF_LUCAS_N)
    assert at_15 > at_ref


def test_snap_work_items_is_ladder_stop_not_throughput():
    # Prefer a true rung request so the contract stays on CHRONUS_SCALE_RUNGS.
    snapped = snap_work_items(15)
    assert snapped in CHRONUS_SCALE_RUNGS
    # Must not pretend to be a hashrate field
    job = scale_job("paradigm-test", requested=15, payload="fold")
    assert isinstance(job, ChronusScale)
    payload = job.as_dict()
    assert "work_items" in payload
    assert payload["work_items"] == snapped
    assert "hashrate" not in payload
    assert "ths" not in str(payload).lower()
    assert "not a throughput claim" in payload["note"]


def test_scale_report_combines_honest_fields():
    report = scale_report(physical_gpus=80, ladder_index=15)
    assert report["physical_gpus"] == 80
    assert report["capacity"]["effective"] == 887
    assert report["capacity"]["physical"] == 80
    assert "note" in report
    assert report["scale"]["product"] == "Chronus"
    assert report["scale"]["compute_substrate"] == "Turing"


def test_independent_or_overlay_does_not_mint_gpus():
    """Scaling a customer stack multiplies the envelope, never the census."""
    before = compute_effective_capacity(8, ladder_index=10)
    after = compute_effective_capacity(8, ladder_index=18)
    assert before.physical == after.physical == 8
    assert after.effective > before.effective
