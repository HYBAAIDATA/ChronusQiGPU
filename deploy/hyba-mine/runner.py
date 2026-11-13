"""HYBA Mine runner: the two-block campaign at the mining host's full capacity.

Before any pool connection, every lane set on the host (the OpenCL iGPU lanes
and one process lane per available CPU) is qualified against the host reference
and calibrated, and the fastest qualified set takes the whole host. Then the
campaign runs (hyba_mine.campaign): one block on the first pool, a cool-down,
a non-consecutive block on the second pool, then offline. Capacity is reported
once a minute ([CAPACITY]) with discovered, available and allocated lanes, the
calibrated rate and the measured rate kept apart. A share counts only when the
pool accepts it ([POOL SUCCESS] lines).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import bist

from chronus.execution import mining_entrypoint as engine_module

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("HybaMine.runner")


async def main() -> int:
    report = bist.run()
    if report.get("bist") != "PASS":
        logger.error("Mining self-test failed; refusing pool connection")
        for check in report.get("checks", []):
            if not check.get("passed"):
                logger.error(
                    "Failed self-test check=%s error_type=%s",
                    check.get("check", "unknown"),
                    check.get("error", "none"),
                )
        return 1

    from hyba_mine.campaign import parse_pools, run_campaign
    from hyba_mine.lanes import open_lanes

    from chronus.fleet.capacity import CapacityLedger, discover_host

    pools = parse_pools(os.getenv("HYBA_MINE_POOLS", "viabtc,braiins"))
    max_run_seconds = int(os.getenv("HYBA_MINE_MAX_RUN_SECONDS", "14400"))
    campaign_id = os.getenv("HYBA_MINE_CAMPAIGN_ID", "local")
    state_path = os.getenv("HYBA_MINE_STATE", "/var/lib/hyba-mine/campaign.json")

    host = discover_host()
    logger.info("[CAPACITY] discovered %s", json.dumps(host.as_dict(), sort_keys=True))
    process_lanes = int(os.getenv("HYBA_MINE_PROCESS_LANES", "0")) or None
    lanes, reports = await asyncio.to_thread(
        open_lanes, os.getenv("HYBA_MINE_LANES", "auto"), process_lanes
    )
    for report in reports:
        logger.info("[LANES] qualification %s", json.dumps(report, sort_keys=True))
    selected = next(report for report in reports if report.get("selected"))
    available = host.available_cpus if lanes.name == "process-lanes" else lanes.lanes
    ledger = CapacityLedger(
        "SHA256D_NONCE_SEARCH",
        host,
        lanes.name,
        available_lanes=available,
        allocated_lanes=lanes.lanes,
        device=lanes.describe().get("device"),
    )
    ledger.record_calibration(
        selected["calibration"]["work"], selected["calibration"]["elapsed_ns"]
    )
    logger.info("[CAPACITY] %s", json.dumps(ledger.report(), sort_keys=True))
    logger.info(
        "[CAMPAIGN] %s: pools %s, at most %d s",
        campaign_id,
        ",".join(pools),
        max_run_seconds,
    )

    try:
        await run_campaign(
            engine_module,
            pools,
            lanes,
            ledger,
            max_run_seconds=max_run_seconds,
            state_path=state_path,
            campaign_id=campaign_id,
        )
    finally:
        lanes.close()
        logger.info("[CAPACITY] final %s", json.dumps(ledger.report(), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
