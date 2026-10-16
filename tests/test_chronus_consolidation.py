"""Consolidation regressions proving unified Chronus GPU architecture.

Validates:
1. Integrated GPU representation and selection (is_integrated=True, UMA shared host memory).
2. Discrete GPU representation and selection (dedicated VRAM pools).
3. Single-GPU execution topology constraint (device_count=1) in multi-device environments.
4. Memory accounting follows the selected device's actual model (UMA vs VRAM).
5. Authoritative backend selection and scheduling mechanism.
6. Fail-closed deterministic error semantics on unavailable hardware.
7. Device identity deduplication (authoritative pipeline, no dual identities).
8. OneIGPU canonical execution mode with honest device attestation.
"""

from __future__ import annotations

import pytest

import chronus
from chronus.domain import (
    ChronusBackend,
    ChronusCapabilities,
    ChronusDevice,
    ChronusDeviceTopology,
    ChronusDeviceType,
    ChronusDeviceUnavailableError,
    ChronusExecutionContext,
    ChronusExecutionPolicy,
    ChronusMemory,
    ChronusOutOfMemoryError,
    ChronusRuntime,
    ChronusScheduler,
)
from chronus.detect import (
    DetectedDevice,
    to_chronus_device,
    chronus_devices,
    device_identity,
)
from chronus.one_igpu import OneIGPU, OneIGPUResult


@pytest.mark.unit
def test_integrated_gpu_domain_model_and_memory():
    """Chronus correctly represents an integrated GPU with UMA shared system memory."""
    mem = ChronusMemory(
        total_bytes=16 * 1024 * 1024 * 1024,
        is_unified=True,
        memory_type="UMA",
        max_allocation_bytes=4 * 1024 * 1024 * 1024,
    )
    caps = ChronusCapabilities(
        operations=("matmul", "fft", "reduction"),
        compute_units=32,
        has_unified_memory=True,
        is_integrated=True,
    )
    device = ChronusDevice(
        id="opencl:intel:iris_xe",
        name="Intel Iris Xe Graphics",
        vendor="intel",
        device_type=ChronusDeviceType.INTEGRATED_GPU,
        backend=ChronusBackend.OPENCL,
        memory=mem,
        capabilities=caps,
        is_integrated=True,
        is_gpu=True,
    )

    assert device.is_integrated is True
    assert device.device_type == ChronusDeviceType.INTEGRATED_GPU
    assert device.memory.is_unified is True
    assert device.memory.memory_type == "UMA"
    assert device.capabilities.has_unified_memory is True

    # Memory allocation and tracking
    alloc = device.memory.allocate(1024 * 1024, tag="tensor_buffer")
    assert alloc["nbytes"] == 1024 * 1024
    assert alloc["is_unified"] is True
    assert device.memory.allocated_bytes == 1024 * 1024
    assert device.memory.free_bytes == (16 * 1024 * 1024 * 1024) - (1024 * 1024)

    # Release memory
    device.memory.release(1024 * 1024)
    assert device.memory.allocated_bytes == 0


@pytest.mark.unit
def test_discrete_gpu_domain_model_and_memory():
    """Chronus correctly represents a discrete GPU with dedicated VRAM pools."""
    mem = ChronusMemory(
        total_bytes=24 * 1024 * 1024 * 1024,
        is_unified=False,
        memory_type="VRAM",
        max_allocation_bytes=24 * 1024 * 1024 * 1024,
    )
    caps = ChronusCapabilities(
        operations=("matmul", "tensor_core", "sha256d"),
        compute_units=128,
        tensor_cores=True,
        has_unified_memory=False,
        is_integrated=False,
    )
    device = ChronusDevice(
        id="cuda:nvidia:rtx_4090",
        name="NVIDIA GeForce RTX 4090",
        vendor="nvidia",
        device_type=ChronusDeviceType.DISCRETE_GPU,
        backend=ChronusBackend.CUDA,
        memory=mem,
        capabilities=caps,
        is_integrated=False,
        is_gpu=True,
    )

    assert device.is_integrated is False
    assert device.device_type == ChronusDeviceType.DISCRETE_GPU
    assert device.memory.is_unified is False
    assert device.memory.memory_type == "VRAM"
    assert device.capabilities.tensor_cores is True

    # OOM behavior
    with pytest.raises(ChronusOutOfMemoryError):
        device.memory.allocate(30 * 1024 * 1024 * 1024)


