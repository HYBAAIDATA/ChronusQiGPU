"""Offline consensus and evidence regressions for the elevation foundation."""

import hashlib

import pytest

from Intelligence.agentic_mining import AgenticMiningWorkflow
from toe.intelligences.counterfactual import CounterfactualIntelligence
from toe.system import TOESystem

GENESIS_HEADER = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49ffff001d1dac2b7c"
)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_NONCE = 2083236893
DIFF1_TARGET = 0xFFFF << 208


@pytest.fixture
def workflow():
    result = AgenticMiningWorkflow()
    result.phase1_cold_start()
    return result


def test_default_template_has_bitcoin_field_layout(workflow):
    candidate = workflow.phase2_precompute(count=1)[0]
    assert len(candidate.header_template) == 76
    assert candidate.header_template[72:76] == bytes.fromhex("ffff001d")


def test_explicit_header_is_preserved(workflow):
    candidates = workflow.phase2_precompute(count=2, header_template=GENESIS_HEADER[:76])
    assert len(candidates) == 2
    assert all(c.header_template == GENESIS_HEADER[:76] for c in candidates)


def test_genesis_counterfactual_uses_bitcoin_byte_order():
    analysis = CounterfactualIntelligence().evaluate_submission(
        GENESIS_NONCE, GENESIS_HEADER[:76], DIFF1_TARGET
    )
    assert analysis.is_valid_share
    assert bytes.fromhex(analysis.candidate_hash_hex)[::-1].hex() == GENESIS_HASH
    for alternative in analysis.counterfactual_alternatives:
        header = GENESIS_HEADER[:76] + alternative["alt_nonce"].to_bytes(4, "little")
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        assert alternative["alt_hash_hex"] == digest.hex()
        assert alternative["alt_would_meet_target"] == (
            int.from_bytes(digest, "little") <= DIFF1_TARGET
        )


def test_genesis_phase4_and_target_equality(workflow):
    workflow.manifold_bridge.store_candidate(
        GENESIS_NONCE, GENESIS_HEADER[:76], born_prob=0.95, n_anchor=7
    )
    workflow.current_target = DIFF1_TARGET
    result = workflow.phase4_submit(GENESIS_NONCE)
    assert result.accepted
    assert bytes.fromhex(result.hash_hex)[::-1].hex() == GENESIS_HASH
    assert workflow.counterfactual.submission_log[-1].candidate_hash_hex == result.hash_hex
    hash_value = int(GENESIS_HASH, 16)
    workflow.current_target = hash_value - 1
    assert not workflow.phase4_submit(GENESIS_NONCE).accepted
    workflow.current_target = hash_value
    assert workflow.phase4_submit(GENESIS_NONCE).accepted


@pytest.mark.parametrize("length", [0, 60, 75, 77, 80, 81])
def test_malformed_template_rejected_before_submission_side_effects(workflow, length):
    workflow.manifold_bridge.store_candidate(1, bytes(length), born_prob=0.95)
    with pytest.raises(ValueError, match="76 bytes"):
        workflow.phase4_submit(1)
    assert not workflow.submitted_shares
    assert not workflow.counterfactual.submission_log
    with pytest.raises(ValueError, match="76 bytes"):
        CounterfactualIntelligence().evaluate_submission(1, bytes(length), DIFF1_TARGET)


@pytest.mark.parametrize("target", [-1, 1 << 256, True, 1.5])
def test_invalid_target_rejected(workflow, target):
    workflow.manifold_bridge.store_candidate(1, GENESIS_HEADER[:76], born_prob=0.95)
    workflow.current_target = target
    with pytest.raises(ValueError, match="target"):
        workflow.phase4_submit(1)


def test_provenance_parameters_are_snapshotted_and_hashed():
    toe = TOESystem()
    params = {"nested": {"count": 1}}
    record = toe.record_decision("phase", "controller", "compute", params, 1, True)
    params["nested"]["count"] = 2
    assert record.parameters["nested"]["count"] == 1
    assert toe.verify_provenance()
    record.parameters["nested"]["count"] = 3
    assert not toe.verify_provenance()


def test_provenance_chain_detects_reordering():
    toe = TOESystem()
    for i in range(3):
        toe.record_decision("phase", "controller", "compute", {"index": i}, 1, True)
    assert toe.verify_provenance()
    toe.provenance_ledger.reverse()
    assert not toe.verify_provenance()


def test_cooldown_refuses_corrupt_provenance(workflow):
    workflow.toe.provenance_ledger[0].parameters["device_name"] = "tampered"
    with pytest.raises(RuntimeError, match="provenance"):
        workflow.phase6_cool_down()
    assert not workflow.is_cooled_down
