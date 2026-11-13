"""Fleet capacity accounting for Chronus hosts (invariant I64).

Five quantities are kept apart, and each comes from its own source:

* discovered: what the host reports (logical CPUs, CPU affinity, the cgroup CPU
  limit, memory) and, for a device lane set, the device's compute units;
* available: what this process may use (affinity bounded by the cgroup limit,
  or the device's compute units);
* allocated: the lanes a workload has taken;
* calibrated: the rate the allocated lanes reached on this host when they were
  qualified, measured on the lanes themselves;
* measured: work actually executed, from the workload's own counters.

No figure is assumed or copied from elsewhere. Rates are whole units of work
per second, computed from integer nanosecond clocks.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

NS_PER_S = 1_000_000_000


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def parse_cgroup_v2_cpu_max(text: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse cgroup v2 cpu.max ("max 100000" or "200000 100000") to (quota, period)."""
    if not text:
        return None
    parts = text.split()
    if len(parts) != 2 or parts[0] == "max":
        return None
    try:
        quota, period = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if quota <= 0 or period <= 0:
        return None
    return quota, period


def parse_cgroup_v1_cpu(quota_text: Optional[str], period_text: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse cgroup v1 cpu.cfs_quota_us and cpu.cfs_period_us; a quota of -1 means no limit."""
    if not quota_text or not period_text:
        return None
    try:
        quota, period = int(quota_text.strip()), int(period_text.strip())
    except ValueError:
        return None
    if quota <= 0 or period <= 0:
        return None
    return quota, period


def parse_meminfo_total(text: Optional[str]) -> Optional[int]:
    """MemTotal from /proc/meminfo, in bytes."""
    for line in (text or "").splitlines():
        if line.startswith("MemTotal:"):
            fields = line.split()
            if len(fields) >= 2 and fields[1].isdigit():
                return int(fields[1]) * 1024
    return None


@dataclass(frozen=True)
class HostCapacity:
    """What the host reports about itself."""

    logical_cpus: int
    affinity_cpus: int
    cgroup_cpu_quota: Optional[Tuple[int, int]]
    memory_bytes: Optional[int]

    @property
    def cgroup_cpus(self) -> Optional[int]:
        """Whole CPUs the cgroup limit covers (at least one), or None without a limit."""
        if self.cgroup_cpu_quota is None:
            return None
        quota, period = self.cgroup_cpu_quota
        return max(1, quota // period)

    @property
    def available_cpus(self) -> int:
        limit = self.cgroup_cpus
        available = self.affinity_cpus if limit is None else min(self.affinity_cpus, limit)
        return max(1, available)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "logical_cpus": self.logical_cpus,
            "affinity_cpus": self.affinity_cpus,
            "cgroup_cpus": self.cgroup_cpus,
            "available_cpus": self.available_cpus,
            "memory_bytes": self.memory_bytes,
        }


def discover_host(*, cgroup_root: str = "/sys/fs/cgroup", proc_root: str = "/proc") -> HostCapacity:
    """Read the host's own report of its CPUs, CPU limit and memory."""
    logical = os.cpu_count() or 1
    try:
        affinity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = logical
    quota = parse_cgroup_v2_cpu_max(_read(os.path.join(cgroup_root, "cpu.max")))
    if quota is None:
        quota = parse_cgroup_v1_cpu(
            _read(os.path.join(cgroup_root, "cpu", "cpu.cfs_quota_us")),
            _read(os.path.join(cgroup_root, "cpu", "cpu.cfs_period_us")),
        )
    memory = parse_meminfo_total(_read(os.path.join(proc_root, "meminfo")))
    return HostCapacity(logical, max(1, affinity), quota, memory)


def rate_per_second(work: int, elapsed_ns: int) -> int:
    """Whole units of work per second; zero when no time has elapsed."""
    if work < 0 or elapsed_ns < 0:
        raise ValueError("work and elapsed time must be non-negative")
    if elapsed_ns == 0:
        return 0
    return work * NS_PER_S // elapsed_ns


class CapacityLedger:
    """Allocated lanes, the calibrated rate and measured work for one workload on one host."""

    def __init__(
        self,
        workload: str,
        host: HostCapacity,
        backend: str,
        available_lanes: int,
        allocated_lanes: int,
        device: Optional[Dict[str, Any]] = None,
        clock_ns=time.perf_counter_ns,
    ) -> None:
        if available_lanes < 1 or allocated_lanes < 1:
            raise ValueError("available and allocated lanes must be positive")
        if allocated_lanes > available_lanes:
            raise ValueError("allocated lanes exceed the available lanes")
        self.workload = workload
        self.host = host
        self.backend = backend
        self.available_lanes = available_lanes
        self.allocated_lanes = allocated_lanes
        self.device = dict(device or {})
        self._clock_ns = clock_ns
        self._lock = threading.Lock()
        self._started_ns = clock_ns()
        self._window_started_ns = self._started_ns
        self._work_total = 0
        self._busy_ns_total = 0
        self._window_work = 0
        self.calibration_work = 0
        self.calibration_ns = 0

    def record_calibration(self, work: int, elapsed_ns: int) -> None:
        if work <= 0 or elapsed_ns <= 0:
            raise ValueError("calibration needs executed work and elapsed time")
        self.calibration_work = work
        self.calibration_ns = elapsed_ns

    def record(self, work: int, elapsed_ns: int) -> None:
        """Record work the lanes executed and the time they spent executing it."""
        if work < 0 or elapsed_ns < 0:
            raise ValueError("work and elapsed time must be non-negative")
        with self._lock:
            self._work_total += work
            self._busy_ns_total += elapsed_ns
            self._window_work += work

    @property
    def calibrated_per_s(self) -> int:
        return rate_per_second(self.calibration_work, self.calibration_ns)

    def report(self) -> Dict[str, Any]:
        """The five quantities, kept apart; the measured window restarts after each report."""
        now = self._clock_ns()
        with self._lock:
            window_ns = now - self._window_started_ns
            window_work = self._window_work
            self._window_work = 0
            self._window_started_ns = now
            work_total = self._work_total
            busy_ns = self._busy_ns_total
        report = {
            "workload": self.workload,
            "backend": self.backend,
            "device": self.device or None,
            "discovered": self.host.as_dict(),
            "available_lanes": self.available_lanes,
            "allocated_lanes": self.allocated_lanes,
            "calibrated_per_s": self.calibrated_per_s,
            "measured_per_s": rate_per_second(window_work, window_ns),
            "measured_per_s_lifetime": rate_per_second(work_total, now - self._started_ns),
            "measured_per_s_while_busy": rate_per_second(work_total, busy_ns),
            "work_total": work_total,
        }
        report["violations"] = self.violations(report)
        return report

    def violations(self, report: Dict[str, Any]) -> List[str]:
        """I64 checks: allocation within availability, measured rates from executed work only."""
        problems = []
        if report["allocated_lanes"] > report["available_lanes"]:
            problems.append("allocated lanes exceed available lanes")
        if self.backend == "process-lanes" and report["available_lanes"] > self.host.logical_cpus:
            problems.append("available lanes exceed the host's logical CPUs")
        if report["measured_per_s_lifetime"] > report["measured_per_s_while_busy"]:
            problems.append("lifetime rate exceeds the busy rate")
        return problems
