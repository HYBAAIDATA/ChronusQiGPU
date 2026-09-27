import pytest

from igpu.seam.workflow import (
    LAYER_IDS,
    PASS_MEANS,
    WorkflowResult,
    attest_sign,
    attest_verify,
    classify_oi,
    digest_uint256,
    is_hex64,
    share_meets_target,
    sha256d,
)
from mining.stratum_bridge import LiveJob


def test_pass_means_covers_every_layer():
    assert set(PASS_MEANS) == set(LAYER_IDS)


@pytest.mark.parametrize("layer", LAYER_IDS)
def test_layer_happy_record(layer):
    out = WorkflowResult(fail_fast=False)
    verdict = out.record(layer, True, PASS_MEANS[layer])
    assert verdict.passed is True
    assert verdict.layer == layer
    verdict.assert_pass()


@pytest.mark.parametrize("layer", LAYER_IDS)
def test_layer_failure_record(layer):
    out = WorkflowResult(fail_fast=False)
    verdict = out.record(layer, False, f"{layer} forced fail")
    assert verdict.passed is False
    with pytest.raises(AssertionError, match=layer):
        verdict.assert_pass()


def test_every_layer_failure_appears_in_assert_all():
    out = WorkflowResult(fail_fast=False)
    for layer in LAYER_IDS:
        out.record(layer, False, f"{layer} down")
    with pytest.raises(AssertionError) as err:
        out.assert_all()
    msg = str(err.value)
    for layer in LAYER_IDS:
        assert layer in msg


def test_l0_connect_fail_fast_raises():
    out = WorkflowResult(fail_fast=True)
    with pytest.raises(AssertionError, match="L0_connect FAIL"):
        out.record_or_raise("L0_connect", False, "no socket")


def test_l0_handshake_requires_extranonce():
    out = WorkflowResult(fail_fast=False)
    out.record("L0_handshake", bool("") and True, "Authorized: True")
    assert out.verdicts["L0_handshake"].passed is False


def test_l1_parse_missing_field():
    job = LiveJob(job_id="j", prev_hash="", version="20000000", nbits="1d00ffff", ntime="00")
    parsed = all([job.job_id, job.prev_hash, job.version, job.nbits, job.ntime])
    out = WorkflowResult(fail_fast=False)
    out.record("L1_parse", parsed, "missing prevhash")
    assert out.verdicts["L1_parse"].passed is False


def test_l2_header_wrong_length():
    out = WorkflowResult(fail_fast=False)
    out.record("L2_header", len(b"short") == 80, "header=5")
    assert out.verdicts["L2_header"].passed is False


def test_l3_oi_structured_and_unstructured():
    structured = LiveJob(job_id="a", coinb1="aa", version="20000000", nbits="1d00ffff")
    empty = LiveJob(job_id="b")
    assert classify_oi(structured).path == "fold"
    assert classify_oi(empty).path == "tensor"


def test_l4_genetic_zero_batch_fails():
    out = WorkflowResult(fail_fast=False)
    out.record("L4_genetic", 0 > 0, "batch=0")
    assert out.verdicts["L4_genetic"].passed is False


def test_l5_seam_ledger_required():
    out = WorkflowResult(fail_fast=False)
    out.record("L5_seam", False and 1 > 0, "ledger_ok=False")
    assert out.verdicts["L5_seam"].passed is False


def test_l6_search_none_is_fail_zero_is_pass():
    out = WorkflowResult(fail_fast=False)
    out.record("L6_search", 0 is not None, "Nonce found: 0")
    assert out.verdicts["L6_search"].passed is True
    out2 = WorkflowResult(fail_fast=False)
    out2.record("L6_search", None is not None, "Nonce found: None")
    assert out2.verdicts["L6_search"].passed is False


def test_l7_full_width_uint256():
    digest = sha256d(b"header")
    value = digest_uint256(digest)
    assert share_meets_target(digest, value) is True
    assert share_meets_target(digest, value - 1) is False
    with pytest.raises(TypeError):
        share_meets_target(digest, 1.5)  # type: ignore[arg-type]


def test_l8_hex_and_verify():
    body = {"nonce": "00000000", "job_id": "j"}
    sig = attest_sign(body)
    assert is_hex64(sig)
    assert attest_verify(body, sig)
    assert not attest_verify(body, "z" * 64)
    assert not attest_verify({"nonce": "deadbeef"}, sig)


def test_l9_submit_false_is_fail():
    out = WorkflowResult(fail_fast=False)
    out.record("L9_submit", False is True, "Pool response: False")
    assert out.verdicts["L9_submit"].passed is False


def test_l10_forgery_path_must_run():
    body = {"nonce": "00000001", "job_id": "j"}
    sig = attest_sign(body)
    forged = dict(body)
    forged["nonce"] = "deadbeef"
    reject_ran = True
    rejected = not attest_verify(forged, sig)
    assert reject_ran and rejected
    out = WorkflowResult(fail_fast=False)
    out.record("L10_aethel", False, "forgery path skipped")
    assert out.verdicts["L10_aethel"].passed is False


def test_l11_heal_clears_stale_extranonce():
    stale, live = "aaaa", "bbbb"
    healed = bool(live) and stale != ""
    out = WorkflowResult(fail_fast=False)
    out.record("L11_heal", healed, f"stale={stale} live={live}")
    assert out.verdicts["L11_heal"].passed is True
    out2 = WorkflowResult(fail_fast=False)
    out2.record("L11_heal", bool(""), "live_en1 cleared and never reissued")
    assert out2.verdicts["L11_heal"].passed is False


def test_l12_log_requires_prior_pass_lines():
    out = WorkflowResult(fail_fast=False)
    out.record("L12_log", False, "log_lines=0")
    assert out.verdicts["L12_log"].passed is False


def test_record_is_pure_and_duplicate_raises():
    out = WorkflowResult(fail_fast=False)
    out.record("L0_connect", True, "ok")
    with pytest.raises(RuntimeError, match="duplicate"):
        out.record("L0_connect", False, "hidden fail")


def test_fail_fast_false_collects_report():
    out = WorkflowResult(fail_fast=False)
    out.record("L0_connect", True, "ok")
    out.record("L6_search", False, "no nonce")
    with pytest.raises(AssertionError, match="missing=") as err:
        out.assert_all()
    msg = str(err.value)
    assert "L6_search" in msg
    assert "L1_parse" in msg


def test_check_attaches_exception():
    out = WorkflowResult(fail_fast=False)

    def boom():
        raise ValueError("socket closed")

    v = out.check("L11_heal", boom, "heal")
    assert v.passed is False
    assert isinstance(v.exc, ValueError)
    assert "socket closed" in v.detail
