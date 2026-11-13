"""HYBA Mine campaign: two non-consecutive blocks, one pool each.

Stage 1 mines on the first pool from the first job it sends (block height N)
until that pool accepts a share or the network moves past N. Stage 2 connects
to the second pool and cools down (no hashing) until a job for height N + 2 or
later arrives, so the two blocks are not consecutive, then mines that block
until the second pool accepts a share or the network moves on. Then hashing
stops, the pool session closes and the process exits: the host goes offline
for mining. HYBA_MINE_MAX_RUN_SECONDS bounds the whole campaign.

Every method a pool pushes is counted, and anything outside the Stratum V1
methods the miner expects is logged as [POOL PUSH] UNEXPECTED for the
examination after the campaign. A share counts only when the pool accepts it.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from hyba_mine.search import LaneSearchMixin

logger = logging.getLogger("HybaMine.campaign")
NS_PER_S = 1_000_000_000
ACK_GRACE_NS = 15 * NS_PER_S
STATS_INTERVAL_SECONDS = 60
POOLS = ("viabtc", "braiins")
STAGE_END_REASONS = frozenset({"share_accepted", "block_ended", "max_run_time"})
EXPECTED_PUSH_METHODS = frozenset(
    {"mining.notify", "mining.set_difficulty", "mining.set_version_mask", "mining.set_extranonce"}
)


def read_varint(data: bytes, pos: int) -> Tuple[int, int]:
    """Bitcoin CompactSize integer at data[pos]: (value, next position)."""
    if pos >= len(data):
        raise ValueError("truncated varint")
    first = data[pos]
    if first < 0xFD:
        return first, pos + 1
    width = {0xFD: 2, 0xFE: 4, 0xFF: 8}[first]
    if pos + 1 + width > len(data):
        raise ValueError("truncated varint")
    return int.from_bytes(data[pos + 1:pos + 1 + width], "little"), pos + 1 + width


def coinbase_height(coinb1_hex: str) -> Optional[int]:
    """Block height from the BIP34 push at the start of the coinbase script, or None."""
    try:
        data = bytes.fromhex(coinb1_hex)
        pos = 4
        inputs, pos = read_varint(data, pos)
        if inputs != 1 or data[pos:pos + 32] != bytes(32) or data[pos + 32:pos + 36] != b"\xff" * 4:
            return None
        pos += 36
        _, pos = read_varint(data, pos)
        push = data[pos]
    except (ValueError, IndexError, KeyError):
        return None
    if 1 <= push <= 8 and pos + 1 + push <= len(data):
        return int.from_bytes(data[pos + 1:pos + 1 + push], "little")
    if 0x51 <= push <= 0x60:
        return push - 0x50
    return None


def pool_config(pool: str) -> Tuple[str, int, str, str]:
    """Host, port, worker and password for a pool from MINING_<POOL>_* settings."""
    prefix = f"MINING_{pool.upper()}_"
    host = os.getenv(prefix + "HOST", "").strip()
    port_text = os.getenv(prefix + "PORT", "").strip()
    user = os.getenv(prefix + "USER", "").strip()
    password = os.getenv(prefix + "PASSWORD", "")
    if not host or not port_text or not user or not password:
        raise ValueError(f"configure {prefix}HOST, PORT, USER and PASSWORD")
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError(f"{prefix}PORT must be between 1 and 65535")
    return host, port, user, password


def parse_pools(text: str) -> List[str]:
    pools = [item.strip().lower() for item in text.split(",") if item.strip()]
    if not pools or len(pools) != len(set(pools)) or any(pool not in POOLS for pool in pools):
        raise ValueError(f"HYBA_MINE_POOLS must list distinct pools from {POOLS}")
    return pools


class StageControlMixin:
    """Block-height gating, stage end conditions and pool-push records for one stage."""

    def _init_stage(self, stage: str, min_height: Optional[int], deadline_ns: Optional[int]) -> None:
        self.stage = stage
        self.min_height = min_height
        self.deadline_ns = deadline_ns
        self.stage_height: Optional[int] = None
        self.end_reason: Optional[str] = None
        self.heights_seen: List[Tuple[int, str]] = []
        self.push_methods: collections.Counter = collections.Counter()
        self._cooling_height: Optional[int] = None
        original = self.gateway.handle_server_push

        async def recorded(message):
            method = str(message.get("method", ""))[:64]
            self.push_methods[method] += 1
            if method not in EXPECTED_PUSH_METHODS:
                logger.warning("[POOL PUSH] UNEXPECTED method=%s from %s", method, stage)
            return await original(message)

        self.gateway.handle_server_push = recorded

    def _end_stage(self, reason: str) -> None:
        if self.end_reason is None:
            self.end_reason = reason
            logger.info("[CAMPAIGN] stage %s ending: %s", self.stage, reason)

    def _gate(self, job) -> bool:
        """True when this job's block is the stage's block and the stage is still open."""
        if self.end_reason is not None:
            return False
        if self.deadline_ns is not None and time.perf_counter_ns() >= self.deadline_ns:
            self._end_stage("max_run_time")
            return False
        height = coinbase_height(job.get("coinb1_hex", ""))
        if height is None:
            self._end_stage("block_height_unreadable")
            return False
        if not self.heights_seen or self.heights_seen[-1][0] != height:
            self.heights_seen.append((height, str(job.get("prevhash_hex", ""))[:16]))
            logger.info("[CAMPAIGN] %s sent a job for block height %d", self.stage, height)
        if self.min_height is not None and height < self.min_height:
            if self._cooling_height != height:
                self._cooling_height = height
                logger.info("[CAMPAIGN] cooling down at height %d; %s mines from height %d",
                            height, self.stage, self.min_height)
            return False
        if self.stage_height is None:
            self.stage_height = height
            logger.info("[CAMPAIGN] stage %s mining block height %d", self.stage, height)
            return True
        if height > self.stage_height:
            self._end_stage("block_ended")
            return False
        return height == self.stage_height


def make_stage_miner(engine_module):
    """The canonical engine with lane search and stage control; the engine itself is unchanged."""

    class StageMiner(StageControlMixin, LaneSearchMixin, engine_module.ChronusRealMiningEngine):
        def _search_nonce_batch(self, job, merkle_root_bytes, pool_mask_hex, share_target):
            if not self._gate(job):
                time.sleep(0.5)
                return None
            return self._lane_search(job, merkle_root_bytes, pool_mask_hex, share_target)

        async def _listen_pool_events(self):
            # The engine listener retries socket-read errors forever; here a read error
            # ends the stage instead, so the campaign can reconnect.
            read_line = self.gateway.read_line

            async def read_line_or_close():
                try:
                    return await read_line()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("[CAMPAIGN] pool read failed: %s", type(exc).__name__)
                    return b""

            self.gateway.read_line = read_line_or_close
            try:
                await super()._listen_pool_events()
            finally:
                self.gateway.read_line = read_line
                if self.running:
                    self._end_stage("pool_session_ended")

        async def _watch_stage(self):
            while self.running:
                await asyncio.sleep(0.5)
                if self.shares_accepted > 0:
                    self._end_stage("share_accepted")
                if self.deadline_ns is not None and time.perf_counter_ns() >= self.deadline_ns:
                    self._end_stage("max_run_time")
                if self.end_reason is None:
                    continue
                grace_end = time.perf_counter_ns() + ACK_GRACE_NS
                while (
                    self.end_reason != "pool_session_ended"
                    and self.shares_submitted > self.shares_accepted + self.shares_rejected
                    and time.perf_counter_ns() < grace_end
                ):
                    await asyncio.sleep(0.25)
                self.running = False
                return

        async def _report_stats(self):
            while True:
                await asyncio.sleep(STATS_INTERVAL_SECONDS)
                logger.info(
                    "[STATS] stage=%s height=%s sha256d_evaluations=%d window=%d shares_found=%d "
                    "submitted=%d accepted=%d rejected=%d",
                    self.stage, self.stage_height, self.hashes_computed, self.window,
                    self.shares_found, self.shares_submitted, self.shares_accepted, self.shares_rejected,
                )
                logger.info("[CAPACITY] %s", json.dumps(self.ledger.report(), sort_keys=True))

        async def run(self, max_seconds=None):
            watcher = asyncio.create_task(self._watch_stage())
            stats = asyncio.create_task(self._report_stats())
            try:
                await super().run(max_seconds=max_seconds)
            finally:
                watcher.cancel()
                stats.cancel()

    return StageMiner


def stage_result(index: int, pool: str, miner, attempt: int) -> Dict[str, Any]:
    pushes = dict(getattr(miner, "push_methods", {}))
    return {
        "stage": index + 1,
        "pool": pool,
        "attempt": attempt,
        "block_height": getattr(miner, "stage_height", None),
        "heights_seen": [height for height, _ in getattr(miner, "heights_seen", [])],
        "end_reason": getattr(miner, "end_reason", None),
        "sha256d_evaluations": miner.hashes_computed,
        "shares_found": miner.shares_found,
        "submitted": miner.shares_submitted,
        "accepted_by_pool": miner.shares_accepted,
        "rejected_by_pool": miner.shares_rejected,
        "lane_recheck_failures": getattr(miner, "lane_recheck_failures", 0),
        "push_methods": pushes,
        "unexpected_push_methods": sorted(m for m in pushes if m not in EXPECTED_PUSH_METHODS),
    }


def load_state(path: str, campaign_id: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        if state.get("campaign_id") == campaign_id:
            return state
    except (OSError, ValueError):
        pass
    return {"campaign_id": campaign_id, "stages": [], "last_height": None, "complete": False}


def save_state(path: str, state: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(state, handle, sort_keys=True)
    os.replace(temporary, path)


async def run_campaign(engine_module, pools: List[str], lanes, ledger, *, max_run_seconds: int,
                       state_path: str, campaign_id: str, connect_attempts: int = 3) -> Dict[str, Any]:
    """Run the stages in order; the state file lets a restarted container resume."""
    deadline = time.perf_counter_ns() + max_run_seconds * NS_PER_S if max_run_seconds > 0 else None
    state = load_state(state_path, campaign_id)
    if state.get("complete"):
        logger.info("[CAMPAIGN] %s is already complete; the miner stays offline", campaign_id)
        return state
    stage_miner = make_stage_miner(engine_module)
    for index, pool in enumerate(pools):
        if index < len(state["stages"]):
            continue
        host, port, user, password = pool_config(pool)
        min_height = None if state["last_height"] is None else state["last_height"] + 2
        result = None
        stage_done = False
        for attempt in range(1, connect_attempts + 1):
            miner = stage_miner(host, port, user, password)
            miner._init_lane_search(lanes, ledger)
            miner._init_stage(pool, min_height, deadline)
            try:
                # The campaign deadline also bounds connection and handshake.
                timeout = None if deadline is None else max(0.0, (deadline - time.perf_counter_ns()) / NS_PER_S)
                await asyncio.wait_for(miner.run(), timeout)
            except asyncio.TimeoutError:
                miner._end_stage("max_run_time")
            except Exception as exc:  # connection and session errors end this attempt
                miner._end_stage(f"session_error:{type(exc).__name__}")
            result = stage_result(index, pool, miner, attempt)
            if miner.stage_height is not None and miner.end_reason in STAGE_END_REASONS:
                stage_done = True
                break
            if deadline is not None and time.perf_counter_ns() >= deadline:
                break
            if miner.stage_height is not None:
                min_height = miner.stage_height  # the next attempt mines the same block
            await asyncio.sleep(10)
        if not stage_done:
            state["failure"] = result
            state["complete"] = False
            save_state(state_path, state)
            logger.error("[CAMPAIGN] stage %d on %s did not finish; the campaign failed: %s",
                         index + 1, pool, json.dumps(result, sort_keys=True))
            return state
        state["failure"] = None
        state["stages"].append(result)
        if result["block_height"] is not None:
            state["last_height"] = result["block_height"]
        save_state(state_path, state)
        logger.info("[CAMPAIGN] stage result %s", json.dumps(result, sort_keys=True))
        if result["end_reason"] == "max_run_time":
            break
    state["complete"] = True
    save_state(state_path, state)
    logger.info("[CAMPAIGN] complete: hashing stopped and pool sessions closed; the miner goes offline")
    logger.info("[CAMPAIGN] summary %s", json.dumps(state, sort_keys=True))
    return state
