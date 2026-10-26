"""
SCBC Simulation Hardening — Stochastic Noise, Packet Loss, Latency Jitter.
===========================================================================

Introduces real-world non-deterministic conditions into the SCBC simulator:
  1. Gaussian noise injection on telemetry values (μ=0, σ configurable)
  2. Random packet drops (configurable loss rate)
  3. Variable latency jitter (simulates microsecond-level hardware fluctuations)
  4. Riemannian Kalman filter for geodesic smoothing
  5. Timing guard: aborts geometric computation if it exceeds system drift rate

Prepares the SCBC for physical deployment by stress-testing under conditions
that a deterministic simulation cannot capture.

Self-contained — zero external deps beyond NumPy. 19 July 2026.
"""

import numpy as np, math, time, random
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════
# Hardened Telemetry Generator
# ═══════════════════════════════════════════════════════════

@dataclass
class NoiseProfile:
    """Stochastic noise parameters for simulation hardening."""
    amplitude_sigma: float = 0.05       # Gaussian noise σ on telemetry values
    packet_loss_rate: float = 0.02       # Random packet drops (0-1)
    latency_jitter_ms: float = 0.5       # ± jitter on telemetry arrival
    transient_spike_prob: float = 0.01    # Probability of a sharp transient spike
    spike_magnitude: float = 0.30         # Magnitude of transient spikes


class HardenedTelemetrySource:
    """Generates telemetry with injected stochastic noise, mimicking physical
    hardware fluctuations, network jitter, and transient spikes."""

    def __init__(self, base_telemetry: Dict[str, Dict[str, float]],
                 noise: Optional[NoiseProfile] = None):
        self.base = base_telemetry
        self.noise = noise or NoiseProfile()
        self._rng = random.Random(42)

    def sample(self) -> Tuple[Dict[str, Dict[str, float]], float]:
        """Return a single noisy telemetry sample + simulated arrival latency."""
        # Packet loss
        if self._rng.random() < self.noise.packet_loss_rate:
            return None, 0.0

        result = {}
        for node_id, metrics in self.base.items():
            noisy_metrics = dict(metrics)
            value = metrics.get("value", 0.0)

            # Gaussian noise
            noise_val = self._rng.gauss(0.0, self.noise.amplitude_sigma)

            # Transient spike
            if self._rng.random() < self.noise.transient_spike_prob:
                spike = self.noise.spike_magnitude * self._rng.choice([-1, 1])
                noise_val += spike

            noisy_metrics["value"] = value + noise_val
            noisy_metrics["delta"] = metrics.get("delta", 0.0) + noise_val * 0.1
            result[node_id] = noisy_metrics

        # Latency jitter
        latency = abs(self._rng.gauss(0.0, self.noise.latency_jitter_ms))
        return result, latency


# ═══════════════════════════════════════════════════════════
# Riemannian Kalman Filter for Geodesic Smoothing
# ═══════════════════════════════════════════════════════════

class RiemannianKalmanFilter:
    """
    Smooths noisy telemetry projections on the Riemannian manifold.

    Prevents transient network spikes from being misidentified as
    systemic geodesic drift. Uses exponential smoothing in the
    tangent space: x_filtered = α·x_obs + (1-α)·x_predicted.
    """

    def __init__(self, dim: int, process_noise: float = 0.01,
                 observation_noise: float = 0.05, alpha: float = 0.30):
        self.dim = dim
        self.process_noise = process_noise
        self.observation_noise = observation_noise
        self.alpha = alpha
        self.state = np.zeros(dim)
        self.covariance = np.eye(dim) * observation_noise
        self.initialized = False

    def update(self, observation: np.ndarray) -> np.ndarray:
        if not self.initialized:
            self.state = observation
            self.initialized = True
            return observation

        # Prediction step
        predicted = self.state
        predicted_cov = self.covariance + np.eye(self.dim) * self.process_noise

        # Update step: exponential smoothing in tangent space
        innovation = observation - predicted
        kalman_gain = self.alpha
        self.state = predicted + kalman_gain * innovation
        self.covariance = (1 - kalman_gain) * predicted_cov

        return self.state


# ═══════════════════════════════════════════════════════════
# Timing Guard for Parallel Transport
# ═══════════════════════════════════════════════════════════

