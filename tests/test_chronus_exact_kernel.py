import ctypes
import random
import subprocess
from chronus.compiler.exact_kernel import ExactKernelIR
from chronus.virtual_igpu.exact_kernel import execute_kernel, verify_kernel


def test_fused_ir_native_simd_compilation_matches_integer_oracle(tmp_path):
    ir = ExactKernelIR(tile_items=123)
    indices = list(range(100)) + [random.Random(1337 + i).randrange(1025) for i in range(40)]
    source, library = tmp_path / "kernel.c", tmp_path / "kernel.so"
    source.write_text(ir.lower("c"))
    subprocess.run(
        ["cc", "-O3", "-fopenmp-simd", "-shared", "-fPIC", str(source), "-o", str(library)],
        check=True,
    )
    fn = ctypes.CDLL(str(library)).chronus_kernel
    u32 = ctypes.c_uint32
    fn.argtypes = [ctypes.POINTER(u32), u32, u32, ctypes.POINTER(u32)]
    fn.restype = None
    data, output = (u32 * len(indices))(*indices), (u32 * (len(indices) * 5))()
    fn(data, len(indices), 0xFFFFFFF0, output)
    rows = [list(output[i : i + 5]) for i in range(0, len(output), 5)]
    assert rows == ir.reference(indices, 0xFFFFFFF0) == ir.execute(indices, 0xFFFFFFF0)
    request = {"ir": ir.to_dict(), "indices": indices, "seed": 0xFFFFFFF0}
    result = execute_kernel(request)
    assert verify_kernel(request, result) == []
    result["rows"][0][0] ^= 1
    assert verify_kernel(request, result)
    assert ir.legality()["tile_working_bytes"] <= 32768


def test_scaled_independent_native_gpu_uses_lucas_plan_and_exact_receipts(tmp_path):
    import pytest
    from chronus.scaled_gpiu import ScaledGPIU
    from chronus.virtual_igpu.portable_adapter import PortableExactAdapter
    from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeConfig

    adapter = PortableExactAdapter("c")
    runtime = RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[adapter])
    engine = ScaledGPIU(runtime, tenant="scale-test")
    result = engine.execute(workload_id="scaled", base_items=1, scale_index=10, chunk_items=32)
    assert result["executed_items"] == 123
    assert all(row[1] == 123 for row in result["rows"])
    assert len({row[3] for row in result["rows"]}) == 123
    assert all(r["verification"]["verdict"] == "match" for r in result["receipts"])
    assert result["golden_pisot_conjugate_bound"] == [2**10, 3**10]
    with pytest.raises(MemoryError):
        engine.execute(workload_id="oversize", base_items=1000, max_items=100)
    host = ScaledGPIU(runtime, tenant="scale-test", mode="host", host_adapter_id=adapter.id)
    with pytest.raises(ValueError, match="host accelerator"):
        host.execute(workload_id="host", base_items=1)


def test_host_augmentation_discovers_without_manual_binding(tmp_path):
    from chronus.scaled_gpiu import ScaledGPIU
    from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
    from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeConfig

    runtime = RuntimeDaemon(
        RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()]
    )
    engine = ScaledGPIU(runtime, tenant="capacity", mode="host_gpu_augmentation")
    result = engine.execute(workload_id="automatic", base_items=1, scale_index=10)
    assert result["product_mode"] == "host_gpu_augmentation"
    assert result["executed_items"] == 123
    assert all(r["actual_device"] == "cpu-emulator" for r in result["receipts"])
    # Missing accelerator follows the existing, explicitly labelled fallback policy.
    assert all("software_fallback" in str(r) for r in result["receipts"])