@pytest.mark.unit
def test_single_gpu_policy_in_multi_device_environment():
    """Single-GPU scheduling constraint (device_count=1) selects exactly one device."""
    igpu = ChronusDevice(
        id="opencl:intel:iris",
        name="Intel Iris Xe",
        vendor="intel",
        device_type=ChronusDeviceType.INTEGRATED_GPU,
        backend=ChronusBackend.OPENCL,
        is_integrated=True,
    )
    dgpu_1 = ChronusDevice(
        id="cuda:nvidia:rtx_4090",
        name="NVIDIA GeForce RTX 4090",
        vendor="nvidia",
        device_type=ChronusDeviceType.DISCRETE_GPU,
        backend=ChronusBackend.CUDA,
        is_integrated=False,
    )
    dgpu_2 = ChronusDevice(
        id="cuda:nvidia:rtx_3080",
        name="NVIDIA GeForce RTX 3080",
        vendor="nvidia",
        device_type=ChronusDeviceType.DISCRETE_GPU,
        backend=ChronusBackend.CUDA,
        is_integrated=False,
    )

    scheduler = ChronusScheduler(devices=[igpu, dgpu_1, dgpu_2])

    # Topology: SINGLE, prefer integrated
    selected_igpu = scheduler.select_device(
        topology=ChronusDeviceTopology.SINGLE,
        prefer_integrated=True,
    )
    assert selected_igpu is not None
    assert selected_igpu.id == "opencl:intel:iris"
    assert selected_igpu.is_integrated is True

    # Topology: SINGLE, discrete only
    selected_dgpu = scheduler.select_device(
        topology=ChronusDeviceTopology.SINGLE,
        policy=ChronusExecutionPolicy.DISCRETE_ONLY,
    )
    assert selected_dgpu is not None
    assert selected_dgpu.is_integrated is False
    assert selected_dgpu.backend == ChronusBackend.CUDA

    # Creating context for single GPU binds exactly one device
    ctx = scheduler.create_context(selected_dgpu)
    assert ctx.device.id == selected_dgpu.id
    assert ctx.policy == ChronusExecutionPolicy.FAIL_CLOSED


@pytest.mark.unit
def test_backend_selection_and_deterministic_failure():
    """Backend selection succeeds when available and fails deterministically when absent."""
    cpu_device = ChronusDevice(
        id="cpu:generic:host",
        name="Host CPU",
        vendor="generic",
        device_type=ChronusDeviceType.CPU,
        backend=ChronusBackend.CPU,
        is_integrated=False,
        is_gpu=False,
    )
    scheduler = ChronusScheduler(devices=[cpu_device])

    # Requesting CUDA under FAIL_CLOSED policy must raise ChronusDeviceUnavailableError
    with pytest.raises(ChronusDeviceUnavailableError) as exc_info:
        scheduler.select_device(
            backend=ChronusBackend.CUDA,
            policy=ChronusExecutionPolicy.FAIL_CLOSED,
        )
    assert "No suitable Chronus device found" in str(exc_info.value)

    # Requesting under FALLBACK_ALLOWED allows selecting available fallback
    fallback_device = scheduler.select_device(
        backend=ChronusBackend.CUDA,
        policy=ChronusExecutionPolicy.FALLBACK_ALLOWED,
    )
    assert fallback_device is not None
    assert fallback_device.backend == ChronusBackend.CPU


@pytest.mark.unit
def test_authoritative_discovery_pipeline_and_deduplication():
    """Authoritative discovery normalizes and deduplicates devices without duplicate identities."""
    from chronus.detect import find_prior

    d1 = DetectedDevice(
        backend="cuda",
        name="GeForce RTX 4090",
        vendor="nvidia",
        is_gpu=True,
        is_integrated=False,
    )
    d2 = DetectedDevice(
        backend="opencl",
        name="GeForce RTX 4090",
        vendor="NVIDIA Corporation",
        is_gpu=True,
        is_integrated=False,
    )

    cd1 = to_chronus_device(d1)
    cd2 = to_chronus_device(d2)

    assert cd1.backend == ChronusBackend.CUDA
    assert cd2.backend == ChronusBackend.OPENCL
    # Canonical identity check matches underlying physical vendor/device normalization
    ident1 = cd1.identity
    ident2 = cd2.identity
    assert ident1 == ident2 == ("geforce rtx 4090", "nvidia")
    prior = find_prior([d1], d2.identity)
    assert prior is d1


@pytest.mark.unit
def test_execution_context_honest_attestation():
    """Chronus execution context honestly reports execution device and prevents false claims."""
    cpu_device = ChronusDevice(
        id="cpu:generic:host",
        name="Host CPU",
        vendor="generic",
        device_type=ChronusDeviceType.CPU,
        backend=ChronusBackend.CPU,
        is_integrated=False,
        is_gpu=False,
    )
    ctx = ChronusExecutionContext(device=cpu_device, policy=ChronusExecutionPolicy.FAIL_CLOSED)

    receipt = ctx.execute({"operation": "benchmark_hash", "inputs": [1, 2, 3]})
    assert receipt["executed"] is True
    assert receipt["device_id"] == "cpu:generic:host"
    assert receipt["backend"] == "cpu"
    # Never claim physical GPU when running on CPU
    assert receipt["is_gpu"] is False
    assert receipt["is_integrated"] is False


@pytest.mark.unit
def test_one_igpu_canonical_execution_mode():
    """Chronus OneIGPU execution mode runs exact verified datapath and generates valid attestation."""
    # Test canonical OneIGPU execution mode directly imported from chronus
    engine = OneIGPU(
        mode="standalone",
        working_width=32,
        prime_rom_limit=1000,
        golden_quantum_enabled=False,
    )
    result = engine.dispatch([15, 16])

    assert isinstance(result, OneIGPUResult)
    assert result.verify() is True
    assert len(result.records) == 2
    assert result.backend == "cpu_reference"
    # Attestation receipt contains honest execution identity
    assert result.evidence is not None
    assert result.plan["executor"] == "cpu_reference"
