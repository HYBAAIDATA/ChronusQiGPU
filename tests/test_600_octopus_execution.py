"""Tests for the 600-Arm Octopus Execution Coordinator and Entangled Qubit Hashing.

Phase P5 unit test suite:
- 32-qubit entangled stabilizer register (16 Bell pairs, 16 e-bits entropy)
- Symplectic Clifford transformations and state tableau verification
- 100% Host SHA256d bit-exact independent recheck
- Physical honesty: virtual QPU / CPU route labeled EMULATOR, never physical silicon
- 600 arms executing concurrently under ThreadPoolExecutor(4)
- 9,600 total Bell pairs across the 600-arm estate
- Merkle root aggregation of execution receipts
- Submission gate: Shadow Mode default (no live submit without approval_flag=True)
- Soak campaign execution over Braiins jobs 00-06 logging jobs, difficulties, invalidations, heals, and rechecks
"""

import math
import struct
import pytest

from chronus.entangled_hashing import EntangledNonceCandidate, EntangledQubitHasher, LaneHashingReceipt
from chronus.exact_geometry import build_600_partition
from chronus.octopus_execution import (
    OctopusCampaignReceipt,
    OctopusExecutionEngine,
    run_10min_soak_campaign,
)
from kellogg.ansatz_v3 import LANES


def test_entangled_qubit_hasher_direct():
    chunks, proof = build_600_partition(base_step=1000, window=600, seed=1337)
    prefix = b"B" * 76
    target = (1 << 256) - 1  # max target: all nonces qualify

    hasher = EntangledQubitHasher(
        chunk=chunks[0],
        header_prefix=prefix,
        target_int=target,
        device_route="chronus_batch",
    )
    receipt = hasher.execute(max_evaluations=5)

    assert receipt.lane_id == 0
    assert receipt.nonces_evaluated > 0
    assert receipt.entangled_qubit_dimension == 32
    assert receipt.bell_pairs == 16
    assert receipt.host_recheck_pct == 100.0
    assert "emulator" in receipt.executed_route.lower()  # Physical honesty: EMULATOR

    candidate = receipt.winning_candidate
    assert candidate is not None
    assert candidate.bell_pair_count == 16
    assert candidate.entanglement_entropy_ebits == 16.0
    assert "CHP[32q:16Bell" in candidate.state_tableau
    assert candidate.recheck_passed is True
    assert len(candidate.sha256d_hex) == 64


def test_octopus_campaign_execution_600_arms(tmp_path):
    engine = OctopusExecutionEngine(shadow_dir=tmp_path / "shadow", max_workers=4)
    prefix = b"C" * 76
    target = (1 << 240)  # moderate difficulty

    receipt = engine.run_campaign(
        job_id="braiins_job_01",
        job_fingerprint="fp_soak_test_01",
        header_prefix=prefix,
        target_int=target,
        base_step=0,
        window=1200,
        seed=1337,
        approval_flag=False,  # Shadow mode
        max_nonces_per_arm=2,
    )

    assert receipt.total_arms == 600
    assert receipt.nonces_evaluated == 1200
    assert receipt.host_recheck_pct == 100.0
    assert receipt.qubit_dimension == 32
    assert receipt.total_bell_pairs == 9600
    assert len(receipt.merkle_root) == 64
    assert len(receipt.search_plan_hash) == 64
    assert receipt.submitted_live is False
    assert receipt.shadow_logged is True
    assert len(receipt.lane_receipts) == 600


def test_octopus_campaign_live_submit_authorization(tmp_path):
    engine = OctopusExecutionEngine(shadow_dir=tmp_path / "shadow", max_workers=4)
    prefix = b"D" * 76
    target = (1 << 256) - 1  # win guaranteed

    receipt = engine.run_campaign(
        job_id="braiins_job_winner",
        job_fingerprint="fp_winner_test",
        header_prefix=prefix,
        target_int=target,
        base_step=0,
        window=600,
        seed=42,
        approval_flag=True,  # Explicit live approval
        max_nonces_per_arm=1,
    )

    assert receipt.submitted_live is True
    assert receipt.winning_share is not None
    assert receipt.winning_share.recheck_passed is True


def test_soak_campaign_runner(tmp_path):
    engine = OctopusExecutionEngine(shadow_dir=tmp_path / "shadow", max_workers=4)
    # Braiins pool jobs 00-06
    braiins_jobs = [
        ("braiins_job_00", "fp_00", (1 << 256) - 1),
        ("braiins_job_01", "fp_01", (1 << 250)),
        ("braiins_job_02", "fp_02", (1 << 248)),
        ("braiins_job_03", "fp_03", (1 << 246)),
        ("braiins_job_04", "fp_04", (1 << 244)),
        ("braiins_job_05", "fp_05", (1 << 242)),
        ("braiins_job_06", "fp_06", (1 << 240)),
    ]

    # Run soak test for 2 iterations of the job list
    soak_summary = run_10min_soak_campaign(
        engine=engine,
        jobs=braiins_jobs,
        max_duration_seconds=5.0,  # Fast bound for unit test execution
        window_per_campaign=600,
    )

    assert soak_summary["campaigns_completed"] > 0
    assert soak_summary["total_arms_engaged"] >= 600
    assert soak_summary["host_recheck_average_pct"] == 100.0
    assert soak_summary["shadow_mode_enforced"] is True
    assert soak_summary["unapproved_submissions"] == 0
