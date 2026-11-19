"""Behavioral tests for actual SHA-256d mining candidate selection."""

import hashlib
from fractions import Fraction

from chronus.execution.mining_entrypoint import ChronusRealMiningEngine
from chronus.stratum.bip310 import format_extranonce2
from chronus.stratum.endian_engine import compute_merkle_root_stratum
from chronus.stratum.gatekeeper import compute_share_target_exact
from chronus.stratum.gateway import StratumGateway
import pytest

pytestmark = pytest.mark.real


def test_search_nonce_batch_returns_target_valid_nonce_and_gatekeeper_accepts():
    engine = ChronusRealMiningEngine("127.0.0.1", 3333, "test.worker", "x")
    engine.nonce_batch_size = 8
    engine.gateway = StratumGateway(
        "127.0.0.1", 3333, "test.worker", "x", shard_count=8
    )
    engine.partitioner = engine.gateway.partitioner
    job = {
        "job_id": "local-job",
        "prevhash_hex": "00" * 32,
        "coinb1_hex": "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff0403759905",
        "coinb2_hex": "00000000",
        "merkle_branches": [],
        "version_hex": "20000000",
        "nbits_hex": "207fffff",
        "ntime_hex": "60000000",
    }
    engine.gateway.jobs[job["job_id"]] = job
    engine.gateway.job_history.append(job["job_id"])
    engine.gateway.extranonce1_hex = "a45b7889"
    engine.gateway.extranonce2_size = 4
    engine.gateway.current_difficulty = Fraction(1, 10**12)

    extranonce2 = format_extranonce2(1, 4)
    merkle = compute_merkle_root_stratum(
        job["coinb1_hex"],
        engine.gateway.extranonce1_hex,
        extranonce2,
        job["coinb2_hex"],
        job["merkle_branches"],
    )
    target = compute_share_target_exact(engine.gateway.current_difficulty)
    candidate = engine._search_nonce_batch(
        job, merkle, engine.gateway.pool_mask_hex, target
    )

    assert candidate is not None
    nonce, version_bits, digest_int = candidate
    shard = next(r for r in engine.partitioner.ranges if r.start_nonce <= nonce < r.end_nonce)
    version = engine.partitioner.compute_version_bits(shard.shard_id)
    rolled_version, _ = __import__(
        "chronus.stratum.bip310", fromlist=["apply_version_rolling"]
    ).apply_version_rolling(int(job["version_hex"], 16), engine.gateway.pool_mask_hex, version)
    header = __import__(
        "chronus.stratum.endian_engine", fromlist=["build_header80"]
    ).build_header80(
        rolled_version,
        __import__("chronus.stratum.endian_engine", fromlist=["swap_prevhash_words"]).swap_prevhash_words(job["prevhash_hex"]),
        merkle,
        int(job["ntime_hex"], 16),
        int(job["nbits_hex"], 16),
        nonce,
    )
    digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
    assert int.from_bytes(digest, "little") <= target

    valid, reason, *_ = engine.gatekeeper.verify_candidate(
        job,
        engine.gateway.extranonce1_hex,
        extranonce2,
        engine.gateway.extranonce2_size,
        job["ntime_hex"],
        nonce,
        version_bits,
        engine.gateway.pool_mask_hex,
        engine.gateway.current_difficulty,
        dedup_ledger=engine.gateway.dedup_ledger,
        active_job_ids=engine.gateway.jobs,
    )
    assert valid, reason
    assert engine.hashes_computed > 0
