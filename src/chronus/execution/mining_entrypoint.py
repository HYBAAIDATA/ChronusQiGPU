#!/usr/bin/env python3
"""Authored geometric/Galois mining pipeline with a bounded Stratum V1 session."""

from __future__ import annotations

import asyncio
import hashlib
from fractions import Fraction
import json
import logging
import os
import sys
import time
from typing import Optional, Tuple

from chronus.execution.geometric_galois_miner import GeometricGaloisMiner
from chronus.execution.hashrate_cap import process_cap
from chronus.execution.mining_scheduler import TuringMiningScheduler
from chronus.stratum.endian_engine import swap_prevhash_words, compute_merkle_root_stratum, build_header80
from chronus.stratum.bip310 import (
    apply_version_rolling,
    build_mining_submit_params,
    format_extranonce2,
)
from chronus.stratum.endpoint import PoolEndpoint, parse_endpoint
from chronus.stratum.sharding import ShareCandidate, WorkPartitioner
from chronus.stratum.gateway import StratumGateway
from chronus.stratum.gatekeeper import (
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
)
from chronus.stratum.rate_limiter import IntegerNanosecondTokenBucket, PriorityShareQueue

from chronus.service.metrics import SHARES_SUBMITTED, SHARES_ACCEPTED, SHARES_REJECTED, SHARE_LATENCY, HASHRATE_BATCHES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChronusMiningEntrypoint")

DEFAULT_POOL_PORT = 3333
_KNOWN_POOLS = {"BRAIINS", "VIABTC"}


def _load_dotenv() -> None:
    """Populate os.environ from the nearest .env. Real env vars win."""
    for base in (os.getcwd(), os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))):
        env_file = os.path.join(base, ".env")
        if not os.path.exists(env_file):
            continue
        with open(env_file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))
        return


def _endpoint_from_specs() -> Optional[Tuple[str, PoolEndpoint, str, str]]:
    """Highest-priority entry from PYTHIA_POOL_SPECS, if that is configured."""
    raw = os.getenv("PYTHIA_POOL_SPECS", "").strip().strip("'").strip('"')
    if not raw:
        return None
    try:
        specs = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"PYTHIA_POOL_SPECS is not valid JSON: {exc}") from exc
    if not isinstance(specs, list) or not specs:
        raise ValueError("PYTHIA_POOL_SPECS must be a non-empty JSON array")

    def priority(spec: dict) -> int:
        try:
            return int(spec.get("priority", 999))
        except (TypeError, ValueError):
            return 999

    spec = sorted((s for s in specs if isinstance(s, dict)), key=priority)[0]
    try:
        endpoint = parse_endpoint(str(spec["endpoint"]), DEFAULT_POOL_PORT)
        user = str(spec["user"])
    except KeyError as exc:
        raise ValueError(f"pool spec missing key {exc}") from exc
    password = str(spec.get("pass") or spec.get("password") or "x")
    return "SPECS", endpoint, user, password


def load_env_config() -> Tuple[str, PoolEndpoint, str, str]:
    """Return (pool_label, endpoint, user, password). Raises on incomplete config."""
    _load_dotenv()

    from_specs = _endpoint_from_specs()
    if from_specs is not None:
        return from_specs

    active_pool = os.getenv("MINING_ACTIVE_POOL", "BRAIINS").strip().upper() or "BRAIINS"
    if active_pool not in _KNOWN_POOLS:
        raise ValueError(f"MINING_ACTIVE_POOL must be one of {sorted(_KNOWN_POOLS)}")

    host_raw = os.getenv(f"MINING_{active_pool}_HOST", "").strip()
    port_raw = os.getenv(f"MINING_{active_pool}_PORT", "").strip()
    user = os.getenv(f"MINING_{active_pool}_USER", "").strip()
    password = (
        os.getenv(f"MINING_{active_pool}_PASSWORD")
        or os.getenv(f"MINING_{active_pool}_PASS")
        or "x"
    )
    if not host_raw or not user:
        raise ValueError(
            f"Set PYTHIA_POOL_SPECS, or MINING_{active_pool}_HOST and "
            f"MINING_{active_pool}_USER, before starting"
        )

    scheme, separator, bare_host = host_raw.partition("://")
    if not separator:
        scheme, bare_host = "stratum+tcp", host_raw
        # Braiins and ViaBTC document "x" and "123" as ignored placeholders.
        # Match the password that is sent. Surrounding whitespace is a different value.
        if password not in {"x", "123"}:
            logger.warning(
                "MINING_%s_HOST has no scheme, so this password is sent on cleartext "
                "stratum+tcp. Use a stratum+ssl:// host when the password is a secret.",
                active_pool,
            )
    # Only bolt the port on when the host does not already carry one.
    if port_raw and ":" not in bare_host.rsplit("]", 1)[-1]:
        bare_host = f"{bare_host}:{port_raw}"
    endpoint = parse_endpoint(f"{scheme}://{bare_host}", DEFAULT_POOL_PORT)
    return active_pool, endpoint, user, password


