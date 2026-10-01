"""Shared mathematical constants for the Aethel storage substrate."""

import numpy as np

DIM = 11

PHI = (1 + np.sqrt(5)) / 2
PSI = 1 - PHI
SQRT5 = np.sqrt(5)

LUCAS_15 = 1364
LUCAS_20 = 15127
LUCAS_31 = 3010349

MODULUS_Q = 2**61 - 1  # Mersenne prime for the Galois field

PRIMES_25 = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
    31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
    73, 79, 83, 89, 97,
]

# ---------------------------------------------------------------------------
# Shared-memory ingestion ABI v1 — the canonical constants mirrored from
# chronus/mla1517_platform/host/mla1517_aethel.h and mla1517_mmio.h.
# tests/test_aethel_concurrency.py parses the C headers at test time and
# asserts these values match exactly; do not diverge.
# ---------------------------------------------------------------------------

STATE_BYTES = 64              # MLA1517_STATE_BYTES
AETHEL_ABI_VERSION = 1        # MLA1517_AETHEL_ABI_VERSION
AETHEL_MAGIC = 0x4D4C413135313741  # MLA1517_AETHEL_MAGIC ("MLA1517A")
AETHEL_HEADER_BYTES = 0x40    # MLA1517_AETHEL_HEADER_BYTES
AETHEL_SLOT_STRIDE = 0x80     # MLA1517_AETHEL_SLOT_STRIDE
AETHEL_D7_OFFSET = 28         # MLA1517_AETHEL_D7_OFFSET
AETHEL_D10_OFFSET = 40        # MLA1517_AETHEL_D10_OFFSET
