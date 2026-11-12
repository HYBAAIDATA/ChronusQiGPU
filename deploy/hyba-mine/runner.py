"""HYBA Mine runner for the unattended mining host.

Runs the canonical Stratum V1 miner, chronus.execution.mining_entrypoint
(ChronusRealMiningEngine), unchanged, with two operational guards:

* when the pool ends the session, the runner stops the engine, so the process
  exits and the host's container restart policy reconnects with a fresh
  handshake, instead of hashing jobs that can no longer be submitted;
* every 60 seconds it logs one [STATS] line with the engine's own counters.
  Hashing counts are local measurements; a share counts only when the pool
  accepts it ([POOL SUCCESS] lines from the engine).

Configuration is the engine's own (MINING_ACTIVE_POOL and MINING_<POOL>_*).
The worker name is not logged here.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

import bist
from chronus.execution import mining_entrypoint as engine_module

logger = logging.getLogger("HybaMineRunner")
STATS_INTERVAL_SECONDS = 60


class HostMiner(engine_module.ChronusRealMiningEngine):
    """The canonical engine with session-end and statistics guards."""

    async def run(self, max_seconds=None):
        stats_task = asyncio.create_task(self._report_stats())
        try:
            await super().run(max_seconds=max_seconds)
        finally:
            stats_task.cancel()
            await asyncio.gather(stats_task, return_exceptions=True)

    async def _listen_pool_events(self):
        try:
            await super()._listen_pool_events()
        finally:
            if self.running:
                logger.warning("Pool session ended; stopping so the host restarts the miner with a fresh handshake.")
                self.running = False

    async def _report_stats(self):
        started = time.monotonic()
        while True:
            await asyncio.sleep(STATS_INTERVAL_SECONDS)
            logger.info(
                "[STATS] uptime_s=%d sha256d_evaluations=%d shares_found=%d submitted=%d accepted=%d rejected=%d",
                int(time.monotonic() - started),
                self.hashes_computed,
                self.shares_found,
                self.shares_submitted,
                self.shares_accepted,
                self.shares_rejected,
            )


async def main() -> int:
    report = bist.run()
    if report.get("bist") != "PASS":
        logger.error("Mining self-test failed; refusing pool connection")
        for check in report.get("checks", []):
            if not check.get("passed"):
                logger.error("Failed self-test check=%s error_type=%s",
                             check.get("check", "unknown"), check.get("error", "none"))
        return 1
    logger.info("Mining self-test passed")
    pool, host, port, user, password = engine_module.load_env_config()
    logger.info("HYBA Mine: pool %s at %s:%d", pool, host, port)
    miner = HostMiner(host, port, user, password)
    max_seconds_text = os.getenv("MINING_MAX_SECONDS", "").strip()
    await miner.run(max_seconds=int(max_seconds_text) if max_seconds_text else None)
    logger.info("Session closed: sha256d_evaluations=%d accepted=%d rejected=%d",
                miner.hashes_computed, miner.shares_accepted, miner.shares_rejected)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
