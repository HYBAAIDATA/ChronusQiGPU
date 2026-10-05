"""Paradigm spine — triad, thesis bounds, schedules, honesty."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronus.paradigm.bakeoff import run_bakeoff
from chronus.paradigm.conformance import run_conformance
from chronus.paradigm.honesty import run_honesty_chaos
from chronus.paradigm.schedules import (
    GOLDEN_STRIDE,
    ScheduleName,
    assert_golden_stride_constant,
    coverage_unique,
    nonce_walk,
)
from chronus.paradigm.thesis import THESIS, THESIS_ID, assert_thesis_bounds, thesis_text
from chronus.paradigm.triad import run_triad, write_report


@pytest.mark.unit
def test_thesis_is_single_systems_sentence():
    text = thesis_text()
    assert "fail-closed" in text.lower() or "fail-closed" in text
    assert "SHA256d" in text or "sha256d" in text.lower()
    assert THESIS["track"] == "systems"
    assert THESIS_ID.startswith("c-paradigm")
    rep = assert_thesis_bounds()
    assert rep["ok"] is True


@pytest.mark.unit
def test_thesis_rejects_refuted_marketing():
    from al_haras.refuted_claims import ClaimRefuted

    with pytest.raises(ClaimRefuted):
        assert_thesis_bounds("We deliver Exponential speedup on mainnet.")


@pytest.mark.unit
def test_golden_stride_constant_and_uniqueness():
    assert assert_golden_stride_constant() == GOLDEN_STRIDE
    seq = nonce_walk(ScheduleName.GOLDEN_STRIDE, seed=42, count=20_000)
    assert coverage_unique(seq)
    seq2 = nonce_walk(ScheduleName.SEQUENTIAL, seed=42, count=1000)
    assert coverage_unique(seq2)
    phi = nonce_walk(ScheduleName.PHI_TIER, seed=7, count=500, header=b"\x02" * 76)
    assert coverage_unique(phi)


@pytest.mark.unit
def test_bakeoff_reports_without_claiming_advantage():
    report = run_bakeoff(count=256, seed=99, target_int=(1 << 255))
    assert report.ok
    assert len(report.results) == 3
    assert report.metadata.get("advantage_claimed") is False
    assert all(r.unique for r in report.results)
    # Negative-result field always populated (honest voice)
    assert isinstance(report.negative_result, str) and report.negative_result


@pytest.mark.unit
def test_conformance_software_gates(tmp_path: Path):
    report = run_conformance(store_dir=tmp_path / "conf")
    assert report.abi_version == "virtual_igpu_v1"
    failed = [c for c in report.checks if not c.passed]
    assert report.ok, f"conformance failures: {failed}"
    assert report.pending  # external gates must stay visible


@pytest.mark.unit
def test_honesty_chaos(tmp_path: Path):
    report = run_honesty_chaos(store_dir=tmp_path / "hon")
    failed = [c for c in report.cases if not c.passed]
    assert report.ok, f"honesty failures: {failed}"


@pytest.mark.unit
def test_triad_green_and_persists(tmp_path: Path):
    report = run_triad(include_honesty=True)
    assert report.ok, json.dumps(
        {leg.name: leg.detail for leg in report.legs if not leg.ok},
        default=str,
        indent=2,
    )
    assert report.artifact_digest
    assert THESIS_ID in report.claim_ids
    out = write_report(tmp_path / "paradigm_triad.json", report)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["thesis_id"] == THESIS_ID
