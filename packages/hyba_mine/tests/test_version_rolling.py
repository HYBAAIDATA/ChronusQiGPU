# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""BIP310 version rolling: rolling math, rolled work units, host recheck, itinerary."""

import struct
import unittest
from fractions import Fraction

import _support  # noqa: F401  (import paths)
from _support import GENESIS_EN2, GENESIS_NONCE, VerifyingPool

from chronus.execution.stratum import StratumJob
from chronus.stratum.bip310 import apply_version_rolling

from hyba_mine.plan import NONCE_SPACE, PythiaItinerary, UnitSpec
from hyba_mine.vectors import GENESIS
from hyba_mine.work import (
    CLIENT_VERSION_MASK,
    HostRecheck,
    MiningJob,
    make_unit,
    pdep,
    roll_version,
    sha256d,
    version_fits,
    version_space,
)

GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
EASY = Fraction(1, 2 ** 32)  # every hash meets this share target


def genesis_job() -> MiningJob:
    """The verifying pool's genesis job, as the client receives it (extranonce1 '', size 4)."""
    params = VerifyingPool().notify_message("genesis", True)["params"]
    return MiningJob(job=StratumJob.from_notify(list(params)), pool_id="viabtc", generation=1, epoch=0,
                     extranonce1=b"", extranonce2_size=4, difficulty=Fraction(1), received_at="test")


class TestRollingMath(unittest.TestCase):
    def test_index_zero_is_the_job_version(self):
        self.assertEqual(roll_version(0x20000000, 0x1FFFE000, 0), (0x20000000, 0))
        self.assertEqual(roll_version(0x20002000, 0x1FFFE000, 0), (0x20002000, 0x2000))
        for base in (0x00000001, 0x20000000, 0x3FFFFFFF):
            self.assertEqual(roll_version(base, 0, 0), (base, 0))

    def test_rolled_versions_are_distinct_inside_the_mask_and_match_chronus(self):
        base, mask = 0x20000000, 0x0000E000
        rolled = [roll_version(base, mask, index) for index in range(8)]
        self.assertEqual(len({version for version, _ in rolled}), 8)
        for version, bits in rolled:
            self.assertEqual(bits & ~mask, 0)
            self.assertEqual(version & ~mask, base & ~mask)
            self.assertEqual(version, apply_version_rolling(base, mask, bits)[0])
            self.assertTrue(version_fits(base, version, bits, mask))

    def test_pdep_and_version_space(self):
        self.assertEqual(version_space(0), 1)
        self.assertEqual(version_space(0x1FFFE000), 65536)
        self.assertEqual(pdep(0, 0x1FFFE000), 0)
        self.assertEqual(pdep(1, 0x1FFFE000), 0x00002000)
        self.assertEqual(pdep(16, 0x1FFFE000), 0x00020000)
        self.assertEqual(pdep(65535, 0x1FFFE000), 0x1FFFE000)
        with self.assertRaises(ValueError):
            pdep(8, 0x0000E000)
        with self.assertRaises(ValueError):
            pdep(-1, 0x0000E000)

    def test_version_fits_detects_mask_withdrawal(self):
        base = 0x20000000
        version, bits = roll_version(base, 0x1FFFE000, 16)
        self.assertEqual(bits, 0x00020000)
        self.assertTrue(version_fits(base, version, bits, 0x1FFFE000))
        self.assertFalse(version_fits(base, version, bits, 0x0000E000))
        self.assertFalse(version_fits(base, version, bits, 0))
        version0, bits0 = roll_version(base, 0x1FFFE000, 0)
        for mask in (0, 0x0000E000, 0x1FFFE000):
            self.assertTrue(version_fits(base, version0, bits0, mask))


