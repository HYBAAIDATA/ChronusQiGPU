import numpy as np
import pytest

from aethel.device import IGpuSku
from aethel.punch import resolve_punch_host, resolve_punch_host_class
from aethel.storage import FibonacciAddress
from aethel.zeckendorf import apply_zeckendorf_compression, reverse_zeckendorf_expansion
from igpu.opencl_host import OpenClPunchHost, PunchUnsupported


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


def test_legacy_host_rejects_float_punches_it_cannot_execute_exactly():
    host = OpenClPunchHost()
    with pytest.raises(PunchUnsupported):
        host.run_punch_batch(0x15, n=1, in_float=np.ones(11, dtype=np.float32))


def test_standalone_writes_fibonacci_address():
    sku = IGpuSku("standalone")
    t = sku.ingest("job-solo", 15)
    assert t.mode == "standalone"
    assert isinstance(t.address, FibonacciAddress)
    assert t.ledger_ok is True
    assert sku.space.read(t.address)


def test_nested_sits_in_host_pool_same_ladder():
    sku = IGpuSku("nested")
    t = sku.ingest("job-host", 12)
    assert t.mode == "nested"
    assert t.work_items > 0
    assert t.ledger_ok is True
    assert sku.ctx.cu_pool is not None
