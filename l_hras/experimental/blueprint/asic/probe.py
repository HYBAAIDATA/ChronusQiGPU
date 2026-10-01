# l_hras/asic/probe.py

import time
import numpy as np
from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.capability import ASICCapability

def run_hash_benchmark(device, duration: float) -> int:
    runner = getattr(device, "run_hash_benchmark", None)
    if not callable(runner):
        raise RuntimeError("device does not expose run_hash_benchmark")
    return int(runner(duration))

def read_power(device) -> float:
    reader = getattr(device, "read_power", None)
    if not callable(reader):
        raise RuntimeError("device does not expose read_power")
    return float(reader())

def build_attestation_chain(device) -> list:
    builder = getattr(device, "build_attestation_chain", None)
    if not callable(builder):
        raise RuntimeError("device does not expose build_attestation_chain")
    chain = list(builder())
    if not chain:
        raise RuntimeError("device returned an empty attestation chain")
    return chain

def measure_hashrate_distribution(device, samples: int = 64, warmup: int = 8) -> Distribution:
    """Measure the hashrate distribution."""
    measurements = []
    for i in range(samples + warmup):
        start = time.perf_counter_ns()
        hashes = run_hash_benchmark(device, duration=0.01)
        elapsed = max(1, time.perf_counter_ns() - start) / 1_000_000_000.0
        hps = hashes / elapsed
        if i >= warmup:
            measurements.append(hps)
    return Distribution(
        mean=float(np.mean(measurements)),
        stddev=float(np.std(measurements)),
        samples=len(measurements),
        p50=float(np.percentile(measurements, 50)),
        p95=float(np.percentile(measurements, 95)),
        p99=float(np.percentile(measurements, 99)),
    )

def measure_power_distribution(device, samples: int = 64) -> Distribution:
    """Measure the power distribution."""
    measurements = []
    for _ in range(samples):
        power = read_power(device)
        measurements.append(power)
    return Distribution(
        mean=float(np.mean(measurements)),
        stddev=float(np.std(measurements)),
        samples=len(measurements),
        p50=float(np.percentile(measurements, 50)),
        p95=float(np.percentile(measurements, 95)),
        p99=float(np.percentile(measurements, 99)),
    )

def probe_asic(device) -> 'Result':
    """Probe an ASIC and return its capability."""
    # Measure hashrate
    hashrate = measure_hashrate_distribution(device, samples=64)
    if hashrate.mean == 0:
        return Err(ASICError.ASIC_ABSENT)

    # Measure power
    power = measure_power_distribution(device, samples=64)

    # Compute efficiency
    efficiency = Distribution(
        mean=power.mean / hashrate.mean,
        stddev=0.0,
        samples=min(power.samples, hashrate.samples),
        p50=power.p50 / hashrate.p50,
        p95=power.p95 / hashrate.p95,
        p99=power.p99 / hashrate.p99,
    )

    # Check fold capability
    fold_capable = device.firmware.supports_fold()
    max_fold_qubits = device.firmware.max_fold_qubits() if fold_capable else 0

    # Build attestation chain
    chain = build_attestation_chain(device)

    # Determine device class
    device_class = (
        DeviceClass.ASIC_QUANTUM_ARMED if fold_capable
        else DeviceClass.ASIC_CLASSIC
    )

    return Ok(ASICCapability(
        device_id=device.id,
        vendor=device.vendor,
        model=device.model,
        firmware_digest=device.firmware.digest,
        technology=device.technology,
        device_class=device_class,
        hashrate=hashrate,
        power=power,
        efficiency=efficiency,
        fold_capable=fold_capable,
        max_fold_qubits=max_fold_qubits,
        supported_kernels={
            KernelName.SHA256D_SCAN,
            KernelName.SHA256D_VERIFY,
            KernelName.SHA256D_MIDSTATE,
            KernelName.SHA256D_MERKLE,
            KernelName.FOLD_11D if fold_capable else None,
            KernelName.UNFOLD_11D if fold_capable else None,
            KernelName.ZECKENDORF_CERTIFICATE if fold_capable else None,
            KernelName.ATTEST_RESULT,
            KernelName.ATTEST_COMPOSE,
        } - {None},
        state=DeviceState.PRESENT,
        attestation_chain=chain,
    ))

# Executable invariant catalogue; tests determine each outcome.
INVARIANTS = {
    'ASIC_P1': 'No ASIC capability is returned with hashrate.mean == 0.',
    'ASIC_P2': 'Every ASIC capability has a non-empty attestation chain.',
    'ASIC_P3': 'Every ASIC capability carries the firmware digest.',
    'ASIC_P4': 'The fold capability is declared, not assumed.',
}
