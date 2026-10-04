import hashlib

import numpy as np
import pytest

from aethel.device import ChronusSku
from aethel.punch import resolve_punch_host, resolve_punch_host_class
from aethel.storage import FibonacciAddress
from aethel.zeckendorf import apply_zeckendorf_compression, reverse_zeckendorf_expansion
from chronus.opencl_host import OpenClPunchHost, PunchUnsupported


class _FakeMemFlags:
    READ_ONLY = 1
    WRITE_ONLY = 2
    READ_WRITE = 4
    COPY_HOST_PTR = 8


class _FakeBuffer:
    def __init__(self, hostbuf):
        self.hostbuf = hostbuf


class _FakeQueue:
    def finish(self):
        pass


class _FakeCl:
    mem_flags = _FakeMemFlags

    @staticmethod
    def Buffer(ctx, flags, hostbuf=None):
        return _FakeBuffer(hostbuf)

    @staticmethod
    def enqueue_copy(queue, dest, src):
        if src.hostbuf is not None:
            np.copyto(dest, src.hostbuf)


def _fake_device_host(hit_value=None):
    """An OpenClPunchHost wired to a fake device with no real OpenCL."""
    host = OpenClPunchHost.__new__(OpenClPunchHost)
    host.use_opencl = True
    host.backend = "opencl:fake-device"
    host.last_dispatch_backend = "none"
    host.last_cpu_rescan = None
    host._cl = _FakeCl
    host._ctx = object()
    host._queue = _FakeQueue()
    host._punch = None

    def _scan(queue, global_size, local_size, hdr_buf, tgt_buf, window, hit_buf):
        hit_buf.hostbuf[0] = -1 if hit_value is None else hit_value

    host._scan = _scan
    return host


def _u256(digest: bytes) -> int:
    return int.from_bytes(digest[::-1], "big")


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _earliest_winner(header76: bytes, window: int):
    scores = [_u256(_sha256d(header76 + n.to_bytes(4, "little"))) for n in range(window)]
    best = min(scores)
    return scores.index(best), best


def test_aethel_prefers_complete_unified_punch_contract():
    host_cls = resolve_punch_host_class()
    assert host_cls is not None
    assert {0x02, 0x15, 0x1C} <= host_cls.SUPPORTED_PUNCH_IDS


def test_resolved_host_roundtrips_more_than_eight_blocks():
    host = resolve_punch_host()
    assert host is not None
    payload = bytes(range(96))
    sparse = apply_zeckendorf_compression(payload, host=host)
    assert reverse_zeckendorf_expansion(sparse, host=host) == payload


def test_legacy_host_infers_encode_width_and_decodes_full_batch():
    host = OpenClPunchHost()
    values = np.arange(1, 11, dtype=np.uint64)
    encoded = host.run_punch_batch(0x02, in_ulong=values)["ulong"]
    assert encoded.shape == (len(values) * 121,)

    masks = np.empty(len(values) * 2, dtype=np.uint64)
    masks[0::2] = encoded[0::121][: len(values)]
    masks[1::2] = encoded[1::121][: len(values)]
    decoded = host.run_punch_batch(0x1C, n=len(values), in_ulong=masks)["ulong"]
    assert [int(decoded[index * 121]) for index in range(len(values))] == list(range(1, 11))


def test_legacy_host_executes_0x15_and_reports_the_actual_backend():
    host = OpenClPunchHost()
    result = host.run_punch_batch(0x15, n=1, in_float=np.ones(11, dtype=np.float32))
    assert result["float"].shape == (11,)
    assert np.isfinite(result["float"][0])
    assert host.last_dispatch_backend in ("cpu", "cpu_fallback") or (
        host.last_dispatch_backend.startswith("opencl:")
    )


def test_legacy_host_rejects_float_punches_it_cannot_execute_exactly():
    host = OpenClPunchHost()
    with pytest.raises(PunchUnsupported):
        host.run_punch_batch(0x02, n=1, in_float=np.ones(11, dtype=np.float32))


def test_standalone_writes_fibonacci_address():
    sku = ChronusSku("standalone")
    t = sku.ingest("job-solo", 15)
    assert t.mode == "standalone"
    assert isinstance(t.address, FibonacciAddress)
    assert t.ledger_ok is True
    assert sku.space.read(t.address)


