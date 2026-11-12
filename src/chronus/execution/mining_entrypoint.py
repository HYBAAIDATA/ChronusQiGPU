#!/usr/bin/env python3
"""Authored geometric/Galois mining pipeline with a bounded Stratum V1 session."""

from __future__ import annotations

import asyncio
import hashlib
from fractions import Fraction
import logging
import os
import sys
import time
from typing import Optional, Tuple

from chronus.execution.geometric_galois_miner import GeometricGaloisMiner
from chronus.execution.mining_scheduler import TuringMiningScheduler
from chronus.stratum.endian_engine import swap_prevhash_words, compute_merkle_root_stratum, build_header80
from chronus.stratum.bip310 import (
    apply_version_rolling,
    build_mining_submit_params,
    format_extranonce2,
)
from chronus.stratum.sharding import ShareCandidate, WorkPartitioner
from chronus.stratum.gateway import StratumGateway
from chronus.stratum.gatekeeper import (
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
)
from chronus.stratum.rate_limiter import IntegerNanosecondTokenBucket, PriorityShareQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChronusMiningEntrypoint")


def load_env_config() -> Tuple[str, str, int, str, str]:
    """Reads pool configuration from environment variables or .env file."""
    # Look for .env in current working dir or parents
    for base in [os.getcwd(), os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))]:
        env_file = os.path.join(base, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))
            break

    active_pool = os.getenv("MINING_ACTIVE_POOL", "VIABTC").strip().upper()
    if not active_pool:
        active_pool = "VIABTC"
    if active_pool not in {"VIABTC", "BRAIINS"}:
        raise ValueError("Set MINING_ACTIVE_POOL explicitly to VIABTC or BRAIINS")

    host = os.getenv(f"MINING_{active_pool}_HOST", "").strip()
    port_text = os.getenv(f"MINING_{active_pool}_PORT", "").strip()
    user = os.getenv(f"MINING_{active_pool}_USER", "").strip()
    password = (
        os.getenv(f"MINING_{active_pool}_PASSWORD")
        or os.getenv(f"MINING_{active_pool}_PASS")
        or ""
    )
    if not host or not user or not password or not port_text:
        raise ValueError(
            f"Configure MINING_{active_pool}_HOST, _PORT, _USER, and _PASSWORD before starting"
        )
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError(f"MINING_{active_pool}_PORT must be between 1 and 65535")

    return active_pool, host, port, user, password


