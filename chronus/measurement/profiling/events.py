"""Kernel profiling — measured wall-clock around a real dispatch.

OpenCL event profiling needs a live OpenCL queue; where one exists the caller
can pass the dispatch callable that enqueues through it. The numbers here are
host-observed nanoseconds — the method field says so, never pretending to be
device timestamps.

Invariants:
    PROF1: every profile has a kernel name.
    PROF2: every profile has a measured duration.
    PROF3: the method declares how duration was observed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .._common import now_ns


@dataclass
class KernelProfile:
    kernel_name: str
    queue_time_ns: int
    submit_time_ns: int
    start_time_ns: int
    end_time_ns: int
    duration_ns: int
    method: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kernel_name": self.kernel_name,
            "queue_time_ns": self.queue_time_ns,
            "submit_time_ns": self.submit_time_ns,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "duration_ns": self.duration_ns,
            "method": self.method,
        }


def profile_kernel(
    kernel_name: str,
    dispatch: Callable[[], Any],
    runs: int = 10,
    method: str = "host_wallclock_perf_counter_ns",
) -> List[KernelProfile]:
    """Run ``dispatch`` ``runs`` times; each duration is one real execution."""
    profiles = []
    for _ in range(max(1, int(runs))):
        submit = now_ns()
        start = now_ns()
        dispatch()
        end = now_ns()
        profiles.append(
            KernelProfile(
                kernel_name=kernel_name,
                queue_time_ns=submit - start,
                submit_time_ns=submit,
                start_time_ns=start,
                end_time_ns=end,
                duration_ns=end - start,
                method=method,
            )
        )
    return profiles