class TestUnits(unittest.TestCase):
    def test_make_unit_prefix_carries_rolled_version(self):
        job = genesis_job()
        self.assertEqual(job.header_prefix(GENESIS_EN2), GENESIS.prefix)
        plain = make_unit(job, 1, 0, 4096, Fraction(1), 20)
        zero = make_unit(job, 1, 0, 4096, Fraction(1), 20, version_mask=CLIENT_VERSION_MASK, version_index=0)
        rolled = make_unit(job, 1, 0, 4096, Fraction(1), 20, version_mask=CLIENT_VERSION_MASK, version_index=5)
        self.assertEqual(plain.header_prefix, GENESIS.prefix)
        self.assertEqual(zero.unit_id, plain.unit_id)
        self.assertEqual(zero.header_prefix, plain.header_prefix)
        self.assertEqual(rolled.version, roll_version(job.base_version, CLIENT_VERSION_MASK, 5)[0])
        self.assertEqual(rolled.header_prefix[:4], struct.pack("<I", rolled.version))
        self.assertEqual(rolled.header_prefix[4:], plain.header_prefix[4:])  # merkle root unchanged
        self.assertNotEqual(rolled.unit_id, plain.unit_id)
        self.assertNotEqual(rolled.plan.offset, plain.plan.offset)
        wire, view = rolled.to_wire(), rolled.ledger_view()
        self.assertEqual(wire["version_bits_hex"], f"{rolled.version_bits:08x}")
        self.assertEqual(wire["version_mask_hex"], "1fffe000")
        self.assertEqual(wire["version_hex"], f"{rolled.version:08x}")
        self.assertEqual(view["version_bits"], f"{rolled.version_bits:08x}")
        self.assertEqual(view["version_mask"], "1fffe000")
        self.assertEqual(view["version_index"], 5)
        self.assertEqual(plain.ledger_view()["version_bits"], "00000000")
        with self.assertRaises(ValueError):
            make_unit(job, 1, 0, 4096, Fraction(1), 20, version_mask=0xE0000000)
        with self.assertRaises(ValueError):
            make_unit(job, 1, 0, 4096, Fraction(1), 20, version_mask=0x0000E000, version_index=8)

    def test_host_recheck_uses_rolled_bits(self):
        job = genesis_job()
        mask = CLIENT_VERSION_MASK
        unit = make_unit(job, 1, 0, 4096, EASY, 20, version_mask=mask, version_index=5)
        nonce = unit.plan.nonce_at(0)
        recheck = HostRecheck()
        outcome = recheck.check(job, unit.en2, nonce, EASY, version_bits=unit.version_bits, version_mask=mask)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.hash_hex, sha256d(unit.header_prefix + struct.pack("<I", nonce))[::-1].hex())
        outside = recheck.check(job, unit.en2, nonce, EASY, version_bits=0x00000001, version_mask=mask)
        self.assertEqual(outside.reason, "VERSION_MASK")
        other = make_unit(job, 1, 0, 4096, EASY, 20, version_mask=mask, version_index=6)
        self.assertTrue(recheck.check(job, unit.en2, nonce, EASY, version_bits=other.version_bits, version_mask=mask).ok)
        again = recheck.check(job, unit.en2, nonce, EASY, version_bits=unit.version_bits, version_mask=mask)
        self.assertEqual(again.reason, "DUP")

    def test_genesis_known_answer_rechecks_under_a_granted_mask(self):
        job = genesis_job()
        unit = make_unit(job, 1, 0, 4096, Fraction(1), 20, version_mask=CLIENT_VERSION_MASK, version_index=0)
        outcome = HostRecheck().check(job, unit.en2, GENESIS_NONCE, Fraction(1),
                                      version_bits=unit.version_bits, version_mask=CLIENT_VERSION_MASK)
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.hash_hex, GENESIS_HASH)


class TestItinerary(unittest.TestCase):
    def test_versions_roll_inside_each_extranonce2(self):
        units = list(PythiaItinerary(window_bits=30, windows_per_unit=4).units(en2_limit=2, version_count=4))
        order = []
        for unit in units:
            if not order or order[-1] != (unit.en2_counter, unit.version_index):
                order.append((unit.en2_counter, unit.version_index))
        self.assertEqual(order, [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)])
        for key in order:
            covered = sorted((u.start, u.start + u.count) for u in units if (u.en2_counter, u.version_index) == key)
            position = 0
            for start, end in covered:
                self.assertEqual(start, position)
                position = end
            self.assertEqual(position, NONCE_SPACE)

    def test_default_schedule_is_unchanged(self):
        itinerary = PythiaItinerary(window_bits=30, windows_per_unit=1)
        self.assertEqual(list(itinerary.units(1)), list(itinerary.units(1, version_count=1)))
        self.assertTrue(all(u.version_index == 0 for u in itinerary.units(2)))

    def test_override_version_index_is_checked(self):
        itinerary = PythiaItinerary(override=(UnitSpec(0, 0, 4096, version_index=4),))
        self.assertEqual(len(list(itinerary.units(1, version_count=5))), 1)
        with self.assertRaises(ValueError):
            list(itinerary.units(1, version_count=4))
        with self.assertRaises(ValueError):
            list(PythiaItinerary().units(1, version_count=0))


if __name__ == "__main__":
    unittest.main()
