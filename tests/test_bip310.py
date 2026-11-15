import unittest
from chronus.stratum.bip310 import (
    DEFAULT_CLIENT_MASK_HEX,
    parse_and_intersect_version_mask,
    apply_version_rolling,
    format_extranonce2,
    compute_shard_version_bits,
)


class TestBIP310(unittest.TestCase):
    def test_parse_and_intersect_version_mask(self):
        # Server mask 0x1fffe000 with default client mask 0x1fffe000
        intersected = parse_and_intersect_version_mask("1fffe000", DEFAULT_CLIENT_MASK_HEX)
        self.assertEqual(intersected, "1fffe000")

        # Non-overlapping server mask
        intersected_zero = parse_and_intersect_version_mask("00000000", DEFAULT_CLIENT_MASK_HEX)
        self.assertEqual(intersected_zero, "00000000")

        # Partial mask with < 16 bits must be refused per BIP310 minimum
        intersected_partial = parse_and_intersect_version_mask("0000e000", "1fffe000")
        self.assertEqual(intersected_partial, "00000000")

    def test_apply_version_rolling(self):
        base_ver = "20000000"
        mask = "1fffe000"
        rolled_bits = 0x00004000
        final_ver, bits_hex = apply_version_rolling(base_ver, mask, rolled_bits)
        self.assertEqual(bits_hex, "00004000")
        self.assertEqual(final_ver, int("20004000", 16))

        # Rolled bits masked out
        final_ver2, bits_hex2 = apply_version_rolling(base_ver, "00000000", 0x12345678)
        self.assertEqual(bits_hex2, "00000000")
        self.assertEqual(final_ver2, int(base_ver, 16))

    def test_format_extranonce2(self):
        # 4 bytes size -> 8 hex characters
        en2_hex = format_extranonce2(1, 4)
        self.assertEqual(en2_hex, "00000001")
        self.assertEqual(len(en2_hex), 8)

        en2_hex_large = format_extranonce2(0xdeadbeef, 4)
        self.assertEqual(en2_hex_large, "deadbeef")

        # 6 bytes size
        en2_6 = format_extranonce2(0x1234, 6)
        self.assertEqual(en2_6, "000000001234")
        self.assertEqual(len(en2_6), 12)

        with self.assertRaises(ValueError):
            format_extranonce2(1, 0)
        with self.assertRaises(ValueError):
            format_extranonce2(1 << 33, 4)  # Exceeds 4 bytes

    def test_compute_shard_version_bits(self):
        pool_mask = 0x1fffe000
        total_shards = 8
        assigned_masks = []
        for s in range(total_shards):
            v_bits = compute_shard_version_bits(s, total_shards, pool_mask)
            assigned_masks.append(v_bits)

        # Non-overlapping check across all shards
        self.assertEqual(len(assigned_masks), len(set(assigned_masks)))

        with self.assertRaises(ValueError):
            compute_shard_version_bits(-1, 8, pool_mask)
        with self.assertRaises(ValueError):
            compute_shard_version_bits(8, 8, pool_mask)
        with self.assertRaises(ValueError):
            compute_shard_version_bits(0, 0, pool_mask)


if __name__ == "__main__":
    unittest.main()
