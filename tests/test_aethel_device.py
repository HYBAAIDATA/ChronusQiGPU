from aethel.device import IGpuSku
from aethel.storage import FibonacciAddress


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
