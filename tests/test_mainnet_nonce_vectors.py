"""Regression tests for the chain-verified mainnet nonce header vector.

The vector at ``tests/vectors/mainnet_nonces_975565_976064.json`` holds, for
each of the 500 consecutive mainnet heights 975565-976064, the full 76-byte
header prefix and winning nonce. These tests prove, offline, that every row:

* reproduces its recorded chain hash
  (``sha256d(prefix || nonce_le) == reverse(chain_hash)``), and
* meets its own difficulty target decoded from the embedded ``nbits``,

and that the provenance record (full verification, owner-paste corrections,
retarget boundary) stays consistent. The positional nonce array is derived
from the per-block rows at load time; it is not stored in the vector file.

No network access is required or attempted.
"""
import hashlib
import json
import struct
import unittest
from pathlib import Path

VECTOR_PATH = (
    Path(__file__).resolve().parent / "vectors" / "mainnet_nonces_975565_976064.json"
)

START_HEIGHT = 976064
END_HEIGHT = 975565
ROW_COUNT = 500
REJOINED_INDEX = 497  # value rejoined from the mangled owner paste tail
REJOINED_HEIGHT = START_HEIGHT - REJOINED_INDEX  # 975567
REJOINED_NONCE = 1534279252
RETARGET_HEIGHT = 975744  # 484 * 2016
PASTE_CORRECTIONS = [
    {"index": 154, "height": 975910, "paste_value": 634315162, "chain_value": 1844472833},
    {"index": 155, "height": 975909, "paste_value": 3222296834, "chain_value": 634315162},
    {"index": 156, "height": 975908, "paste_value": 1358818957, "chain_value": 3222296834},
    {"index": 157, "height": 975907, "paste_value": 1848505089, "chain_value": 1358818957},
    {"index": 158, "height": 975906, "paste_value": 1844472833, "chain_value": 1848505089},
]


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def target_from_bits(nbits: int) -> int:
    exponent = nbits >> 24
    mantissa = nbits & 0xFFFFFF
    return mantissa * (1 << (8 * (exponent - 3)))


class MainnetNonceVectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vector = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
        cls.blocks = cls.vector["blocks"]
        # Single source of truth: the positional nonce array is derived from
        # the per-block rows at load time and is not stored in the vector.
        cls.nonces = [row["nonce"] for row in cls.blocks]

    def test_schema_counts_and_ranges(self) -> None:
        self.assertEqual(len(self.nonces), ROW_COUNT)
        self.assertEqual(len(self.blocks), ROW_COUNT)
        self.assertEqual(len(set(self.nonces)), ROW_COUNT)
        self.assertTrue(all(0 <= nonce < 2**32 for nonce in self.nonces))
        self.assertEqual(self.vector["start_height"], START_HEIGHT)
        self.assertEqual(self.vector["end_height"], END_HEIGHT)

    def test_blocks_descending_and_positional_match(self) -> None:
        for index, row in enumerate(self.blocks):
            self.assertEqual(row["height"], START_HEIGHT - index)
            self.assertEqual(row["nonce"], self.nonces[index])
        heights = [row["height"] for row in self.blocks]
        self.assertEqual(heights, sorted(heights, reverse=True))
        self.assertEqual(heights[0], START_HEIGHT)
        self.assertEqual(heights[-1], END_HEIGHT)

    def test_ntime_median_time_past_compliance(self) -> None:
        """The scramble-catcher for the window. Strict pairwise ntime
        monotonicity does NOT hold on real mainnet - miners may emit a header
        whose ntime is slightly older than the immediately prior block's
        (17 such inversions occur inside this 500-block window). The actual
        consensus invariant is BIP113: ntime >= the median of the prior 11
        blocks. A scrambled window breaks that with high probability; honest
        data passes by protocol rule, not by luck."""
        times = [
            struct.unpack("<I", bytes.fromhex(row["prefix_hex"])[68:72])[0]
            for row in self.blocks
        ]
        for index in range(0, ROW_COUNT - 11):
            median_past = sorted(times[index + 1 : index + 12])[5]
            self.assertGreaterEqual(
                times[index],
                median_past,
                f"height {START_HEIGHT - index} violates median-time-past",
            )
        # Sanity: the window spans days, not seconds.
        self.assertGreater(times[0] - times[-1], 86_400 * 2)

    def test_nbits_constant_within_retarget_periods(self) -> None:
        """nbits is constant inside each 2016-block period. The single
        boundary inside the window is height 975744 = 484 * 2016 (index 320):
        indices 0-320 carry the post-retarget value, 321-499 the previous."""
        def nbits(row: dict) -> int:
            return struct.unpack("<I", bytes.fromhex(row["prefix_hex"])[72:76])[0]

        self.assertEqual(self.blocks[320]["height"], 975744)
        self.assertEqual(self.blocks[321]["height"], 975743)
        self.assertEqual({nbits(row) for row in self.blocks[0:321]}, {386012787})
        self.assertEqual({nbits(row) for row in self.blocks[321:500]}, {386000300})

    def test_every_row_reproduces_chain_hash_and_meets_target(self) -> None:
        for row in self.blocks:
            prefix = bytes.fromhex(row["prefix_hex"])
            self.assertEqual(len(prefix), 76, f"height {row['height']} prefix length")
            nbits = struct.unpack("<I", prefix[72:76])[0]
            header = prefix + struct.pack("<I", row["nonce"])
            digest = sha256d(header)
            self.assertEqual(
                digest,
                bytes.fromhex(row["chain_hash"])[::-1],
                f"height {row['height']} does not reproduce its chain hash",
            )
            self.assertLessEqual(
                int.from_bytes(digest, "little"),
                target_from_bits(nbits),
                f"height {row['height']} does not meet its own target",
            )

    def test_provenance_records_full_verification_and_corrections(self) -> None:
        provenance = self.vector["provenance"]
        self.assertIn("VERIFIED 500/500", provenance["status"])
        self.assertEqual(provenance["paste_corrections"], PASTE_CORRECTIONS)

    def test_rejoined_row_matches_chain(self) -> None:
        row = self.blocks[REJOINED_INDEX]
        self.assertEqual(row["height"], REJOINED_HEIGHT)
        self.assertEqual(row["nonce"], REJOINED_NONCE)

    def test_retarget_boundary_arithmetic(self) -> None:
        check = self.vector["provenance"]["retarget_check"]
        self.assertEqual(RETARGET_HEIGHT, 484 * 2016)
        self.assertEqual(check["expected_boundary_height"], RETARGET_HEIGHT)
        self.assertEqual(check["nbits_before"], 386000300)
        self.assertEqual(check["nbits_after"], 386012787)
        self.assertGreater(
            target_from_bits(check["nbits_after"]),
            target_from_bits(check["nbits_before"]),
        )


if __name__ == "__main__":
    unittest.main()
