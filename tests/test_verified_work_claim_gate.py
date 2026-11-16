"""No synthetic benchmark used as performance evidence; contract tests only."""
from copy import deepcopy
import pytest
from benchmarks.verify_11_5_claim import characterize


def sample():
    return {
        "schema": "chronus.real-workload/1",
        "result": "PASS",
        "data_generated_by_benchmark": False,
        "git_commit": "a" * 40,
        "input_count": 1,
        "entries": [{
            "source_sha256": "b" * 64,
            "source_class": "TEST_FIXTURE_NON_PRODUCTION",
            "workload": {
                "operation": "tensor_reference_add_and_pulvini",
                "addition_exact_match": True,
                "pulvini": {
                    "input_promoted_bytes": 1150,
                    "working_set_bytes": 100,
                    "kernel_bytes": 1700,
                    "complete_retained_bytes": 1800,
                    "numerical_reconstruction_verified": True,
                    "relative_reconstruction_error": 1e-16,
                    "net_storage_compression_claim": False,
                },
            },
        }],
    }


def test_11_5_active_ratio_does_not_verify_work_or_net_storage():
    evidence = characterize(sample(), expected_sha="a" * 40)
    assert evidence["claim_status"] == "HELD"
    assert evidence["11_5x_verified_work_proven"] is False
    assert evidence["tensor_records"][0]["active_working_set_ratio"] == 11.5
    assert evidence["tensor_records"][0]["complete_retained_ratio"] < 1
    assert evidence["production_qualified"] is False


def test_refuse_bad_sha_and_missing_kernels():
    with pytest.raises(ValueError, match="commit mismatch"):
        characterize(sample(), expected_sha="c" * 40)
    data = sample()
    data["entries"][0]["workload"]["pulvini"]["complete_retained_bytes"] = 100
    with pytest.raises(ValueError, match="inconsistent retained"):
        characterize(data)


def test_refuse_auto_promoted_claim_and_wrong_work():
    data = sample()
    data["entries"][0]["workload"]["pulvini"]["net_storage_compression_claim"] = True
    with pytest.raises(ValueError, match="net-compression"):
        characterize(data)
    data = sample()
    data["entries"][0]["workload"]["addition_exact_match"] = False
    with pytest.raises(ValueError, match="incorrect useful work"):
        characterize(data)


def test_refuse_fake_inputs_and_invalid_numerical_error():
    data = sample()
    data["data_generated_by_benchmark"] = True
    with pytest.raises(ValueError):
        characterize(data)
    data = sample()
    data["entries"][0]["workload"]["pulvini"]["relative_reconstruction_error"] = float("nan")
    with pytest.raises(ValueError, match="tolerance"):
        characterize(data)
