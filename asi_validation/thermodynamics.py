"""Physical energy collection for validation Domains T1-T3.

Only cumulative hardware energy counters are accepted.  Power estimates,
synthetic readings, and missing sensors fail closed and cannot become evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, Sequence


class EnergyCounter(Protocol):
    name: str
    max_joules: float | None

    def read_joules(self) -> float: ...


@dataclass(frozen=True)
class TaskEnergySample:
    trial: int
    elapsed_seconds: float
    joules: float
    sensor: str
    return_code: int
    valid: bool
    failure_reason: str | None = None


class RaplCounter:
    """Linux Intel RAPL cumulative package-energy counter."""

    def __init__(self, energy_path: Path, max_range_path: Path) -> None:
        self.energy_path = energy_path
        self.max_range_path = max_range_path
        self.name = f"rapl:{energy_path.parent.name}"
        self.max_joules = self._read_number(max_range_path) / 1_000_000

    @staticmethod
    def _read_number(path: Path) -> float:
        value = float(path.read_text(encoding="utf-8").strip())
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid cumulative energy value in {path}")
        return value

    def read_joules(self) -> float:
        return self._read_number(self.energy_path) / 1_000_000

    @classmethod
    def discover(cls, root: Path = Path("/sys/class/powercap")) -> list[RaplCounter]:
        counters: list[RaplCounter] = []
        for energy_path in sorted(root.glob("intel-rapl*/energy_uj")):
            maximum = energy_path.with_name("max_energy_range_uj")
            if maximum.is_file():
                counters.append(cls(energy_path, maximum))
        return counters


class NvidiaSmiCounter:
    """NVIDIA cumulative board-energy counter exposed by nvidia-smi/NVML."""

    max_joules = None

    def __init__(self, gpu_index: int = 0, executable: str = "nvidia-smi") -> None:
        self.gpu_index = gpu_index
        self.executable = executable
        self.name = f"nvml:gpu-{gpu_index}"

    def read_joules(self) -> float:
        completed = subprocess.run(
            [self.executable, f"--id={self.gpu_index}", "--query-gpu=total_energy_consumption", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
        )
        millijoules = float(completed.stdout.strip().splitlines()[0])
        if not math.isfinite(millijoules) or millijoules < 0:
            raise ValueError("NVML returned an invalid cumulative energy value")
        return millijoules / 1_000


def counter_delta(start: float, end: float, maximum: float | None) -> float:
    """Calculate monotonic consumption, accounting for one counter wrap."""
    if not all(math.isfinite(value) and value >= 0 for value in (start, end)):
        raise ValueError("energy readings must be finite and non-negative")
    if end >= start:
        return end - start
    if maximum is None or maximum <= start:
        raise ValueError("counter decreased without a valid wrap range")
    return maximum - start + end


def measure_command(command: Sequence[str], counter: EnergyCounter, *, trials: int = 1) -> list[TaskEnergySample]:
    if not command:
        raise ValueError("command must not be empty")
    if trials < 1:
        raise ValueError("trials must be at least one")
    samples: list[TaskEnergySample] = []
    for trial in range(1, trials + 1):
        try:
            start_energy = counter.read_joules()
            started = time.perf_counter()
            completed = subprocess.run(list(command), check=False)
            elapsed = time.perf_counter() - started
            joules = counter_delta(start_energy, counter.read_joules(), counter.max_joules)
            valid = completed.returncode == 0 and joules > 0
            reason = None if valid else "COMMAND_FAILED" if completed.returncode else "ZERO_ENERGY_DELTA"
            samples.append(TaskEnergySample(trial, elapsed, joules, counter.name, completed.returncode, valid, reason))
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
            samples.append(TaskEnergySample(trial, 0.0, 0.0, counter.name, -1, False, f"SENSOR_ERROR:{type(error).__name__}"))
    return samples


def protocol_evidence(samples: Sequence[TaskEnergySample], classical_joules_per_task: float) -> dict[str, dict[str, float | bool]]:
    """Produce T1/T3 observations; incomplete physical instrumentation stays false."""
    if not samples or classical_joules_per_task <= 0 or not all(sample.valid for sample in samples):
        return {}
    values = [sample.joules for sample in samples]
    mean = statistics.fmean(values)
    cv = statistics.pstdev(values) / mean * 100 if len(values) > 1 else 0.0
    sensor_names = {sample.sensor.split(":", 1)[0] for sample in samples}
    monitoring: dict[str, float | bool] = {
        "component_meter_present": bool(sensor_names & {"rapl", "nvml"}),
        "continuous_samples": len(samples),
        "energy_integrated": True,
    }
    if "pdu" in sensor_names:
        monitoring["external_meter_present"] = True
        monitoring["pdu_meter_present"] = True
    return {
        "T1_ENERGY": {
            "energy_ratio_vs_classical": mean / classical_joules_per_task,
            "energy_cv_pct": cv,
            "runs": len(samples),
        },
        "T3_MONITORING": monitoring,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect physical joules per task with fail-closed RAPL telemetry")
    parser.add_argument("--rapl-root", type=Path, default=Path("/sys/class/powercap"))
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--classical-joules-per-task", type=float, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    counters = RaplCounter.discover(args.rapl_root)
    if not counters:
        report = {"schema_version": 1, "status": "NOT_RUN", "reason": "RAPL_SENSOR_UNAVAILABLE", "samples": [], "evidence": {}}
        exit_code = 2
    else:
        samples = measure_command(command, counters[0], trials=args.trials)
        evidence = protocol_evidence(samples, args.classical_joules_per_task)
        report = {"schema_version": 1, "status": "MEASURED" if evidence else "INVALID", "samples": [asdict(sample) for sample in samples], "evidence": evidence}
        exit_code = 0 if evidence else 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
