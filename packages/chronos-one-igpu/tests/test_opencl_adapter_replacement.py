import dataclasses
import itertools
import pytest
from chronos_one_igpu.adapters.base import default_pipeline_spec,BackendAbsent,CompileError,CompiledKernel,DispatchError
from chronos_one_igpu.adapters.opencl import OpenCLAdapter

@pytest.mark.parametrize('change',[{'working_width':257},{'working_width':True},{'field':'approximation'},{'fail_closed':False}])
def test_adapter_invalid_spec_rejected_before_device_access(change):
    adapter=OpenCLAdapter(prime_rom_limit=1000)
    with pytest.raises(CompileError):adapter.compile(dataclasses.replace(default_pipeline_spec(32),**change))


def test_all_device_request_not_silently_hybrid():
    adapter=OpenCLAdapter(execution_profile='all_device_exact')
    with pytest.raises(BackendAbsent):adapter.compile(default_pipeline_spec(32))


def test_bounded_invalid_batch_rejected_before_probe():
    adapter=OpenCLAdapter(max_batch=2,prime_rom_limit=1000);kernel=CompiledKernel('opencl','uncompiled',default_pipeline_spec(32))
    with pytest.raises(DispatchError):adapter.dispatch(kernel,itertools.count())
    with pytest.raises(DispatchError):adapter.dispatch(kernel,[1000])
    with pytest.raises(RuntimeError):adapter.receipt()


def test_actual_adapter_preserves_full_datapath_when_gpu_exists():
    adapter=OpenCLAdapter(prime_rom_limit=1000)
    try:
        try:kernel=adapter.compile(default_pipeline_spec(32))
        except BackendAbsent as exc:pytest.skip('actual OpenCL adapter evidence UNAVAILABLE: '+str(exc))
        result=adapter.dispatch(kernel,[0,1,10]);details=adapter.receipt_details()
        assert len(result.records)==3 and details['all_six_stages_independently_verified']
        assert details['stage_placement']['lucas']=='opencl_exact_integer_with_host_verification'
        assert details['stage_placement']['binet']=='host_exact'
        assert not details['all_device_pipeline_claimed']and adapter.receipt().throughput_rps is None
        tampered=dataclasses.replace(kernel,kernel_digest='wrong')
        with pytest.raises(DispatchError):adapter.dispatch(tampered,[1])
    finally:adapter.close()


def test_prime_rom_integer_root_replacement_parity():
    from chronos_one_igpu.lucas_datapath import PrimeROM
    from math import isqrt
    rom=PrimeROM(1000);expected=[];n=2
    while len(expected)<1000:
        if all(n%d for d in range(2,isqrt(n)+1)):expected.append(n)
        n+=1
    assert rom.values==tuple(expected)and rom.lookup(1000)==7919


def test_existing_cpu_adapter_contract_and_certificate_preserved():
    from chronos_one_igpu.adapters.cpu import CpuAdapter
    from chronos_one_igpu.lucas_datapath import DatapathConfig
    from chronos_one_igpu.certificate import bind_record
    adapter=CpuAdapter(DatapathConfig(32,6,1000));kernel=adapter.compile(default_pipeline_spec(32));result=adapter.dispatch(kernel,[0,1,10])
    certificate=bind_record(result.records[2],adapter.receipt(),'reference')
    assert certificate.classification=='MEASURED'and len(result.records)==3