class ChronusRealMiningEngine:
    """Geometric/Galois mining runner with verified submissions and bounded work."""

    def __init__(
        self,
        endpoint: PoolEndpoint | str,
        user: str | int,
        password: str,
        legacy_password: str | None = None,
    ):
        """Accept a PoolEndpoint, or the legacy (host, port, user, password) form."""
        if isinstance(endpoint, PoolEndpoint):
            if legacy_password is not None:
                raise TypeError("legacy_password is only valid with a host string")
            pool_endpoint = endpoint
            worker_name = str(user)
            pool_password = password
        else:
            if legacy_password is None:
                raise TypeError("legacy construction requires host, port, user, and password")
            pool_endpoint = PoolEndpoint(str(endpoint), int(user), False)
            worker_name = password
            pool_password = legacy_password

        self.endpoint = pool_endpoint
        self.user = worker_name
        self.password = pool_password
        self.gateway = StratumGateway(
            host=pool_endpoint.host,
            port=pool_endpoint.port,
            worker_name=worker_name,
            password=pool_password,
            shard_count=32,
            tls=pool_endpoint.tls,
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
        self._hash_throttled = False

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

        # The self-test contains asyncio.run checks; execute it off the caller's loop.
        selftest_report = await asyncio.to_thread(run_selftest)
        if selftest_report.get("bist") != "PASS":
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
                if msg.get("error"):
                    logger.warning("[POOL] Uncorrelated error response: %s", msg["error"])
                continue
            if msg.get("result") is not True and msg.get("result") is not False and not msg.get("error"):
                continue
            submitted_ns = self._pending_submits.pop(rpc_id)
            SHARE_LATENCY.observe((time.perf_counter_ns() - submitted_ns) / 1_000_000_000)
            self._submission_changed.set()
            if msg.get("result") is True and not msg.get("error"):
                self.shares_accepted += 1
                SHARES_ACCEPTED.inc()
                logger.info("[POOL SUCCESS] Share ACCEPTED (Total accepted: %d)", self.shares_accepted)
            else:
                self.shares_rejected += 1
                SHARES_REJECTED.inc()
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
        self._hash_throttled = False
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
            if result.iterations_evaluated == 0:
                self._hash_throttled = True
                break
            HASHRATE_BATCHES.inc()
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
                    if self._hash_throttled:
                        delay = process_cap().wait_ns() / 1_000_000_000
                        await asyncio.sleep(delay if delay > 0 else 0.001)
                    else:
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
                    # Reserve and register before the request can reach the wire.
                    rpc_id = self.gateway.reserve_id()
                    self._pending_submits[rpc_id] = time.perf_counter_ns()
                    self._submission_changed.set()
                    await self.gateway.write_rpc("mining.submit", submit_params, rpc_id)
                    self.shares_submitted += 1
                    SHARES_SUBMITTED.inc()
                    self.gatekeeper.record_submitted_share()
                else:
                    logger.info("[RATE LIMITER] Share acquisition throttled locally.")
            except Exception:
                logger.exception("Error in SHA-256d mining loop")
                raise

            await asyncio.sleep(0)


async def async_main():
    active_pool, endpoint, user, password = load_env_config()
    logger.info(f"[CONFIG] Active Pool Target: {active_pool}")
    logger.info(f"[CONFIG] Socket Endpoint:    {endpoint}")
    logger.info(f"[CONFIG] Worker Identity:    {user}")
    engine = ChronusRealMiningEngine(endpoint, user, password)  # CHANGED
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

