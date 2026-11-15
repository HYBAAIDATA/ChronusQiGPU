import json
import struct
import unittest
from pathlib import Path

from chronus.stratum.endian_engine import (
    swap_prevhash_words,
    sha256d,
    merkle_root_from_txids,
    compute_merkle_root_stratum,
    build_header80,
)
from chronus.stratum.bip310 import (
    get_mining_configure_payload,
    parse_and_intersect_version_mask,
    build_mining_submit_params,
)


class TestEndianEngine(unittest.TestCase):
    def test_swap_prevhash_words(self):
        prev_hex = "0000000100000002000000030000000400000005000000060000000700000008"
        swapped = swap_prevhash_words(prev_hex)
        self.assertEqual(len(swapped), 32)
        # First 4-byte word '00000001' (>I) packed as <I is b'\x01\x00\x00\x00'
        self.assertEqual(swapped[:4], b"\x01\x00\x00\x00")
        
        # Exact struct equality: struct.pack("<8I", *struct.unpack(">8I", raw))
        raw = bytes.fromhex(prev_hex)
        expected = struct.pack("<8I", *struct.unpack(">8I", raw))
        self.assertEqual(swapped, expected)

    def test_swap_prevhash_words_validation(self):
        with self.assertRaises(ValueError):
            swap_prevhash_words("00" * 31)
        with self.assertRaises(ValueError):
            swap_prevhash_words(b"\x00" * 33)

    def test_build_header80_length_and_slices(self):
        swapped_prev = b"\x01" * 32
        merkle_raw = b"\x02" * 32
        header = build_header80(0x20000000, swapped_prev, merkle_raw, 0x60000000, 0x1d00ffff, 12345)
        self.assertEqual(len(header), 80)
        self.assertEqual(header[0:4], struct.pack("<I", 0x20000000))
        self.assertEqual(header[4:36], swapped_prev)
        self.assertEqual(header[36:68], merkle_raw)
        self.assertEqual(header[68:72], struct.pack("<I", 0x60000000))
        self.assertEqual(header[72:76], struct.pack("<I", 0x1d00ffff))
        self.assertEqual(header[76:80], struct.pack("<I", 12345))

    def test_build_header80_invalid_slices(self):
        with self.assertRaises(ValueError):
            build_header80(1, b"\x00" * 31, b"\x00" * 32, 1, 1, 1)
        with self.assertRaises(ValueError):
            build_header80(1, b"\x00" * 32, b"\x00" * 31, 1, 1, 1)

    def test_merkle_root_odd_count_duplication(self):
        t1 = sha256d(b"tx1")
        t2 = sha256d(b"tx2")
        t3 = sha256d(b"tx3")
        
        # 1 txid
        root1 = merkle_root_from_txids([t1])
        self.assertEqual(root1, t1)

        # 2 txids
        root2 = merkle_root_from_txids([t1, t2])
        self.assertEqual(root2, sha256d(t1 + t2))

        # 3 txids (odd duplication of t3)
        root3 = merkle_root_from_txids([t1, t2, t3])
        layer1_0 = sha256d(t1 + t2)
        layer1_1 = sha256d(t3 + t3)
        self.assertEqual(root3, sha256d(layer1_0 + layer1_1))

        with self.assertRaises(ValueError):
            merkle_root_from_txids([])

    def test_compute_merkle_root_stratum(self):
        cb1 = "01000000"
        en1 = "a45b7889"
        en2 = "00000001"
        cb2 = "00000000"
        root_no_branch = compute_merkle_root_stratum(cb1, en1, en2, cb2, [])
        coinbase_tx = bytes.fromhex(cb1 + en1 + en2 + cb2)
        self.assertEqual(root_no_branch, sha256d(coinbase_tx))

        b1 = "11" * 32
        root_with_branch = compute_merkle_root_stratum(cb1, en1, en2, cb2, [b1])
        expected_with_branch = sha256d(sha256d(coinbase_tx) + bytes.fromhex(b1))
        self.assertEqual(root_with_branch, expected_with_branch)

    def test_bitcoin_core_regtest_genesis_vector(self):
        vector_path = Path(__file__).parent / "vectors" / "regtest_block0.json"
        self.assertTrue(vector_path.exists(), "regtest_block0.json must exist")
        data = json.loads(vector_path.read_text(encoding="utf-8"))

        fields = data["fields"]
        version = fields["version"]
        prevhash = bytes.fromhex(fields["prevhash"])
        merkle = bytes.fromhex(fields["merkle_root_internal_le"])
        ntime = fields["ntime"]
        nbits = fields["nbits"]
        nonce = fields["nonce"]

        header = build_header80(version, prevhash, merkle, ntime, nbits, nonce)
        self.assertEqual(len(header), 80)
        self.assertEqual(header.hex(), data["header_hex"])

        # Validate double-SHA256 hash matches Bitcoin Core Genesis Hash
        computed_hash_be = sha256d(header)[::-1].hex()
        self.assertEqual(computed_hash_be, data["block_hash_be"])
        self.assertEqual(computed_hash_be, "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206")

    def test_bip310_configure_payload_matches_directive(self):
        self.assertEqual(
            get_mining_configure_payload(),
            ["version-rolling",
             {"version-rolling.mask": "1fffe000",
              "version-rolling.min-bit-count": 16}]
        )

    def test_bip310_refuses_short_mask(self):
        self.assertEqual(
            parse_and_intersect_version_mask("0fffffff", "1fffe000"),
            "00000000"
        )

    def test_bip310_accepts_long_mask(self):
        self.assertEqual(
            parse_and_intersect_version_mask("1fffffff", "1fffe000"),
            "1fffe000"
        )

    def test_bip310_submit_arity_5_vs_6(self):
        # 5 params when version_bits_hex is None
        params_5 = build_mining_submit_params("worker1", "job1", "00000001", "60000000", "12345678", None)
        self.assertEqual(len(params_5), 5)
        self.assertEqual(params_5, ["worker1", "job1", "00000001", "60000000", "12345678"])

        # 6 params when version_bits_hex is not None
        params_6 = build_mining_submit_params("worker1", "job1", "00000001", "60000000", "12345678", "00002000")
        self.assertEqual(len(params_6), 6)
        self.assertEqual(params_6, ["worker1", "job1", "00000001", "60000000", "12345678", "00002000"])


if __name__ == "__main__":
    unittest.main()
