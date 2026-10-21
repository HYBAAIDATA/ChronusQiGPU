"""Tests for Intelligence.mining_native — honest native workflow composition."""

import struct

import pytest

from Intelligence.mining_native import (
    CLAIM_BOUNDARY,
    NativeMiningWorkflow,
    ProbeSchedule,
)
from mining.hash_pipeline import double_sha256

HEADER = bytes(range(80))
EASY_TARGET = b"\xff" * 31 + b"\x7f"


@pytest.fixture()
def workflow() -> NativeMiningWorkflow:
    return NativeMiningWorkflow()


def test_cold_start_reports_real_backend(workflow):
    report = workflow.cold_start()
    assert report["phase"] == "cold_start"
    assert report["hasher_backend"] in ("cpu", "opencl:gpu", "opencl:cpu", "opencl:other")
    assert report["ontology"] == "MiningBridge"
    assert report["claim_boundary"] == CLAIM_BOUNDARY


def test_precompute_is_reorder_only(workflow):
    nonces = [123, 456, 789, 101112, 131415]
    schedule = workflow.precompute(nonces)
    assert sorted(schedule.probe_order) == sorted(n & 0xFFFFFFFF for n in nonces)
    assert schedule.candidates_scored == len(nonces)
    assert schedule.passed_filter <= len(nonces)
    assert isinstance(schedule, ProbeSchedule)
    assert schedule.decision.strategy in ("structured", "unstructured")


def test_hold_requires_precompute(workflow):
    with pytest.raises(ValueError):
        workflow.hold()


def test_submit_consensus_gate_is_real_sha256d(workflow):
    schedule = workflow.hold(workflow.precompute(list(range(64))))
    out = workflow.submit(HEADER, EASY_TARGET, schedule)
    assert out["phase"] == "submit"
    assert out["mining_success"] is True
    assert out["truth_class"] == "measured"
    nonce = out["winning_nonce"]
    blob = HEADER[:76] + struct.pack("<I", nonce)
    digest = bytes.fromhex(out["winning_hash_hex"])
    assert digest == double_sha256(blob)
    assert digest[::-1] < EASY_TARGET
    assert out["measured_hps"] > 0


def test_submit_without_schedule_grinds_nothing(workflow):
    out = workflow.submit(HEADER, EASY_TARGET)
    assert out["mining_success"] is False
    assert out["hashes_computed"] == 0


def test_tick_full_cycle(workflow):
    out = workflow.tick(HEADER, EASY_TARGET, base_nonce=1000, nonce_count=32)
    assert out["mining_success"] is True
    assert out["decision_strategy"] in ("structured", "unstructured")
    provenance = workflow.cool_down()
    assert provenance["grinds"] == 1
    assert provenance["winners"] == 1
    assert provenance["schedule_held"] is True


def test_telemetry_measured_only(workflow):
    tel = workflow.telemetry()
    assert tel["measured_only"] is True
    assert tel["grinds"] == 0 and tel["winners"] == 0
    assert "ehash" not in str(tel).lower()
    assert "claim_boundary" in tel


def test_claim_boundary_forbids_consensus_bypass():
    lowered = CLAIM_BOUNDARY.lower()
    assert "double-sha256" in lowered
    assert "no o(1) share discovery" in lowered
    assert "no consensus bypass" in lowered