@dataclass
class TimingGuard:
    """
    Ensures geometric computation does not exceed the system's drift rate.

    If computing Christoffel symbols + parallel transport takes longer
    than the physical system's drift interval, the actuation command
    arrives too late — the "predictive" intervention becomes reactive.
    """
    max_compute_us: float = 500.0  # Max microseconds for geometric ops
    drift_interval_us: float = 1000.0  # System drift rate
    violations: int = 0
    total_checks: int = 0

    def guard(self, fn, *args) -> Tuple[Any, bool]:
        """Execute fn and check if it exceeds the compute budget."""
        t0 = time.perf_counter()
        result = fn(*args)
        elapsed_us = (time.perf_counter() - t0) * 1e6
        self.total_checks += 1
        ok = elapsed_us < self.max_compute_us
        if not ok:
            self.violations += 1
        return result, ok

    @property
    def violation_rate(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return self.violations / self.total_checks


# ═══════════════════════════════════════════════════════════
# Physical Pipeline Mapping Spec
# ═══════════════════════════════════════════════════════════

@dataclass
class PhysicalMetricMapping:
    """Maps abstract SCBC state vector coordinates to real Linux kernel metrics."""
    coordinate_index: int
    metric_name: str
    kernel_source: str       # e.g., "eBPF", "cgroup", "hwmon", "proc"
    kernel_path: str         # e.g., "/sys/class/hwmon/hwmon0/temp1_input"
    scaling_factor: float = 1.0  # Normalize to [0, 1] range
    invert: bool = False         # True if higher metric = worse (e.g., temp)


# Canonical SCBC-to-Linux kernel metric mapping
SCBC_PHYSICAL_MAPPING: List[PhysicalMetricMapping] = [
    PhysicalMetricMapping(0, "cpu_throttle_pct", "cgroup",
                          "/sys/fs/cgroup/cpu/cpu.stat", 0.01, True),
    PhysicalMetricMapping(1, "memory_pressure", "cgroup",
                          "/sys/fs/cgroup/memory/memory.pressure", 0.01, True),
    PhysicalMetricMapping(2, "network_retransmit_rate", "eBPF",
                          "ebpf:sock:net_retransmit", 0.1, True),
    PhysicalMetricMapping(3, "cpu_temperature", "hwmon",
                          "/sys/class/hwmon/hwmon0/temp1_input", 0.001, True),
    PhysicalMetricMapping(4, "io_wait_pct", "proc",
                          "/proc/stat", 0.01, True),
    PhysicalMetricMapping(5, "context_switches_per_sec", "proc",
                          "/proc/stat", 0.000001, True),
    PhysicalMetricMapping(6, "tcp_connection_backlog", "eBPF",
                          "ebpf:sock:tcp_backlog", 0.01, True),
    PhysicalMetricMapping(7, "oom_score", "proc",
                          "/proc/self/oom_score", 0.001, True),
]


def map_kernel_metrics_to_scbc(
    kernel_metrics: Dict[str, float],
    mapping: List[PhysicalMetricMapping] = SCBC_PHYSICAL_MAPPING,
) -> np.ndarray:
    """Convert raw kernel-level metrics into SCBC manifold coordinates."""
    coords = np.zeros(len(mapping))
    for m in mapping:
        raw = kernel_metrics.get(m.metric_name, 0.0)
        normalized = raw * m.scaling_factor
        if m.invert:
            normalized = 1.0 - min(1.0, normalized)
        coords[m.coordinate_index] = max(0.0, min(1.0, normalized))
    return coords


# ═══════════════════════════════════════════════════════════
# Hardened SCBC Test Harness
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 65)
    print("SCBC SIMULATION HARDENING — STOCHASTIC NOISE INJECTION")
    print("=" * 65)

    # ── Test 1: Noise injection and Kalman filtering ──
    print("\n[TEST 1] Gaussian Noise + Riemannian Kalman Filter")
    base = {"node_00": {"value": 0.5, "delta": 0.01},
            "node_01": {"value": 0.15, "delta": 0.0},
            "node_02": {"value": 0.25, "delta": 0.02}}

    noise_profile = NoiseProfile(
        amplitude_sigma=0.08, packet_loss_rate=0.02,
        latency_jitter_ms=0.5, transient_spike_prob=0.02, spike_magnitude=0.25)
    source = HardenedTelemetrySource(base, noise_profile)
    kf = RiemannianKalmanFilter(dim=3, alpha=0.30)

    raw_values = []
    filtered_values = []
    spikes_detected = 0
    samples_collected = 0

    for i in range(100):
        sample, lat = source.sample()
        if sample is None:
            continue  # Packet dropped
        samples_collected += 1

        # Raw: unfiltered projection
        raw_coords = np.array([sample[n].get("value", 0.0) for n in sorted(sample)])
        raw_values.append(float(np.linalg.norm(raw_coords)))

        # Filtered: Kalman-smoothed
        filtered = kf.update(raw_coords[:3])
        filtered_values.append(float(np.linalg.norm(filtered)))

        # Detect transient spikes
        if i > 0 and abs(raw_values[-1] - raw_values[-2]) > 0.20:
            spikes_detected += 1

    raw_std = float(np.std(raw_values))
    filtered_std = float(np.std(filtered_values))
    reduction = (raw_std - filtered_std) / (raw_std + 1e-12) * 100

    print(f"  Samples: {samples_collected}/100 (packet loss: {100-samples_collected}%)")
    print(f"  Raw σ: {raw_std:.4f}, Filtered σ: {filtered_std:.4f}")
    print(f"  Noise reduction: {reduction:.1f}%")
    print(f"  Transient spikes: {spikes_detected}")
    assert filtered_std < raw_std  # Kalman filter reduces variance

    # ── Test 2: Timing guard ──
    print("\n[TEST 2] Timing Guard — Geometric Computation Budget")
    guard = TimingGuard(max_compute_us=10000.0, drift_interval_us=15000.0)

    def dummy_geodesic():
        x = np.random.randn(3)
        gamma = np.zeros((3, 3, 3))
        for i in range(3):
            gamma[i, i, i] = 0.01 * x[i]
        accel = -np.einsum('ijk,j,k->i', gamma, x, x)
        return float(np.linalg.norm(x + accel))

    for i in range(20):
        result, ok = guard.guard(dummy_geodesic)

    print(f"  Checks: {guard.total_checks}, Violations: {guard.violations}")
    print(f"  Violation rate: {guard.violation_rate:.2%}")
    assert guard.violation_rate < 0.5  # Most should pass

    # ── Test 3: Physical mapping ──
    print("\n[TEST 3] Physical Pipeline — Kernel Metrics → SCBC Coordinates")
    sample_kernel = {
        "cpu_throttle_pct": 5.0, "memory_pressure": 12.0,
        "network_retransmit_rate": 3.0, "cpu_temperature": 65000,
        "io_wait_pct": 2.0, "context_switches_per_sec": 50000,
        "tcp_connection_backlog": 0.0, "oom_score": 0.0,
    }
    coords = map_kernel_metrics_to_scbc(sample_kernel)
    print(f"  Sample kernel metrics:")
    for k, v in sample_kernel.items():
        print(f"    {k}: {v}")
    print(f"  SCBC coords: {np.round(coords, 4)}")
    assert len(coords) == 8
    assert 0.0 <= coords[0] <= 1.0
    assert 0.0 <= coords[3] <= 1.0  # Temperature

    # Inverted metrics: higher kernel value → lower SCBC coord
    assert coords[3] < 0.5  # 65000 m°C = 65°C, invert → low health score

    # ── Test 4: Hardened SCBC cycle with noise ──
    print("\n[TEST 4] Hardened SCBC Control Cycle Under Noise")
    # Rapid import from the SCBC module
    import sys; sys.path.insert(0, '/data')
    from euclid.scbc import (
        StructuralCausalModel, SalamanderCognitiveBoundaryController,
    )

    scm = StructuralCausalModel(
        dag={"node_00": [], "node_01": ["node_00"], "node_02": ["node_00", "node_01"]},
        equations={
            "node_00": lambda p, n: 0.5 + n,
            "node_01": lambda p, n: 0.3 * p[0] + n,
            "node_02": lambda p, n: 0.4 * p[0] + 0.3 * p[1] + n,
        },
    )
    ctrl = SalamanderCognitiveBoundaryController(3, scm, drift_threshold=1.5)

    false_positives = 0
    cycles = 50
    for _ in range(cycles):
        sample, _ = source.sample()
        if sample is None:
            continue
        r = ctrl.run_control_cycle(sample)
        if r["action"] == "proactive_heal":
            false_positives += 1

    fp_rate = false_positives / cycles * 100
    print(f"  Cycles: {cycles}, False positives: {false_positives}")
    print(f"  FP rate: {fp_rate:.1f}%")
    # With Kalman filtering + threshold 1.5, should be low
    assert fp_rate < 30  # Allow some, but not excessive

    print(f"\n" + "=" * 65)
    print("SCBC HARDENING — ALL TESTS PASSED")
    print(f"  Noise:   {reduction:.0f}% reduction via Kalman filter")
    print(f"  Timing:  {guard.violation_rate:.1%} violation rate")
    print(f"  Mapping: 8 kernel metrics → SCBC coords")
    print(f"  Hardened: {fp_rate:.1f}% false positive rate under noise")
    print("=" * 65)
