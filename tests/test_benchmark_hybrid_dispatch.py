"""Smoke tests for the hybrid dispatch benchmark harness."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import benchmarks.hybrid_dispatch_benchmark as hyb


def test_scheduler_reports_honest_capability():
    dev = hyb.HonestCpuScheduler("cpu:test")
    cap = dev.capability()
    assert cap.supported
    assert cap.device_class == "cpu_in_process"
    assert cap.measured_hashes_per_sec > 0


def test_coordinator_run_single_job_verifies():
    from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
    from benchmarks.common import synthetic_header

    job = StratumJob(
        job_id="t0",
        header80=synthetic_header(800_000),
        target=hyb.JOB_TARGET_INT.to_bytes(32, "big"),
        nonce_space=1 << 15,
    )
    coord = HybridCoordinator(
        hyb.HonestCpuScheduler("cpu:A"), hyb.HonestCpuScheduler("cpu:B")
    )
    result = coord.run_job(job, strategy="even")
    assert result.certificate.verify()
    assert hyb._span_overlaps(result) == 0
    if result.share is not None:
        from hyba.hybrid.nonce_scheduler import verify_share

        assert verify_share(result.share, job.header80[:76], job.target)


def test_partition_disjoint_under_both_strategies():
    from hyba.hybrid.lucas_partition import partition

    devs = [hyb.HonestCpuScheduler("cpu:A"), hyb.HonestCpuScheduler("cpu:B")]
    for strategy in ("even", "lucas"):
        spans, cert = partition(1 << 15, devs, strategy=strategy)
        assert cert.verify()
        total = sorted((s.base_nonce, s.base_nonce + s.span) for s in spans)
        cursor = 0
        for base, end in total:
            assert base == cursor
            cursor = end
        assert cursor == 1 << 15
