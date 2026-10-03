from pathlib import Path

from bench.chronus_igpu_evidence import (
    UNAVAILABLE,
    _rapl_delta,
    _rapl_snapshot,
    _sensor_rows,
    roofline_record,
    validate_artifact,
)


def test_roofline_is_unavailable_without_real_peak_inputs():
    record = roofline_record(4.0, 20.0, peak_gflops=None, peak_bandwidth_gbps=None)
    assert record["classification"] == UNAVAILABLE
    assert record["ridge_point_flops_per_byte"] == UNAVAILABLE


def test_roofline_classifies_from_supplied_evidence():
    memory = roofline_record(2.0, 20.0, peak_gflops=400.0, peak_bandwidth_gbps=50.0)
    compute = roofline_record(10.0, 200.0, peak_gflops=400.0, peak_bandwidth_gbps=50.0)
    assert memory["classification"] == "memory_bound"
    assert memory["attainable_gflops"] == 100.0
    assert compute["classification"] == "compute_bound"


def test_gpu_hwmon_reads_real_files_only(tmp_path: Path):
    hwmon = tmp_path / "class/drm/card0/device/hwmon/hwmon0"
    hwmon.mkdir(parents=True)
    (hwmon / "temp1_input").write_text("55000")
    (hwmon / "power1_average").write_text("12500000")
    rows = _sensor_rows(tmp_path)
    assert rows[0]["temperature_c"] == 55.0
    assert rows[0]["power_w"] == 12.5


def test_rapl_wraparound_and_scope_are_explicit(tmp_path: Path):
    # Real sysfs domains are intel-rapl:N; NTFS forbids ':' in names.
    domain = tmp_path / "class/powercap/intel-rapl0"
    domain.mkdir(parents=True)
    (domain / "name").write_text("package-0")
    (domain / "max_energy_range_uj").write_text("1000")
    (domain / "energy_uj").write_text("900")
    before = _rapl_snapshot(tmp_path)
    (domain / "energy_uj").write_text("100")
    after = _rapl_snapshot(tmp_path)
    rows = _rapl_delta(before, after, 0.2)
    assert rows[0]["energy_j"] == 0.0002
    assert rows[0]["scope"] == "package_proxy"


def test_artifact_validation_rejects_non_hardware_samples():
    artifact = {
        "schema": "chronus.igpu-evidence.v1",
        "device": {"available": True},
        "samples": [
            {
                "evidence": {"hardware_executed": False, "wall_time_ns": 1},
                "correctness": {"passed": True},
            }
        ],
        "artifact_sha256": "not-relevant",
    }
    try:
        validate_artifact(artifact)
    except ValueError as exc:
        assert "non-hardware" in str(exc)
    else:
        raise AssertionError("non-hardware artifact was accepted")
