"""
Chronus Zero-Ban Pre-Submission Local Gatekeeper Engine.

Safety Contract:
----------------
Evaluates every candidate share locally BEFORE wire transmission.
Invalid or non-target nonces are dropped internally. Pool rejection and ban
policies remain outside this local verifier's control.

Drop Reasons Enum:
------------------
- BAD_LEN:      Header length != 80 bytes.
- BAD_HEX:      Parameter failed hex decoding.
- STALE_JOB:    Job ID not present in active job table or generation mismatch.
- DUP:          Duplicate share detected in DedupLedger.
- ABOVE_TARGET: Hash integer exceeds exact rational share target.
- EN2_WIDTH:    ExtraNonce2 hex length != expected size * 2.
- VERSION_MASK: Version bits violate pool's negotiated ASICBoost mask.
"""

import enum
import time
from fractions import Fraction
from typing import Dict, Any, Tuple, Optional

from chronus.stratum.bip310 import apply_version_rolling
from chronus.stratum.endian_engine import swap_prevhash_words, compute_merkle_root_stratum, build_header80, sha256d

# Mainnet Difficulty 1 Target (Truediff1 constant)
TRUEDIFF1_TARGET: int = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


class DropReason(enum.Enum):
    BAD_LEN = "BAD_LEN"
    BAD_HEX = "BAD_HEX"
    STALE_JOB = "STALE_JOB"
    DUP = "DUP"
    ABOVE_TARGET = "ABOVE_TARGET"
    EN2_WIDTH = "EN2_WIDTH"
    VERSION_MASK = "VERSION_MASK"


def decode_nbits_target(nbits_hex_or_int: str | int) -> int:
    """
    Decodes Bitcoin nBits compact target representation to 256-bit integer target.
    Formula: target = mantissa * 256^(exponent - 3)
    """
    if isinstance(nbits_hex_or_int, str):
        nbits = int(nbits_hex_or_int, 16)
    else:
        nbits = nbits_hex_or_int

    if type(nbits) is not int or not 0 <= nbits <= 0xffffffff:
        raise ValueError("nBits must be an unsigned 32-bit integer")
    if nbits & 0x00800000:
        raise ValueError("Negative compact target")
    exponent = nbits >> 24
    mantissa = nbits & 0x007FFFFF

    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))

    if not 0 < target < (1 << 256):
        raise ValueError("Compact target must be positive and fit uint256")
    return target


