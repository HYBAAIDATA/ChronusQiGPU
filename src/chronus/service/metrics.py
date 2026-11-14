"""Prometheus counters. No-ops if prometheus_client is absent."""

from __future__ import annotations

from fastapi import APIRouter, Response

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
except ImportError:  # metrics are optional, startup is not
    CONTENT_TYPE_LATEST = "text/plain"
    Counter = Histogram = None
    generate_latest = None

router = APIRouter()


if Counter is not None:
    SHARES_SUBMITTED = Counter("chronus_shares_submitted_total", "Shares submitted")
    SHARES_ACCEPTED = Counter("chronus_shares_accepted_total", "Shares accepted")
    SHARES_REJECTED = Counter("chronus_shares_rejected_total", "Shares rejected")
    SHARE_LATENCY = Histogram("chronus_share_ack_seconds", "Pool ack latency")
    HASHRATE_BATCHES = Counter("chronus_nonce_batches_total", "Nonce batches searched")
else:  # pragma: no cover
    class _NoOp:
        def inc(self, *a, **k):
            pass

        def observe(self, *a, **k):
            pass

    SHARES_SUBMITTED = SHARES_ACCEPTED = SHARES_REJECTED = HASHRATE_BATCHES = _NoOp()
    SHARE_LATENCY = _NoOp()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    if generate_latest is None:
        return Response("prometheus_client not installed\n", media_type="text/plain")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