class ChronusRealMiningEngine:
    """Geometric/Galois mining runner with verified submissions and bounded work."""

    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        self.gateway = StratumGateway(
            host=self.host,
            port=self.port,
            worker_name=self.user,
            password=self.password,
            shard_count=32,
        )
        self.gatekeeper = LocalPreSubmitGatekeeper()
        self.token_bucket = IntegerNanosecondTokenBucket(rate_per_sec=15)
        self.priority_queue = PriorityShareQueue(maxsize=64)
        self.partitioner = WorkPartitioner(shard_count=32)
        self._scheduler_context = None
        self.scheduler = None

        self.search_engine = GeometricGaloisMiner()
        self.last_search_result = None

        self.nonce_batch_size = int(os.getenv("MINING_NONCE_BATCH", "65536"))
        if not 1 <= self.nonce_batch_size <= (1 << 20):
            raise ValueError("MINING_NONCE_BATCH must be between 1 and 2**20")
        self._nonce_context = None
        self._nonce_cursors = {}
        self._scanned_per_shard = {}
        self._next_shard = 0
        self._nonce_space_exhausted = False
        self._nonce_extranonce_exhausted = False

        self.en2_counter = 0
        self.hashes_computed = 0
        self.shares_found = 0
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.shares_rejected = 0
        self.running = False
        self._pending_submits = {}
        self._submission_changed = asyncio.Event()

    async def run(self, max_seconds: Optional[int] = None):
        """Run one session; the deployment supervisor restarts failed sessions."""
        if max_seconds is not None and (type(max_seconds) is not int or max_seconds <= 0):
            raise ValueError("max_seconds must be a positive integer")
        from chronus.execution.mining_selftest import run as run_selftest

        if run_selftest().get("bist") != "PASS":
            raise RuntimeError("Mining self-test failed; refusing pool connection")
        tasks = []
        self.running = True
        self._nonce_context = None
        self._pending_submits.clear()
        self._submission_changed = asyncio.Event()
        try:
            await self.gateway.connect()
            await self.gateway.execute_handshake()
            logger.info("Handshake complete! Pool Version Mask: 0x%s", self.gateway.pool_mask_hex)
            tasks = [asyncio.create_task(self._listen_pool_events()),
                     asyncio.create_task(self._mining_loop()),
                     asyncio.create_task(self._monitor_submissions())]
            done, _ = await asyncio.wait(
                tasks, timeout=max_seconds, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
        finally:
            self.running = False
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.gateway.close()
            logger.info("Session closed cleanly; unresolved submissions=%d", len(self._pending_submits))

    async def _listen_pool_events(self):
        """Only responses to outstanding mining.submit requests count as shares."""
        while self.running:
            msg = await self.gateway.read_message()
            if msg is None:
                continue
            if "method" in msg:
                await self.gateway.handle_server_push(msg)
                continue
            rpc_id = msg.get("id")
            if type(rpc_id) is not int or rpc_id not in self._pending_submits:
                continue
            if msg.get("result") is not True and msg.get("result") is not False and not msg.get("error"):
                continue
            self._pending_submits.pop(rpc_id)
            self._submission_changed.set()
            if msg.get("result") is True and not msg.get("error"):
                self.shares_accepted += 1
                logger.info("[POOL SUCCESS] Share ACCEPTED (Total accepted: %d)", self.shares_accepted)
            else:
                self.shares_rejected += 1
                logger.warning("[POOL REJECT] Share rejected by pool")

    async def _monitor_submissions(self):
        """Enforce acknowledgement deadlines even during an idle socket read."""
        while self.running:
            self._submission_changed.clear()
            if not self._pending_submits:
                await self._submission_changed.wait()
                continue
            remaining = (min(self._pending_submits.values())
                         + int(self.gateway.pool_timeout_sec * 1_000_000_000)
                         - time.perf_counter_ns()) / 1_000_000_000
            if remaining <= 0:
                raise TimeoutError("Pool submission acknowledgement timed out")
            try:
                await asyncio.wait_for(self._submission_changed.wait(), remaining)
            except asyncio.TimeoutError:
                continue

    def _advance_extranonce(self):
        """Allocate fresh work after all shard ranges are consumed, without wrapping."""
        if self._nonce_extranonce_exhausted:
            return
        self.en2_counter += 1
        if self.en2_counter >= 1 << (8 * self.gateway.extranonce2_size):
            self._nonce_extranonce_exhausted = True
            return
        self._current_extranonce2 = format_extranonce2(self.en2_counter, self.gateway.extranonce2_size)
        self._nonce_cursors.clear()
        self._scanned_per_shard.clear()
        self._nonce_space_exhausted = False

    def _search_nonce_batch(
        self,
        job,
        merkle_root_bytes: bytes,
        pool_mask_hex: str,
        share_target: int,
    ):
        """Search a bounded SHA-256d batch across disjoint shard nonce ranges."""
        base_version = int(job["version_hex"], 16)
        prevhash_bytes = swap_prevhash_words(job["prevhash_hex"])
        ntime = int(job["ntime_hex"], 16)
        nbits = int(job["nbits_hex"], 16)
        shard_count = len(self.partitioner.ranges)
        scheduler_context = (job.get("generation"), job.get("revision"),
                             job["job_id"], merkle_root_bytes, pool_mask_hex)
        if scheduler_context != self._scheduler_context:
            seed = hashlib.sha256(build_header80(
                base_version, prevhash_bytes, merkle_root_bytes, ntime, nbits, 0
            )[:76]).digest()
            self.scheduler = TuringMiningScheduler(seed)
            self._scheduler_context = scheduler_context
        shards = [self.partitioner.ranges[index]
                  for index in self.scheduler.order(shard_count, self._next_shard)]
        batch_per_shard = max(1, self.nonce_batch_size // shard_count)
        budget = self.nonce_batch_size

        for shard in shards:
            if budget <= 0:
                break
            span = shard.end_nonce - shard.start_nonce
            cursor = self._nonce_cursors.get(shard.shard_id, shard.start_nonce)
            cursor = shard.start_nonce + ((cursor - shard.start_nonce) % span)
            mask = int(pool_mask_hex, 16)
            version_bits = (shard.shard_id << 13) & mask
            version_bits_hex = f"{version_bits:08x}"
            rolled_version, _ = apply_version_rolling(
                base_version, mask, version_bits
            )
            remaining = span - self._scanned_per_shard.get(shard.shard_id, 0)
            count = min(batch_per_shard, remaining, shard.end_nonce - cursor, budget)
            if count <= 0:
                continue

            header_prefix = build_header80(
                rolled_version, prevhash_bytes, merkle_root_bytes, ntime, nbits, 0
            )[:76]
            result = self.search_engine.solve_header_range(header_prefix, share_target, cursor, count)
            self.last_search_result = result
            self.hashes_computed += result.iterations_evaluated
            budget -= result.iterations_evaluated
            self._nonce_cursors[shard.shard_id] = cursor + result.iterations_evaluated
            self._scanned_per_shard[shard.shard_id] = (
                self._scanned_per_shard.get(shard.shard_id, 0) + result.iterations_evaluated
            )
            self._next_shard = (shard.shard_id + 1) % shard_count
            if result.found:
                return result.nonce, version_bits_hex, int.from_bytes(result.header_hash, "little")

        if all(
            self._scanned_per_shard.get(shard.shard_id, 0)
            >= shard.end_nonce - shard.start_nonce
            for shard in shards
        ):
            self._nonce_space_exhausted = True
        return None

    async def _mining_loop(self):
        """Continuously hash assigned nonce subranges and verify target hits."""
        logger.info("Starting bounded SHA-256d nonce search across disjoint shards.")
        while self.running:
            if not self.gateway.jobs:
                await asyncio.sleep(0.2)
                continue

            latest_job_id = self.gateway.job_history[-1] if self.gateway.job_history else None
            if not latest_job_id or latest_job_id not in self.gateway.jobs:
                await asyncio.sleep(0.2)
                continue

            job = self.gateway.jobs[latest_job_id]
            context = (
                job["job_id"],
                job.get("generation", self.gateway.connection_generation),
                job.get("revision", 0),
                self.gateway.work_revision,
                self.gateway.pool_mask_hex,
                self.gateway.extranonce1_hex,
                self.gateway.extranonce2_size,
            )
            if context != self._nonce_context:
                self._nonce_context = context
                self.en2_counter = -1
                self._nonce_extranonce_exhausted = False
                self._advance_extranonce()
            elif self._nonce_space_exhausted:
                self._advance_extranonce()
            en2_hex = self._current_extranonce2

            if self._nonce_extranonce_exhausted:
                await asyncio.sleep(0.2)
                continue

            extranonce1 = self.gateway.extranonce1_hex
            extranonce2_size = self.gateway.extranonce2_size
            pool_mask_hex = self.gateway.pool_mask_hex
            work_revision = self.gateway.work_revision
            generation = self.gateway.connection_generation
            try:
                merkle_root_bytes = compute_merkle_root_stratum(
                    job["coinb1_hex"],
                    extranonce1,
                    en2_hex,
                    job["coinb2_hex"],
                    job["merkle_branches"]
                )

                diff_val = job.get("difficulty", self.gateway.current_difficulty)
                diff_frac = (
                    diff_val if isinstance(diff_val, Fraction) else Fraction(str(diff_val))
                )
                share_target = compute_share_target_exact(diff_frac)
                batch = asyncio.create_task(asyncio.to_thread(
                    self._search_nonce_batch,
                    job,
                    merkle_root_bytes,
                    pool_mask_hex,
                    share_target,
                ))
                try:
                    candidate = await asyncio.shield(batch)
                except asyncio.CancelledError:
                    # Finish this bounded worker before closing or reusing the
                    # session; to_thread cancellation cannot stop its thread.
                    await batch
                    raise
                if candidate is None:
                    await asyncio.sleep(0)
                    continue
                solution_nonce, version_bits_submit, candidate_hash = candidate

                # A pool push may have invalidated this batch while hashing.
                if (not self.running or self.gateway.jobs.get(job["job_id"]) is not job
                        or generation != self.gateway.connection_generation
                        or work_revision != self.gateway.work_revision):
                    continue
                logger.info(
                    "[GEOMETRIC GALOIS] Target hit for job %s; Zeckendorf=%s amplitude=%d harmonic=%s vertex=%d",
                    job["job_id"], self.last_search_result.zeckendorf_indices,
                    self.last_search_result.galois_amplitude, self.last_search_result.harmonic_consensus,
                    self.last_search_result.polychoron_vertex_idx,
                )

                is_block_candidate = candidate_hash <= decode_nbits_target(job["nbits_hex"])
                queued = ShareCandidate(
                    job_id=job["job_id"],
                    extranonce2_hex=en2_hex,
                    ntime_hex=job["ntime_hex"],
                    nonce_int=solution_nonce,
                    version_bits_hex=version_bits_submit,
                    hash_int=candidate_hash,
                )
                if not self.priority_queue.push(queued, is_block_hit=is_block_candidate):
                    logger.info("[RATE LIMITER] Normal share queue full; candidate discarded.")
                    continue
                queued_candidate, queued_block = self.priority_queue.pop()
                if queued_candidate is None:
                    continue
                solution_nonce = queued_candidate.nonce_int
                version_bits_submit = queued_candidate.version_bits_hex

                is_valid, drop_reason, block_hash_be, hash_int, target_int, is_block = (
                    self.gatekeeper.verify_candidate(
                        job_data=job,
                        extranonce1_hex=extranonce1,
                        extranonce2_hex=en2_hex,
                        extranonce2_size=extranonce2_size,
                        ntime_hex=job["ntime_hex"],
                        nonce_int=solution_nonce,
                        version_bits_hex=version_bits_submit,
                        pool_mask_hex=pool_mask_hex,
                        current_difficulty=diff_frac,
                        dedup_ledger=self.gateway.dedup_ledger,
                        active_job_ids=self.gateway.jobs,
                    )
                )
                if not is_valid:
                    logger.info(
                        "[LOCAL GATEKEEPER] Candidate dropped: %s",
                        drop_reason.value if drop_reason else "UNKNOWN",
                    )
                    await asyncio.sleep(0)
                    continue

                if is_block != queued_block or hash_int != queued_candidate.hash_int:
                    logger.error("Gatekeeper result mismatch; refusing candidate submission.")
                    continue
                self.shares_found += 1

                if is_block or self.token_bucket.acquire():
                    logger.info("[LIVE WIRE] Submitting validated share for job %s", job["job_id"])
                    submit_params = build_mining_submit_params(
                        self.user,
                        job["job_id"],
                        en2_hex,
                        job["ntime_hex"],
                        f"{solution_nonce:08x}",
                        version_bits_submit if int(pool_mask_hex, 16) else None,
                    )
                    if len(self._pending_submits) >= 1024:
                        raise ConnectionError("Too many unacknowledged submissions")
                    # Register before drain yields, so a fast acknowledgement cannot race us.
                    rpc_id = self.gateway.msg_id + 1
                    self._pending_submits[rpc_id] = time.perf_counter_ns()
                    self._submission_changed.set()
                    await self.gateway.write_rpc("mining.submit", submit_params)
                    self.shares_submitted += 1
                    self.gatekeeper.record_submitted_share()
                else:
                    logger.info("[RATE LIMITER] Share acquisition throttled locally.")
            except Exception:
                logger.exception("Error in SHA-256d mining loop")
                raise

            await asyncio.sleep(0)


async def async_main():
    active_pool, host, port, user, password = load_env_config()
    logger.info("========================================================================")
    logger.info("       HYBA INTERNAL GEOMETRIC/GALOIS MINER   ")
    logger.info("========================================================================")
    logger.info(f"[CONFIG] Active Pool Target: {active_pool}")
    logger.info(f"[CONFIG] Socket Endpoint:    {host}:{port}")
    logger.info(f"[CONFIG] Worker Identity:    {user}")

    engine = ChronusRealMiningEngine(host, port, user, password)
    max_sec_env = os.getenv("MINING_MAX_SECONDS")
    max_seconds = int(max_sec_env) if max_sec_env else None
    await engine.run(max_seconds=max_seconds)


def cli_main():
    """CLI synchronous wrapper for console script entrypoint."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Miner terminated by user.")
        sys.exit(0)


if __name__ == "__main__":
    cli_main()

