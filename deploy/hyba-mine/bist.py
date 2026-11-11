"""HYBA Mine built-in self-test (BIST): no BIST pass, no stratum connect.

Known-answer checks of the miner's own hash path against public Bitcoin data
(the genesis block and block 1). Every check calls the functions the miner uses
for live work: chronus.stratum.endian_engine (header, prevhash word order,
coinbase and merkle root), chronus.stratum.gatekeeper (share and network
targets, the pre-submission verification) and chronus.stratum.bip310 (version
rolling). It prints one JSON report and exits 0 only if every check passes.
It makes no network connection.
"""

import json
import sys
from fractions import Fraction

from chronus.stratum.bip310 import apply_version_rolling
from chronus.stratum.endian_engine import (
    build_header80,
    compute_merkle_root_stratum,
    sha256d,
    swap_prevhash_words,
)
from chronus.stratum.gatekeeper import (
    TRUEDIFF1_TARGET,
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
)

# Block 0: the coinbase transaction, its merkle root and the header fields.
GENESIS_COINBASE = (
    "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff"
    "4d04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72"
    "206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73ffffffff"
    "0100f2052a01000000434104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f"
    "61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac00000000"
)
GENESIS_MERKLE = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_TIME = 1231006505
NBITS_DIFF1 = 0x1D00FFFF
GENESIS_NONCE = 2083236893

# Block 1, with its previous-block hash in Stratum V1 word order.
BLOCK1_MERKLE = "0e3e2357e806b6cdb1f70b54c3a3a17b6714ee1f0e68bebb44a74b1efd512098"
BLOCK1_HASH = "00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048"
BLOCK1_PREVHASH_STRATUM = "0a8ce26f72b3f1b646a2a6c14ff763ae65831e939c085ae10019d66800000000"
BLOCK1_TIME = 1231469665
BLOCK1_NONCE = 2573394689


def run() -> dict:
    checks = []

    def check(name: str, passed: bool) -> None:
        checks.append({"check": name, "passed": bool(passed)})

    coinbase = bytes.fromhex(GENESIS_COINBASE)
    # A pool sends the coinbase as coinb1 | extranonce1 | extranonce2 | coinb2; the
    # miner joins the four parts, so any interior split must give the same root.
    cut = 42
    coinb1 = coinbase[:cut].hex()
    extranonce1 = coinbase[cut:cut + 4].hex()
    extranonce2 = coinbase[cut + 4:cut + 8].hex()
    coinb2 = coinbase[cut + 8:].hex()
    merkle = compute_merkle_root_stratum(coinb1, extranonce1, extranonce2, coinb2, [])
    check("merkle_root_from_stratum_coinbase", merkle[::-1].hex() == GENESIS_MERKLE)

    header0 = build_header80(1, swap_prevhash_words("00" * 32), merkle, GENESIS_TIME, NBITS_DIFF1, GENESIS_NONCE)
    digest0 = sha256d(header0)
    check("sha256d_block0_header", len(header0) == 80 and digest0[::-1].hex() == GENESIS_HASH)

    prev1 = swap_prevhash_words(BLOCK1_PREVHASH_STRATUM)
    check("stratum_prevhash_word_order", prev1 == bytes.fromhex(GENESIS_HASH)[::-1])
    header1 = build_header80(1, prev1, bytes.fromhex(BLOCK1_MERKLE)[::-1], BLOCK1_TIME, NBITS_DIFF1, BLOCK1_NONCE)
    digest1 = sha256d(header1)
    check("sha256d_block1_header", digest1[::-1].hex() == BLOCK1_HASH)

    diff1 = 0xFFFF << 208
    check(
        "share_and_network_targets",
        decode_nbits_target(NBITS_DIFF1) == diff1
        and TRUEDIFF1_TARGET == diff1
        and compute_share_target_exact(Fraction(1)) == diff1
        and compute_share_target_exact(Fraction(2)) == diff1 // 2,
    )
    check(
        "block_hashes_meet_target",
        int.from_bytes(digest0, "little") <= diff1 and int.from_bytes(digest1, "little") <= diff1,
    )

    rolled, bits = apply_version_rolling("20000000", "1fffe000", 0xFFFFFFFF)
    check(
        "version_rolling_stays_inside_mask",
        apply_version_rolling("00000001", "00000000", 0xFFFFFFFF) == (1, "00000000")
        and rolled == 0x3FFFE000
        and bits == "1fffe000",
    )

    # The exact pre-submission path the miner runs before every mining.submit,
    # on block 0 presented as a Stratum job.
    job = {
        "job_id": "bist",
        "prevhash_hex": "00" * 32,
        "coinb1_hex": coinb1,
        "coinb2_hex": coinb2,
        "merkle_branches": [],
        "version_hex": "00000001",
        "nbits_hex": f"{NBITS_DIFF1:08x}",
        "ntime_hex": f"{GENESIS_TIME:08x}",
    }
    gatekeeper = LocalPreSubmitGatekeeper()
    accepted = gatekeeper.verify_candidate(
        job, extranonce1, extranonce2, 4, job["ntime_hex"], GENESIS_NONCE, "00000000", "00000000", Fraction(1)
    )
    check(
        "gatekeeper_accepts_block0",
        accepted[0] is True and accepted[1] is None and accepted[2] == GENESIS_HASH and accepted[5] is True,
    )
    refused = gatekeeper.verify_candidate(
        job, extranonce1, extranonce2, 4, job["ntime_hex"], GENESIS_NONCE + 1, "00000000", "00000000", Fraction(1)
    )
    check(
        "gatekeeper_refuses_wrong_nonce",
        refused[0] is False and refused[1] is not None and refused[1].value == "ABOVE_TARGET",
    )

    passed = all(item["passed"] for item in checks)
    return {"bist": "PASS" if passed else "FAIL", "checks": checks}


def main() -> int:
    report = run()
    print(json.dumps(report, indent=1))
    return 0 if report["bist"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
