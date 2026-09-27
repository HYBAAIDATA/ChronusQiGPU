import tempfile
import unittest
from pathlib import Path

from mla1517.primedb_engine import MLA1517State, NativePrimeDB

ROOT = Path(__file__).parents[1]
LIBRARY = ROOT / "host" / "libprimedb_storage.so"


@unittest.skipUnless(LIBRARY.exists(), "build host/libprimedb_storage.so first")
class NativePrimeDBTests(unittest.TestCase):
    def test_native_commit_and_callback_query(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativePrimeDB(directory, capacity_per_vertex=4, library_path=LIBRARY) as db:
                state = MLA1517State(
                    d1_nonce=123,
                    d5_zeckendorf=0x100,
                    d7_prime_addr=34,
                    d10_cassini=-1,
                    d11_time_state=456,
                )
                self.assertEqual(db.commit(state), (14, 0))
                matches = db.find_resonant_blocks(14, 0x1)
                self.assertEqual(matches[0]["nonce"], 123)
                self.assertEqual(matches[0]["cassini"], -1)

    def test_invalid_cassini_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativePrimeDB(directory, capacity_per_vertex=4, library_path=LIBRARY) as db:
                state = MLA1517State(d7_prime_addr=14, d10_cassini=0)
                with self.assertRaises(ValueError):
                    db.commit(state)
