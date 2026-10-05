"""Tests for the Chronus-owned native SHA-256d lanes.

The CUDA lane is exercised end-to-end against a fake ``cupy`` module whose
``RawKernel`` emulates the kernel ABI in Python while computing digests
with real hashlib — so the bind-time self-check battery (which compares
device output to hashlib) runs genuinely, not as a stubbed pass. What this
does not cover is the actual NVRTC compilation of ``_CUDA_SHA256D_SOURCE``;
that requires CUDA hardware and is exercised by the benchmark script /
probe on a CUDA host.
"""

from __future__ import annotations

import hashlib
import struct
import sys
import types
import unittest
from unittest import mock

import numpy as np


def _sha256d(blob: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def _digest_at(header: bytes, nonce: int) -> bytes:
    return _sha256d(header[:76] + struct.pack("<I", nonce & 0xFFFFFFFF))


def _hits(digest: bytes, target_be: bytes) -> bool:
    return digest[::-1] <= target_be


GOLDEN_STRIDE = 0x9E3779B9
NO_HIT = 0xFFFFFFFF


class _FakeArray:
    """Minimal cupy.ndarray: a numpy backing store with set/get."""

    def __init__(self, array: np.ndarray):
        self._a = array

    @property
    def size(self) -> int:
        return int(self._a.size)

    @property
    def shape(self):
        return self._a.shape

    def set(self, value) -> None:
        self._a[...] = np.asarray(value, dtype=self._a.dtype).reshape(self._a.shape)

    def get(self) -> np.ndarray:
        return self._a.copy()

    def __getitem__(self, key):
        return _FakeArray(self._a[key])

    def __len__(self):
        return len(self._a)


def _unwrap(value):
    return value._a if isinstance(value, _FakeArray) else value


def _scalar(value) -> int:
    return int(np.asarray(_unwrap(value), dtype=np.uint64).item())


def _emulate_kernel(name: str, args: tuple) -> None:
    """Python emulation of the Chronus CUDA kernel contracts."""
    args = tuple(_unwrap(a) for a in args)
    if name == "bitcoin_sha256d":
        header, nonces, out, n = args
        header_b = bytes(np.asarray(header, dtype=np.uint8))
        nonces = np.asarray(nonces, dtype=np.uint32).ravel()
        for i in range(int(n)):
            out[i * 32 : (i + 1) * 32] = np.frombuffer(
                _digest_at(header_b, int(nonces[i])), np.uint8
            )
        return
    mid, header, target = (np.asarray(a, dtype=np.uint8).tobytes() for a in args[:3])
    if name == "bitcoin_sha256d_midstate":
        nonces, hits, n = args[3], args[4], _scalar(args[5])
        nonces = np.asarray(nonces, dtype=np.uint32).ravel()
        for i in range(n):
            hits[i] = 1 if _hits(_digest_at(header, int(nonces[i])), target) else 0
        return
    n = _scalar(args[-1])
    if name == "bitcoin_sha256d_gold":
        seed = _scalar(args[3])
        scratch = np.asarray(args[4], dtype=np.uint32)
        fifo = np.asarray(args[5], dtype=np.uint8)
        for gid in range(n):
            if _hits(_digest_at(header, (seed + gid * GOLDEN_STRIDE) & 0xFFFFFFFF), target):
                fifo[gid] = 1
                if gid < scratch[0]:
                    scratch[0] = gid
                scratch[1] += 1
        return
    scratch = np.asarray(args[-2], dtype=np.uint32)
    if name == "bitcoin_sha256d_range":
        base = _scalar(args[3])
        nonce_of = lambda gid: (base + gid) & 0xFFFFFFFF  # noqa: E731
    elif name == "bitcoin_sha256d_m32":
        base = _scalar(args[3])
        lanes = np.asarray(args[4], dtype=np.uint8)
        nonce_of = lambda gid: (  # noqa: E731
            base + int(lanes[gid % 32]) + 32 * (gid // 32)
        ) & 0xFFFFFFFF
    elif name == "bitcoin_sha256d_hendrix":
        base, window, stride, position_base = (
            _scalar(args[3]),
            _scalar(args[4]),
            _scalar(args[5]),
            _scalar(args[6]),
        )
        nonce_of = lambda gid: (  # noqa: E731
            base + ((position_base + gid) * stride) % window
        ) & 0xFFFFFFFF
    else:
        raise AssertionError(f"fake cupy has no emulation for {name}")
    for gid in range(n):
        if _hits(_digest_at(header, nonce_of(gid)), target):
            if gid < scratch[0]:
                scratch[0] = gid
            scratch[1] += 1


class _FakeRawKernel:
    def __init__(self, source, name, options=None):
        self.name = name

    def __call__(self, grid, tgroup, args):
        _emulate_kernel(self.name, args)


class _FakeEvent:
    def __init__(self, enable_timing=False):
        pass

    def record(self):
        pass

    def synchronize(self):
        pass


class _FakeDevice:
    def __init__(self, index):
        self.index = index

    def use(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_cupy() -> types.ModuleType:
    cp = types.ModuleType("cupy")
    cp.uint8 = np.uint8
    cp.uint32 = np.uint32

    def _empty(shape, dtype=np.uint8):
        if isinstance(shape, tuple):
            n = int(np.prod(shape))
        else:
            n = int(shape)
        return _FakeArray(np.zeros(n, dtype=dtype))

    cp.empty = _empty
    cp.zeros = _empty
    cp.asarray = lambda a, dtype=None: _FakeArray(
        np.asarray(a, dtype=dtype).copy()
    )
    cp.RawKernel = _FakeRawKernel
    cp.cuda = types.SimpleNamespace(
        Device=_FakeDevice,
        Event=_FakeEvent,
        get_elapsed_time=lambda a, b: 0.5,
        runtime=types.SimpleNamespace(
            getDeviceCount=lambda: 1,
            getDeviceProperties=lambda i: {
                "name": b"FakeCUDA",
                "totalGlobalMem": 1 << 30,
                "multiProcessorCount": 8,
            },
        ),
    )
    return cp


class _FakeMlxUnavailable:
    """Metal lane is expected to refuse on non-Darwin hosts."""


class NativeSha256dCudaTests(unittest.TestCase):
    """End-to-end under the fake cupy: the real host contract runs."""

    def _hasher(self):
        from mining.native_sha256d import ChronusCudaSha256dHasher

        with mock.patch.dict(sys.modules, {"cupy": _fake_cupy()}):
            return ChronusCudaSha256dHasher()

    def test_bind_runs_real_self_check(self):
        hasher = self._hasher()
        self.assertEqual(hasher.backend, "cuda")
        self.assertEqual(hasher.device, "FakeCUDA")
        self.assertEqual(hasher._gold_device_run, "PASS")
        self.assertFalse(hasher.telemetry()["opencl_required"])
        self.assertGreater(hasher.launches, 0)

    def test_hash_batch_parity_with_hashlib(self):
        hasher = self._hasher()
        header = bytes(range(80))
        nonces = [0, 1, 2, 999, 0xFFFFFFFF]
        expected = [_digest_at(header, n) for n in nonces]
        self.assertEqual(hasher.hash_batch(header, nonces), expected)

    def test_grind_range_winner_matches_cpu_reference(self):
        header = bytes(range(80))
        # target = digest at nonce 5 -> the smallest probe index whose
        # digest <= target wins; identical for every correct lane.
        hit_nonce = 5
        target = _digest_at(header, hit_nonce)[::-1]
        hasher = self._hasher()
        win, dig, count = hasher.grind_target_range(header, target, 0, 64)
        self.assertIsNotNone(win)
        self.assertEqual(count, 64)
        self.assertEqual(dig, _digest_at(header, win))
        self.assertLessEqual(_digest_at(header, win)[::-1], target)
        self.assertTrue(all(
            not _hits(_digest_at(header, n), target) or n >= win
            for n in range(64)
        ))

    def test_m32_gold_hendrix_orders(self):
        header = bytes(range(80))
        hasher = self._hasher()
        max_target = b"\xff" * 32
        lanes = tuple(range(32))
        win, dig, count = hasher.grind_target_m32(header, max_target, 0, lanes, 64)
        self.assertEqual(win, lanes[0])
        self.assertEqual(count, 64)
        win, dig, count, hit_nonces = hasher.grind_target_gold(
            header, max_target, 64, seed=7
        )
        self.assertEqual(win, 7)
        self.assertEqual(count, 64)
        # FIFO caps at GOLD_FIFO_DEPTH=8 earliest probe indices.
        self.assertEqual(
            hit_nonces, [(7 + g * GOLDEN_STRIDE) & 0xFFFFFFFF for g in range(8)]
        )
        win, dig, count = hasher.grind_target_hendrix(
            header, max_target, 0, 256, GOLDEN_STRIDE, 0, 64
        )
        self.assertEqual(win, 0)
        self.assertEqual(count, 64)

    def test_device_lie_is_rejected_by_recheck(self):
        """A fabricated hit fails the hashlib recheck instead of accepting."""
        hasher = self._hasher()
        header = bytes(range(80))
        with mock.patch.object(hasher, "_launch", return_value=(3, None)):
            with self.assertRaisesRegex(RuntimeError, "recheck"):
                hasher.grind_target_range(header, b"\x00" * 32, 0, 64)

    def test_validation_errors(self):
        hasher = self._hasher()
        header = bytes(range(80))
        with self.assertRaises(ValueError):
            hasher.hash_batch(b"short", [1])
        with self.assertRaises(ValueError):
            hasher.grind_target_range(header, b"\xff" * 31, 0, 64)
        with self.assertRaises(ValueError):
            hasher.grind_target_m32(header, b"\xff" * 32, 0, tuple(range(32)), 63)
        with self.assertRaises(ValueError):
            hasher.grind_target_batch(
                header,
                b"\xff" * 32,
                np.arange(hasher.grind_batch + 1, dtype=np.uint32),
            )
        self.assertEqual(hasher.hash_batch(header, []), [])


class NativeSha256dUnavailableTests(unittest.TestCase):
    def test_cuda_lane_fails_closed_without_cupy(self):
        from mining import native_sha256d

        with mock.patch.object(
            native_sha256d, "_load_cupy", side_effect=ImportError("no module")
        ):
            with self.assertRaises(native_sha256d.NativeSha256dUnavailable):
                native_sha256d.ChronusCudaSha256dHasher()

    def test_metal_lane_fails_closed_off_darwin(self):
        from mining import native_sha256d

        if sys.platform == "darwin":
            self.skipTest("requires a non-Darwin host")
        with self.assertRaises(native_sha256d.NativeSha256dUnavailable):
            native_sha256d.ChronusMetalSha256dHasher()

    def test_probe_reports_measured_reason(self):
        from mining import native_sha256d

        probe = native_sha256d.probe_metal_mining()
        self.assertEqual(probe.lane, "metal")
        self.assertEqual(probe.available, sys.platform == "darwin")
        self.assertFalse(probe.as_dict()["opencl_required"])
        if sys.platform != "darwin":
            self.assertIn("Darwin", probe.reason)


class HasherFactoryTests(unittest.TestCase):
    def test_factory_routes_native_tokens(self):
        from mining import bitcoin_hasher
        from mining import native_sha256d

        cuda_stub = mock.Mock(return_value="cuda-hasher")
        metal_stub = mock.Mock(return_value="metal-hasher")
        with mock.patch.object(
            native_sha256d, "ChronusCudaSha256dHasher", cuda_stub
        ), mock.patch.object(
            native_sha256d, "ChronusMetalSha256dHasher", metal_stub
        ):
            self.assertEqual(bitcoin_hasher.hasher_for_backend("cuda"), "cuda-hasher")
            self.assertEqual(bitcoin_hasher.hasher_for_backend("Metal"), "metal-hasher")

    def test_factory_rejects_unknown_token(self):
        from mining import bitcoin_hasher

        with self.assertRaisesRegex(ValueError, "unknown hasher backend"):
            bitcoin_hasher.hasher_for_backend("quantum")


if __name__ == "__main__":
    unittest.main()
