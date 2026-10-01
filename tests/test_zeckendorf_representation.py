"""The Zeckendorf encoders agree on the summands, not on the raw bit positions."""

import importlib.util
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from millennium.poincare_golden_11d import FIB_TABLE, encode_zeckendorf

_CORE_PATH = _ROOT / "chronus" / "mla1517" / "core.py"
_spec = importlib.util.spec_from_file_location("zeckendorf_core", _CORE_PATH)
_core = importlib.util.module_from_spec(_spec)
sys.modules["zeckendorf_core"] = _core
_spec.loader.exec_module(_core)


def _reconstruct(mask: int) -> int:
    return sum(FIB_TABLE[i] for i in range(len(FIB_TABLE)) if mask & (1 << i))


def _indices(n: int) -> tuple[int, ...]:
    """Greedy Zeckendorf indices, F_2 = 1, F_3 = 2, no consecutive indices."""
    if n <= 0:
        return ()
    fibs = [(2, 1)]
    a, b, idx = 1, 2, 3
    while b <= n:
        fibs.append((idx, b))
        a, b, idx = b, a + b, idx + 1
    rem = n
    chosen = []
    for index, value in reversed(fibs):
        if value <= rem:
            chosen.append(index)
            rem -= value
    if rem:
        raise AssertionError(rem)
    return tuple(chosen)


class ZeckendorfRepresentationTests(unittest.TestCase):
    def test_encoders_agree_on_summands_below_the_bucket_window(self) -> None:
        for n in range(0, 4000):
            indices = _indices(n)
            self.assertEqual(sum(FIB_TABLE[i] for i in indices), n)
            ordered = tuple(sorted(indices))
            self.assertTrue(all(b - a >= 2 for a, b in zip(ordered, ordered[1:])))
            core_mask, core_bits = _core.zeckendorf(n)
            self.assertEqual(_core.zeckendorf_decode(core_mask), n)
            self.assertEqual(core_mask & (core_mask << 1), 0)
            # core bit i is F_{i+2}; the Poincaré mask stores F_i in bit i.
            self.assertEqual(tuple(i + 2 for i in core_bits), tuple(sorted(indices, reverse=True)))
            if n == 0:
                self.assertEqual(encode_zeckendorf(0), (0, 0))
                continue
            mask, _max_k = encode_zeckendorf(n)
            self.assertEqual(_reconstruct(mask), n)
            self.assertEqual(mask & (mask << 1), 0)
            self.assertEqual(
                tuple(i for i in range(len(FIB_TABLE)) if mask & (1 << i)),
                tuple(sorted(indices)),
            )
            self.assertEqual(mask, core_mask << 2)

    def test_bucket_window_fails_closed_at_F25(self) -> None:
        last = FIB_TABLE[25] - 1
        mask, _ = encode_zeckendorf(last)
        self.assertEqual(_reconstruct(mask), last)
        with self.assertRaises(ValueError):
            encode_zeckendorf(FIB_TABLE[25])


if __name__ == "__main__":
    unittest.main()