def test_nested_sits_in_host_pool_same_ladder():
    sku = ChronusSku("nested")
    t = sku.ingest("job-host", 12)
    assert t.mode == "nested"
    assert t.work_items > 0
    assert t.ledger_ok is True
    assert sku.ctx.cu_pool is not None


def test_mandatory_cpu_rescan_confirms_true_device_hit():
    header = bytes(range(76))
    window = 64
    winner, target = _earliest_winner(header, window)
    host = _fake_device_host(hit_value=winner)
    assert host.scan_sha256d(header, target, window) == winner
    assert host.last_dispatch_backend == "opencl:fake-device"
    assert host.last_cpu_rescan["agreed"] is True
    assert host.last_cpu_rescan["device_claim"] == winner


def test_mandatory_cpu_rescan_corrects_phantom_device_hit():
    header = bytes(range(76))
    window = 64
    winner, target = _earliest_winner(header, window)
    phantom = (winner + 7) % window
    host = _fake_device_host(hit_value=phantom)
    assert host.scan_sha256d(header, target, window) == winner
    assert host.last_dispatch_backend == "cpu_fallback"
    assert host.last_cpu_rescan["agreed"] is False
    assert host.last_cpu_rescan["device_claim"] == phantom
    assert host.last_cpu_rescan["cpu_result"] == winner


def test_mandatory_cpu_rescan_catches_skipped_winner():
    header = bytes(range(76))
    window = 64
    winner, target = _earliest_winner(header, window)
    host = _fake_device_host(hit_value=None)  # device reports a miss
    assert host.scan_sha256d(header, target, window) == winner
    assert host.last_dispatch_backend == "cpu_fallback"
    assert host.last_cpu_rescan["agreed"] is False
    assert host.last_cpu_rescan["device_claim"] is None


def test_mandatory_cpu_rescan_confirms_true_device_miss():
    header = bytes(range(76))
    host = _fake_device_host(hit_value=None)
    assert host.scan_sha256d(header, 0, 64) is None
    assert host.last_dispatch_backend == "opencl:fake-device"
    assert host.last_cpu_rescan["agreed"] is True


def test_mandatory_cpu_rescan_reruns_wrong_device_punch():
    host = _fake_device_host()
    host._punch = object()  # mark the punch channel as bound
    values = np.array([1, 2, 3], dtype=np.uint64)
    ref = host._cpu_punch(0x02, values.size, values)

    bad = ref.copy()
    bad[0] += 1
    host._dispatch_punch = lambda opcode, count, vals: bad
    result = host.run_punch_batch(0x02, in_ulong=values)
    assert host.last_dispatch_backend == "cpu_fallback"
    assert host.last_cpu_rescan["agreed"] is False
    np.testing.assert_array_equal(result["ulong"], ref)

    host._dispatch_punch = lambda opcode, count, vals: ref.copy()
    result = host.run_punch_batch(0x02, in_ulong=values)
    assert host.last_dispatch_backend == "opencl:fake-device"
    assert host.last_cpu_rescan["agreed"] is True
    np.testing.assert_array_equal(result["ulong"], ref)


def test_mandatory_cpu_rescan_reruns_wrong_float_punch():
    host = _fake_device_host()
    host._punch = object()
    values = np.ones(11, dtype=np.float32)
    ref = host._cpu_punch_float(0x15, 1, values)

    bad = ref.copy()
    bad[0] += 1.0
    host._dispatch_punch_float = lambda opcode, count, vals: bad
    result = host.run_punch_batch(0x15, n=1, in_float=values)
    assert host.last_dispatch_backend == "cpu_fallback"
    assert host.last_cpu_rescan["agreed"] is False
    np.testing.assert_array_equal(result["float"], ref)

    host._dispatch_punch_float = lambda opcode, count, vals: ref.copy()
    result = host.run_punch_batch(0x15, n=1, in_float=values)
    assert host.last_dispatch_backend == "opencl:fake-device"
    assert host.last_cpu_rescan["agreed"] is True
    np.testing.assert_array_equal(result["float"], ref)
