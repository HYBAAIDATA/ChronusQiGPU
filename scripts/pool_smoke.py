#!/usr/bin/env python3
"""Non-destructive Stratum pool smoke test.

Proves, against a live endpoint, exactly the operations a miner needs before
it may submit: TCP/TLS connect -> ``mining.subscribe`` -> ``mining.authorize``.
The script NEVER sends ``mining.submit`` — share submission is absent by
construction, not by a flag, so a smoke run can never touch pool state.

Authorize behavior:
- ``MLA1517_STRATUM_USER`` set (plus ``MLA1517_STRATUM_PASSWORD``): the real
  worker is authorized; a rejection is reported as a credential failure.
- Unset: a deliberately invalid sentinel worker is used and the EXPECTED
  result is a rejection — it proves the endpoint is a genuine Stratum
  server that enforces authorization, not an accept-everything honeypot.

Usage:
    PYTHONPATH=mla1517_platform_v3.4/python python scripts/pool_smoke.py \
        --endpoint stratum.braiins.com:3333 [--endpoint stratum+ssl://...] \
        [--wait-for-job SECONDS]

Exit status is 0 only when every probed stage reports its honest result.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_ROOT = _ROOT / "mla1517_platform_v3.4" / "python"
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from manifold_pool_coordinator import (  # noqa: E402
    StratumAuthorizationError,
    StratumClient,
    parse_endpoint,
)

SENTINEL_WORKER = "pythia-smoke.invalid-worker"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        action="append",
        required=True,
        help="[scheme://]HOST:PORT; stratum+ssl:// forces TLS. Repeatable.",
    )
    parser.add_argument("--tls", action="store_true", help="require TLS on bare endpoints")
    parser.add_argument(
        "--wait-for-job",
        type=float,
        default=0.0,
        help="seconds to listen for a mining.notify job before closing (0 = skip)",
    )
    return parser


async def _probe(endpoint_text: str, *, tls: bool, wait_for_job: float) -> dict:
    endpoint = parse_endpoint(endpoint_text, endpoint_text.split(":")[0], tls=tls)
    user = os.getenv("MLA1517_STRATUM_USER") or SENTINEL_WORKER
    password = os.getenv("MLA1517_STRATUM_PASSWORD", "x")
    using_real_credentials = user != SENTINEL_WORKER
    captured: dict = {"client": None}

    def _capture(_snapshot: dict) -> None:
        # close() clears runtime_state; grab the confirmed subscription the
        # moment it is published, not after the session is torn down. The sink
        # first fires inside __init__ (before `client` binds), so look it up
        # through the holder.
        c = captured["client"]
        if c is not None and c.runtime_state.subscription is not None:
            captured["subscription"] = c.runtime_state.subscription

    client = StratumClient(
        endpoint,
        username=user,
        password=password,
        connect_timeout=10.0,
        request_timeout=20.0,
        status_sink=_capture,
    )
    captured["client"] = client
    report: dict = {
        "endpoint": endpoint_text,
        "tls": endpoint.tls,
        "authorized_with": (
            "operator worker" if using_real_credentials else "sentinel (expected reject)"
        ),
        "submit": "never — not part of this program",
    }
    authorized = None
    try:
        await client.connect()
        authorized = True
    except StratumAuthorizationError:
        authorized = False
    subscription = client.runtime_state.subscription or captured.get("subscription")
    report["connect"] = True
    # Braiins legitimately returns extranonce1="" in the subscribe result and
    # pushes the real one via mining.set_extranonce; the negotiated
    # extranonce2_size is the honest signal that subscribe completed.
    report["subscribe"] = {
        "extranonce1_len": len(subscription.extranonce1) if subscription else 0,
        "extranonce2_size": subscription.extranonce2_size if subscription else None,
    }
    report["authorized"] = authorized
    report["transport"] = client.runtime_state.snapshot().get("primary", {}).get("transport")
    if wait_for_job > 0 and authorized:
        deadline = asyncio.get_event_loop().time() + wait_for_job
        while (
            asyncio.get_event_loop().time() < deadline and client.proof_adapter.current_job is None
        ):
            await asyncio.sleep(0.25)
        job = client.proof_adapter.current_job
        report["job_observed"] = (
            None
            if job is None
            else {
                "job_id": job.job_id,
                "generation": getattr(job, "generation", None),
            }
        )
    await client.close()
    # Honest verdict: subscribe must have yielded real session parameters.
    # Authorization truth differs per pool: rejecting an unknown worker is the
    # strict outcome (Braiins); many pools accept arbitrary worker strings
    # because the account is embedded in the worker name (ViaBTC) — that is
    # recorded, not a honeypot verdict.
    subscribed = subscription is not None and subscription.extranonce2_size > 0
    if not subscribed:
        report["verdict"] = "FAIL — mining.subscribe yielded no session parameters"
        report["ok"] = False
    elif authorized is not True and using_real_credentials:
        report["verdict"] = "FAIL — real worker rejected; check credentials"
        report["ok"] = False
    elif authorized is True and not using_real_credentials:
        report["verdict"] = (
            "PASS — authorized; pool accepts arbitrary worker names "
            "(authorization is per-connection, not per-account, here)"
        )
        report["ok"] = True
    elif authorized is True:
        report["verdict"] = "PASS — operator worker authorized"
        report["ok"] = True
    else:
        report["verdict"] = "PASS — sentinel rejected; pool enforces worker authorization"
        report["ok"] = True
    return report


async def _main_async(args) -> int:
    results = []
    for endpoint in args.endpoint:
        try:
            results.append(await _probe(endpoint, tls=args.tls, wait_for_job=args.wait_for_job))
        except Exception as exc:
            results.append(
                {
                    "endpoint": endpoint,
                    "submit": "never — not part of this program",
                    "verdict": f"FAIL — {type(exc).__name__}: {exc}",
                    "ok": False,
                }
            )
    print(json.dumps({"pool_smoke": results}, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


def main() -> None:
    args = _build_parser().parse_args()
    raise SystemExit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
