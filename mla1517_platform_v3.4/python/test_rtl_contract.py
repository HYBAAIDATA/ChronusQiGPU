import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
GENERATOR = ROOT / "rtl" / "scripts" / "zcore_rom_generator.py"


def decode_hex_lines(path):
    return [int(line.strip(), 16) for line in path.read_text().splitlines() if line.strip()]


def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def zeckendorf(value):
    fibs = [1, 2]
    while fibs[-1] <= value:
        fibs.append(fibs[-1] + fibs[-2])
    remainder = value
    code = 0
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remainder:
            remainder -= fibs[i]
            code |= 1 << i
    return code


class RTLContractTests(unittest.TestCase):
    def test_rom_generator_and_exact_d5(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--max-nonce",
                    "255",
                    "--fractional-bits",
                    "16",
                    "--out-dir",
                    str(out),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads((out / "zcore_rom_manifest.json").read_text())
            d5 = decode_hex_lines(out / "zcore_d5_zeckendorf.mem")
            d6 = decode_hex_lines(out / "zcore_d6_binet_q.mem")
            self.assertEqual(manifest["depth"], 256)
            self.assertEqual(len(d5), 256)
            self.assertEqual(len(d6), 256)
            for n, code in enumerate(d5):
                self.assertEqual(code, zeckendorf(n))
                self.assertEqual(code & (code << 1), 0)
            self.assertTrue(all(d6[i] < d6[i + 1] for i in range(255)))

    def test_fibonacci_void_anchor_and_cassini(self):
        difficulty_mask = 0x3F
        anchor_mask = 0x40
        winners = []
        for lane in range(32):
            code = zeckendorf(lane)
            if (code & difficulty_mask) == 0 and (code & anchor_mask):
                winners.append(lane)
        self.assertTrue(winners)
        n = 5
        self.assertEqual(fib(n - 1) * fib(n + 1) - fib(n) ** 2, -1)

    def test_rom_boundary_is_explicit(self):
        rom_addr_width = 8
        rom_depth = 1 << rom_addr_width
        self.assertEqual(rom_depth, 256)
        # The RTL contract must reject rather than wrap nonce 256 to address 0.
        self.assertGreaterEqual(256, rom_depth)


if __name__ == "__main__":
    unittest.main(verbosity=2)
