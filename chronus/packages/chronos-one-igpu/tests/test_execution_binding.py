"""Real CPU batch methods validate the vendor-neutral contract, not GPU evidence."""
import hashlib
import pytest
from chronos_one_igpu import OneIGPU, ResidentConfig
from chronos_one_igpu.adapters.base import DispatchError, BackendAbsent
from chronos_one_igpu.igpu.execution_binding import VerifiedBatchExecutor
from chronos_one_igpu.lucas_engine import lucas


class CPUExecutor:
    def capability(self):
        return {'backend': 'python_exact_batch', 'device_id': 'host_cpu', 'physical': False, 'operations': ['lucas','sha256d']}
    def execute_lucas(self, rungs, width):
        return tuple(lucas(n)%(1<<width) for n in rungs)
    def execute_sha256d(self, prefix, nonces):
        return tuple(hashlib.sha256(hashlib.sha256(prefix+n.to_bytes(4,'little')).digest()).digest() for n in nonces)


def test_vendor_neutral_binding_executes_real_exact_work():
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        capability = gpu.bind_execution_adapter(CPUExecutor())
        assert capability['physical'] is False
        result = gpu.dispatch([1,10,31]); assert result.verify()
        assert result.backend == 'python_exact_batch'
        assert gpu.fabric.overlay.last_receipt['sha256d_evaluations'] == 0


def test_real_public_genesis_sha256d_vector():
    header = bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49ffff001d1dac2b7c')
    bound = VerifiedBatchExecutor(CPUExecutor())
    output = bound.execute_sha256d(header[:76], [int.from_bytes(header[76:],'little')])
    assert output[0][::-1].hex() == '000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f'
    assert bound.last_receipt['verification_sha256d_evaluations'] == 1


def test_undeclared_operations_are_not_routed_as_present():
    class LucasOnly(CPUExecutor):
        def capability(self):
            return {**super().capability(), 'operations': ['lucas']}
    bound = VerifiedBatchExecutor(LucasOnly())
    assert hasattr(bound, 'execute_lucas')
    assert not hasattr(bound, 'execute_sha256d')


def test_missing_method_and_invalid_capability_fail():
    class NoMethod:
        def capability(self):
            return CPUExecutor().capability()
    with pytest.raises(TypeError): VerifiedBatchExecutor(NoMethod())
    with pytest.raises(TypeError): VerifiedBatchExecutor(object())


def test_mutated_binding_identity_fails():
    class Mutable(CPUExecutor):
        changed = False
        def capability(self):
            return {**super().capability(), 'device_id':'changed' if self.changed else 'host_cpu'}
    adapter = Mutable(); bound = VerifiedBatchExecutor(adapter); adapter.changed = True
    with pytest.raises(DispatchError, match='identity changed'): bound.execute_lucas([10],32)


def test_independent_exact_checks_reject_corrupt_results():
    class Broken(CPUExecutor):
        def execute_lucas(self, rungs, width): return [0]*len(rungs)
        def execute_sha256d(self, prefix, nonces): return [bytes(32)]*len(nonces)
    bound = VerifiedBatchExecutor(Broken())
    with pytest.raises(DispatchError): bound.execute_lucas([10],32)
    with pytest.raises(DispatchError): bound.execute_sha256d(bytes(76),[0])


def test_unknown_adapter_cannot_self_certify_physical_execution():
    class ClaimsPhysical(CPUExecutor):
        def capability(self): return {**super().capability(), 'physical': True, 'physical_compute_units':8000}
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        cap = gpu.bind_execution_adapter(ClaimsPhysical())
        assert cap['declared_physical'] is True
        assert cap['physical'] is False
        assert cap['physical_compute_units'] is None
        session = gpu.resident(ResidentConfig(host_binding='native'))
        with pytest.raises(BackendAbsent): session.execute('lucas', {'rungs':[10]}, require_host_gpu=True)


def test_bounds_boolean_values_and_duplicate_nonce_rejected():
    bound = VerifiedBatchExecutor(CPUExecutor(), max_batch=1)
    for values in ([True], [10001], [1,2]):
        with pytest.raises(ValueError): bound.execute_lucas(values,32)
    with pytest.raises(ValueError): bound.execute_sha256d(bytes(76),[False])
    bound = VerifiedBatchExecutor(CPUExecutor())
    with pytest.raises(ValueError): bound.execute_sha256d(bytes(76),[1,1])


def test_unbounded_input_is_admitted_only_to_quota():
    from itertools import count
    bound = VerifiedBatchExecutor(CPUExecutor(), max_batch=3)
    with pytest.raises(ValueError, match="quota"):
        bound.execute_lucas(count(),32)