def compute_share_target_exact(difficulty: Fraction | int | str) -> int:
    """
    Computes exact share target integer using arbitrary-precision Fraction division.
    0 floating-point operations. Floor integer division.
    """
    if isinstance(difficulty, float):
        raise TypeError(f"Floating-point difficulty disallowed in exact gatekeeper: got {difficulty}")
    frac_diff = Fraction(difficulty) if isinstance(difficulty, (int, str, Fraction)) else Fraction(str(difficulty))
    if frac_diff <= 0:
        raise ValueError(f"Share difficulty must be positive, got {difficulty}")
    return min((1 << 256) - 1, (TRUEDIFF1_TARGET * frac_diff.denominator) // frac_diff.numerator)


class LocalPreSubmitGatekeeper:
    """
    Evaluates candidate shares locally against strict protocol invariants and targets.
    Exposes timing metrics (measured in nanoseconds / microseconds) and tracks
    both local rejection reasons and network-side stale share rate.
    """
    def __init__(self):
        self.reject_counts: Dict[DropReason, int] = {reason: 0 for reason in DropReason}
        self.verified_shares_count: int = 0
        self.submitted_shares_count: int = 0
        self.stale_shares_count: int = 0
        self.blocks_found_count: int = 0
        self.last_verification_ns: int = 0

    @property
    def stale_share_rate(self) -> float:
        """
        Exposes the network stale share rate as a percentage: (stale / submitted) * 100.
        Reframes the '0.00% invalid share rejection' into a verifiable operational metric.
        """
        if self.submitted_shares_count == 0:
            return 0.0
        return (self.stale_shares_count / self.submitted_shares_count) * 100.0

    def record_submitted_share(self) -> None:
        self.submitted_shares_count += 1

    def record_stale_share(self) -> None:
        self.stale_shares_count += 1
        self.reject_counts[DropReason.STALE_JOB] += 1

    def record_duplicate_share(self) -> None:
        self.reject_counts[DropReason.DUP] += 1

    def verify_candidate(
        self,
        job_data: Dict[str, Any],
        extranonce1_hex: str,
        extranonce2_hex: str,
        extranonce2_size: int,
        ntime_hex: str,
        nonce_int: int,
        version_bits_hex: str,
        pool_mask_hex: str,
        current_difficulty: Fraction,
        dedup_ledger: Optional[Any] = None,
        active_job_ids: Optional[Any] = None
    ) -> Tuple[bool, Optional[DropReason], str, int, int, bool]:
        """
        Executes local 2-stage verification:
        1. Structural checks
        2. Exact target assertion (Hash <= ShareTarget)

        Returns:
            (is_valid, drop_reason, block_hash_be_hex, hash_int, target_int, is_network_block)
        """
        t0 = time.perf_counter_ns()

        # Check Active Job / Stale Job
        if active_job_ids is not None:
            job_id = job_data.get("job_id")
            if job_id not in active_job_ids:
                self.reject_counts[DropReason.STALE_JOB] += 1
                self.last_verification_ns = time.perf_counter_ns() - t0
                return False, DropReason.STALE_JOB, "", 0, 0, False

        # Check Duplicate in DedupLedger
        if dedup_ledger is not None:
            job_id = job_data.get("job_id", "")
            if dedup_ledger.is_duplicate(
                job_id,
                version_bits_hex,
                extranonce2_hex,
                ntime_hex,
                nonce_int
            ):
                self.reject_counts[DropReason.DUP] += 1
                self.last_verification_ns = time.perf_counter_ns() - t0
                return False, DropReason.DUP, "", 0, 0, False

        # Check ExtraNonce2 width
        if len(extranonce2_hex) != extranonce2_size * 2:
            self.reject_counts[DropReason.EN2_WIDTH] += 1
            self.last_verification_ns = time.perf_counter_ns() - t0
            return False, DropReason.EN2_WIDTH, "", 0, 0, False

        # Validate hex parameters
        try:
            prevhash_bytes = swap_prevhash_words(job_data["prevhash_hex"])
            merkle_root_bytes = compute_merkle_root_stratum(
                job_data["coinb1_hex"],
                extranonce1_hex,
                extranonce2_hex,
                job_data["coinb2_hex"],
                job_data["merkle_branches"]
            )
        except Exception:
            self.reject_counts[DropReason.BAD_HEX] += 1
            self.last_verification_ns = time.perf_counter_ns() - t0
            return False, DropReason.BAD_HEX, "", 0, 0, False

        # Version-rolling mask constraint check
        try:
            rolled_bits_int = int(version_bits_hex, 16)
            mask_int = int(pool_mask_hex, 16)
            if (rolled_bits_int & ~mask_int) != 0:
                self.reject_counts[DropReason.VERSION_MASK] += 1
                self.last_verification_ns = time.perf_counter_ns() - t0
                return False, DropReason.VERSION_MASK, "", 0, 0, False

            final_version_int, _ = apply_version_rolling(job_data["version_hex"], pool_mask_hex, rolled_bits_int)
        except Exception:
            self.reject_counts[DropReason.BAD_HEX] += 1
            self.last_verification_ns = time.perf_counter_ns() - t0
            return False, DropReason.BAD_HEX, "", 0, 0, False

        # Construct 80-byte header
        try:
            ntime_int = int(ntime_hex, 16)
            nbits_int = int(job_data["nbits_hex"], 16)
            header_80b = build_header80(
                final_version_int,
                prevhash_bytes,
                merkle_root_bytes,
                ntime_int,
                nbits_int,
                nonce_int
            )
        except Exception:
            self.reject_counts[DropReason.BAD_LEN] += 1
            self.last_verification_ns = time.perf_counter_ns() - t0
            return False, DropReason.BAD_LEN, "", 0, 0, False

        # Compute SHA-256d hash and compare against targets
        raw_digest = sha256d(header_80b)
        hash_int = int.from_bytes(raw_digest, byteorder="little")
        block_hash_be_hex = raw_digest[::-1].hex()

        # Compute share target & block target
        share_target_int = compute_share_target_exact(current_difficulty)
        network_block_target_int = decode_nbits_target(nbits_int)

        is_share_valid = (hash_int <= share_target_int)
        is_network_block = (hash_int <= network_block_target_int)

        self.last_verification_ns = time.perf_counter_ns() - t0

        if not is_share_valid:
            self.reject_counts[DropReason.ABOVE_TARGET] += 1
            return False, DropReason.ABOVE_TARGET, block_hash_be_hex, hash_int, share_target_int, False

        if dedup_ledger is not None:
            dedup_ledger.record(
                job_data.get("job_id", ""),
                version_bits_hex,
                extranonce2_hex,
                ntime_hex,
                nonce_int
            )

        self.verified_shares_count += 1
        if is_network_block:
            self.blocks_found_count += 1

        return True, None, block_hash_be_hex, hash_int, share_target_int, is_network_block
