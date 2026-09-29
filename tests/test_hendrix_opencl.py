"""The Hendrix order executed by the OpenCL kernel, checked against the CPU.

Runs on any OpenCL runtime (an iGPU, or PoCL on a CPU); skipped without one.
The device must visit exactly the schedule's nonces, find the schedule's
first winner, and never be believed without the hashlib recheck.
"""

from __future__ import annotations

import hashlib
import math

import pytest

from mining.bitcoin_hasher import BitcoinHasher

HEADER = bytes(range(76)) + b"\x00\x00\x00\x00"


def _digest(nonce: int) -> bytes:
    blob = HEADER[:76] + nonce.to_bytes(4, "little")
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


@pytest.fixture(scope="module")
def device():
    pytest.importorskip("pyopencl")
    hasher = BitcoinHasher(backend="opencl")
    if not hasher.hendrix_on_device:
        pytest.skip(f"no OpenCL Hendrix kernel bound ({hasher.fallback_reason})")
    return hasher


def _schedule(base: int, window: int, stride: int, start: int, count: int) -> list[int]:
    return [(base + (p * stride) % window) & 0xFFFFFFFF for p in range(start, start + count)]


@pytest.mark.parametrize("window, stride", [(997, 610), (1024, 987), (4096, 2585)])
def test_the_device_finds_the_schedules_first_winner(device, window, stride):
    assert math.gcd(stride, window) == 1
    base = 123_456
    order = _schedule(base, window, stride, 0, window)
    assert sorted(order) == list(range(base, base + window))  # a bijection of the lease
    # The target is the minimum digest over the second half of the schedule,
    # so the first winner in schedule order is known exactly.
    half = window // 2
    later = order[half:]
    best = min(later, key=lambda n: int.from_bytes(_digest(n), "little"))
    target_int = int.from_bytes(_digest(best), "little")
    first = next(
        (i, n) for i, n in enumerate(order) if int.from_bytes(_digest(n), "little") <= target_int
    )
    target_be = target_int.to_bytes(32, "big")
    nonce, digest, hashes = device.grind_target_hendrix(
        HEADER, target_be, base, window, stride, 0, window
    )
    assert nonce == first[1] and digest == _digest(nonce)
    assert hashes >= first[0] + 1
    # The CPU path of the same method agrees.
    cpu = BitcoinHasher(backend="cpu")
    assert cpu.grind_target_hendrix(HEADER, target_be, base, window, stride, 0, window)[:2] == (
        nonce,
        digest,
    )


def test_an_impossible_target_hashes_every_position_and_finds_nothing(device):
    assert device.grind_target_hendrix(HEADER, bytes(32), 7, 997, 610, 100, 500) == (
        None,
        None,
        500,
    )


def test_inputs_outside_the_schedule_are_refused():
    cpu = BitcoinHasher(backend="cpu")
    with pytest.raises(ValueError, match="coprime"):
        cpu.grind_target_hendrix(HEADER, bytes(32), 0, 1024, 512, 0, 10)
    with pytest.raises(ValueError, match="inside the window"):
        cpu.grind_target_hendrix(HEADER, bytes(32), 0, 1024, 987, 1000, 100)
