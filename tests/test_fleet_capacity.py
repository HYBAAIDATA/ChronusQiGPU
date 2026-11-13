"""Fleet capacity accounting (I64): each quantity from its own source."""

import pytest

from chronus.fleet.capacity import (
    CapacityLedger,
    HostCapacity,
    discover_host,
    parse_cgroup_v1_cpu,
    parse_cgroup_v2_cpu_max,
    parse_meminfo_total,
    rate_per_second,
)


def test_cgroup_v2_max_setting_maps_to_no_quota():
    assert parse_cgroup_v2_cpu_max("max 100000\n") is None
    assert parse_cgroup_v2_cpu_max("150000 100000\n") == (150000, 100000)
    assert parse_cgroup_v2_cpu_max("") is None
    assert parse_cgroup_v2_cpu_max("garbage") is None


def test_cgroup_v1_minus_one_means_no_limit():
    assert parse_cgroup_v1_cpu("-1\n", "100000\n") is None
    assert parse_cgroup_v1_cpu("200000\n", "100000\n") == (200000, 100000)


def test_meminfo_total_in_bytes():
    assert (
        parse_meminfo_total("MemTotal:       8040960 kB\nMemFree: 1 kB\n")
        == 8040960 * 1024
    )
    assert parse_meminfo_total("") is None


def test_available_cpus_are_bounded_by_affinity_and_cgroup_limit():
    host = HostCapacity(
        logical_cpus=8,
        affinity_cpus=6,
        cgroup_cpu_quota=(250000, 100000),
        memory_bytes=None,
    )
    assert host.cgroup_cpus == 2
    assert host.available_cpus == 2
    no_quota = HostCapacity(
        logical_cpus=8, affinity_cpus=6, cgroup_cpu_quota=None, memory_bytes=None
    )
    assert no_quota.available_cpus == 6
    tiny = HostCapacity(
        logical_cpus=4,
        affinity_cpus=4,
        cgroup_cpu_quota=(50000, 100000),
        memory_bytes=None,
    )
    assert tiny.available_cpus == 1


def test_discover_host_reads_files(tmp_path):
    (tmp_path / "cpu.max").write_text("300000 100000\n")
    (tmp_path / "meminfo").write_text("MemTotal: 1024 kB\n")
    host = discover_host(cgroup_root=str(tmp_path), proc_root=str(tmp_path))
    assert host.cgroup_cpu_quota == (300000, 100000)
    assert host.memory_bytes == 1024 * 1024
    assert 1 <= host.available_cpus <= host.logical_cpus


def test_rates_are_integers_from_executed_work():
    assert rate_per_second(3_000_000, 1_500_000_000) == 2_000_000
    assert rate_per_second(10, 0) == 0
    with pytest.raises(ValueError):
        rate_per_second(-1, 1)


def test_ledger_keeps_calibrated_and_measured_apart():
    ticks = iter([0, 2_000_000_000, 4_000_000_000])
    host = HostCapacity(
        logical_cpus=4, affinity_cpus=4, cgroup_cpu_quota=None, memory_bytes=None
    )
    ledger = CapacityLedger(
        "SHA256D_NONCE_SEARCH",
        host,
        "process-lanes",
        available_lanes=4,
        allocated_lanes=4,
        clock_ns=lambda: next(ticks),
    )
    ledger.record_calibration(4_000_000, 1_000_000_000)
    ledger.record(6_000_000, 1_500_000_000)
    first = ledger.report()
    assert first["calibrated_per_s"] == 4_000_000
    assert first["measured_per_s"] == 3_000_000
    assert first["measured_per_s_while_busy"] == 4_000_000
    assert first["violations"] == []
    second = ledger.report()
    assert second["measured_per_s"] == 0
    assert second["work_total"] == 6_000_000


def test_allocation_cannot_exceed_availability():
    host = HostCapacity(
        logical_cpus=2, affinity_cpus=2, cgroup_cpu_quota=None, memory_bytes=None
    )
    with pytest.raises(ValueError):
        CapacityLedger(
            "SHA256D_NONCE_SEARCH",
            host,
            "process-lanes",
            available_lanes=2,
            allocated_lanes=3,
        )
