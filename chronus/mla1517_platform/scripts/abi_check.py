#!/usr/bin/env python3
"""Build-time check for the C telemetry and Python snapshot ABI."""

from pathlib import Path
import ctypes
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from chronus.mla1517.telemetry_reader import (
    TELEMETRY_SIZE,
    OFF_MAGIC,
    OFF_VERSION,
    OFF_SEQ,
    OFF_PARTITIONS,
    OFF_VOIDS,
    OFF_ACCEPTED,
    OFF_FAULTS,
    OFF_DROPS,
    OFF_QUERY_FAULTS,
    OFF_RING_OVERFLOWS,
    OFF_CATASTROPHIC,
)

lib = ctypes.CDLL(
    os.getenv(
        "MLA1517_MMIO_LIBRARY", str(Path(__file__).resolve().parents[1] / "host/libmla1517_mmio.so")
    )
)
lib.mla1517_telemetry_size.restype = ctypes.c_size_t
lib.mla1517_telemetry_offset.argtypes = [ctypes.c_uint32]
lib.mla1517_telemetry_offset.restype = ctypes.c_size_t
assert lib.mla1517_telemetry_size() == TELEMETRY_SIZE
for field_id, expected in enumerate(
    (
        OFF_MAGIC,
        OFF_VERSION,
        OFF_SEQ,
        OFF_PARTITIONS,
        OFF_VOIDS,
        OFF_ACCEPTED,
        OFF_FAULTS,
        OFF_DROPS,
        OFF_QUERY_FAULTS,
        OFF_RING_OVERFLOWS,
        OFF_CATASTROPHIC,
    )
):
    actual = lib.mla1517_telemetry_offset(field_id)
    assert actual == expected, (field_id, actual, expected)
print('{"status":"PASS","telemetry_size":%d,"fields":11}' % TELEMETRY_SIZE)
