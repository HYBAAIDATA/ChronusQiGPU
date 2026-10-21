"""Verifiable benchmark harness with a per-domain Lucas scale matrix.

This is an offline measurement harness. It runs one fingerprint workload through
classical and PQSC search paths, while applying the configured Lucas powers
independently to search, memory, tensor, virtual-quantum, hardware,
intelligence, verification, and schedule dimensions.

The quantum result is an exact mathematical square-root query model only. It is
never reported as QPU execution. Effective hardware quantities are mathematical
capacity metadata until a physical device run supplies evidence.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from scripts.lucas_scale_matrix import LucasScaleMatrixEngine, ScalingDomainSpec
except ImportError:  # direct execution from the scripts directory
    from lucas_scale_matrix import LucasScaleMatrixEngine, ScalingDomainSpec

SCHEMA_VERSION = "1.0.0"
COMPOSITE_VERSION = "3.0.0"
HARNESS_NAME = "verifiable-structural-search-benchmark"
HARNESS_VERSION = "1.0.0"
NONCE_WIDTH_BYTES = 8
DEFAULT_HASH_ALGORITHM = "sha256d"
SCALE_BASE_INDEX = 10
DOMAINS = (
    "search",
    "memory",
    "tensor",
    "virtual_quantum",
    "hardware",
    "intelligence",
    "coherence",
    "verification",
    "schedule",
)
# The provided Lucas ladder is the allowed power set. The matrix is deliberately
# per-domain: operators can supply another assignment without code changes.
DEFAULT_SCALE_MATRIX = {
    "search": 10,
    "memory": 7,
    "tensor": 12,
    "virtual_quantum": 15,
    "hardware": 31,
    "intelligence": 50,
    "coherence": 18,
    "verification": 20,
    "schedule": 76,
}
ALLOWED_LUCAS_POWERS = (7, 10, 12, 15, 18, 20, 31, 50, 76)


def _json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default).encode()


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(algorithm: str, value: bytes) -> bytes:
    if algorithm == "sha256d":
        return hashlib.sha256(hashlib.sha256(value).digest()).digest()
    try:
        return hashlib.new(algorithm, value).digest()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unsupported hash algorithm: {algorithm}") from exc


def lucas(n: int) -> int:
    if n < 0:
        raise ValueError("Lucas index must be non-negative")
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("Fibonacci index must be non-negative")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@dataclass(frozen=True)
class LucasPower:
    domain: str
    power: int
    value: int
    base_index: int
    base_value: int

    def scale_integer(self, base: int) -> int:
        if base < 0:
            raise ValueError("base must be non-negative")
        # Exact ceiling of base * L_power / L_10.
        return (base * self.value + self.base_value - 1) // self.base_value

    def as_dict(self) -> dict[str, int | str]:
        return {
            "domain": self.domain,
            "power": self.power,
            "lucas_value": self.value,
            "base_index": self.base_index,
            "base_value": self.base_value,
            "factor_numerator": self.value,
            "factor_denominator": self.base_value,
        }


@dataclass(frozen=True)
class LucasScaleMatrix:
    powers: tuple[tuple[str, int], ...]

    @classmethod
    def from_dict(cls, values: Optional[dict[str, int]] = None) -> "LucasScaleMatrix":
        source = dict(DEFAULT_SCALE_MATRIX if values is None else values)
        missing = set(DOMAINS) - set(source)
        extra = set(source) - set(DOMAINS)
        if missing or extra:
            raise ValueError(f"scale matrix domains mismatch: missing={missing}, extra={extra}")
        if any(not isinstance(v, int) or v not in ALLOWED_LUCAS_POWERS for v in source.values()):
            raise ValueError(f"every domain power must be one of {ALLOWED_LUCAS_POWERS}")
        return cls(tuple((domain, source[domain]) for domain in DOMAINS))

    def power(self, domain: str) -> int:
        for name, power in self.powers:
            if name == domain:
                return power
        raise KeyError(domain)

    def lucas_power(self, domain: str) -> LucasPower:
        power = self.power(domain)
        return LucasPower(domain, power, lucas(power), SCALE_BASE_INDEX, lucas(SCALE_BASE_INDEX))

    def scale_integer(self, domain: str, base: int) -> int:
        return self.lucas_power(domain).scale_integer(base)

    def as_dict(self) -> dict[str, dict[str, int | str]]:
        return {domain: self.lucas_power(domain).as_dict() for domain, _ in self.powers}

    def fingerprint(self) -> str:
        return sha256_hex(canonical_json_bytes(self.as_dict()))

    def engine(self) -> LucasScaleMatrixEngine:
        domains = {
            domain: ScalingDomainSpec(domain, power)
            for domain, power in self.powers
        }
        return LucasScaleMatrixEngine(domains)


@dataclass(frozen=True)
class ScaledDimensions:
    search_space: int
    search_budget: int
    memory_units: int
    tensor_width: int
    tensor_depth: int
    virtual_qubits: int
    virtual_state_dimension: int
    hardware_cores: int
    hardware_memory_units: int
    intelligence_budget: int
    coherence_budget: int
    verification_budget: int

    def as_dict(self) -> dict[str, int]:
        return dataclasses.asdict(self)


def derive_dimensions(
    matrix: LucasScaleMatrix,
    *,
    base_search_space: int,
    base_memory_units: int,
    base_tensor_width: int,
    base_tensor_depth: int,
    base_virtual_qubits: int,
    base_hardware_cores: int,
    base_hardware_memory_units: int,
    base_intelligence_budget: int,
    base_coherence_budget: int,
) -> ScaledDimensions:
    bases = (base_search_space, base_memory_units, base_tensor_width, base_tensor_depth,
             base_virtual_qubits, base_hardware_cores, base_hardware_memory_units,
             base_intelligence_budget, base_coherence_budget)
    if min(bases) < 1:
        raise ValueError("all base dimensions must be positive")
    q = matrix.lucas_power("virtual_quantum")
    virtual_qubits = max(1, base_virtual_qubits + q.value.bit_length() - q.base_value.bit_length())
    return ScaledDimensions(
        search_space=matrix.scale_integer("search", base_search_space),
        search_budget=matrix.scale_integer("search", base_search_space),
        memory_units=matrix.scale_integer("memory", base_memory_units),
        tensor_width=matrix.scale_integer("tensor", base_tensor_width),
        tensor_depth=matrix.scale_integer("tensor", base_tensor_depth),
        virtual_qubits=virtual_qubits,
        virtual_state_dimension=1 << virtual_qubits,
        hardware_cores=matrix.scale_integer("hardware", base_hardware_cores),
        hardware_memory_units=matrix.scale_integer("hardware", base_hardware_memory_units),
        intelligence_budget=matrix.scale_integer("intelligence", base_intelligence_budget),
        coherence_budget=matrix.scale_integer("coherence", base_coherence_budget),
        verification_budget=matrix.scale_integer("verification", base_search_space),
    )


@dataclass(frozen=True)
class WorkloadSpecification:
    workload_id: str
    seed: bytes
    target_prefix: bytes
    hash_algorithm: str
    nonce_min: int
    nonce_max: int
    scale_matrix: LucasScaleMatrix
    dimensions: ScaledDimensions
    matrix_manifest: dict[str, Any]
    matrix_engine_fingerprint: str

    @property
    def search_space(self) -> int:
        return self.nonce_max - self.nonce_min

    def public_dict(self) -> dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "seed_hex": self.seed.hex(),
            "target_prefix_hex": self.target_prefix.hex(),
            "hash_algorithm": self.hash_algorithm,
            "nonce_min": self.nonce_min,
            "nonce_max": self.nonce_max,
            "search_space": self.search_space,
            "scale_matrix": self.scale_matrix.as_dict(),
            "scale_matrix_fingerprint": self.scale_matrix.fingerprint(),
            "matrix_manifest": self.matrix_manifest,
            "matrix_engine_fingerprint": self.matrix_engine_fingerprint,
            "dimensions": self.dimensions.as_dict(),
        }

    def fingerprint(self) -> str:
        return sha256_hex(canonical_json_bytes(self.public_dict()))

    def digest_for_nonce(self, nonce: int) -> bytes:
        if not self.nonce_min <= nonce < self.nonce_max:
            raise ValueError("nonce outside workload range")
        return digest(self.hash_algorithm, self.seed + nonce.to_bytes(NONCE_WIDTH_BYTES, "big"))

    def verify_solution(self, nonce: int, digest_hex: str) -> bool:
        try:
            actual = bytes.fromhex(digest_hex)
            return actual == self.digest_for_nonce(nonce) and actual.startswith(self.target_prefix)
        except (TypeError, ValueError):
            return False


def make_workload(
    workload_id: str,
    master_seed: bytes,
    *,
    nonce_bits: int,
    target_prefix_bytes: int,
    scale_matrix: Optional[dict[str, int]] = None,
    hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
    base_memory_units: int = 1,
    base_tensor_width: int = 1,
    base_tensor_depth: int = 1,
    base_virtual_qubits: int = 1,
    base_hardware_cores: int = 1,
    base_hardware_memory_units: int = 1,
    base_intelligence_budget: int = 1,
    base_coherence_budget: int = 1,
) -> WorkloadSpecification:
    if not workload_id or len(master_seed) < 16:
        raise ValueError("workload_id and a seed of at least 16 bytes are required")
    if not 1 <= nonce_bits <= 63 or not 1 <= target_prefix_bytes <= 32:
        raise ValueError("invalid nonce_bits or target_prefix_bytes")
    digest(hash_algorithm, b"")
    matrix = LucasScaleMatrix.from_dict(scale_matrix)
    matrix_engine = matrix.engine()
    matrix_manifest = matrix_engine.generate_matrix_manifest()
    matrix_engine_fingerprint = matrix_engine.compute_fingerprint()
    base_space = 1 << nonce_bits
    dimensions = derive_dimensions(
        matrix,
        base_search_space=base_space,
        base_memory_units=base_memory_units,
        base_tensor_width=base_tensor_width,
        base_tensor_depth=base_tensor_depth,
        base_virtual_qubits=base_virtual_qubits,
        base_hardware_cores=base_hardware_cores,
        base_hardware_memory_units=base_hardware_memory_units,
        base_intelligence_budget=base_intelligence_budget,
        base_coherence_budget=base_coherence_budget,
    )
    seed = hashlib.sha256(
        bytes(master_seed) + b"|workload|" + workload_id.encode() + b"|scale|" +
        canonical_json_bytes(matrix.as_dict()) + canonical_json_bytes(dimensions.as_dict()) +
        matrix_engine_fingerprint.encode("ascii")
    ).digest()
    witness = int.from_bytes(hashlib.sha256(seed + b"|witness").digest()[:8], "big") % dimensions.search_space
    target = digest(hash_algorithm, seed + witness.to_bytes(8, "big"))[:target_prefix_bytes]
    return WorkloadSpecification(
        workload_id=workload_id,
        seed=seed,
        target_prefix=target,
        hash_algorithm=hash_algorithm,
        nonce_min=0,
        nonce_max=dimensions.search_space,
        scale_matrix=matrix,
        dimensions=dimensions,
        matrix_manifest=matrix_manifest,
        matrix_engine_fingerprint=matrix_engine_fingerprint,
    )


@dataclass(frozen=True)
class BenchmarkMetric:
    runner: str
    kind: str
    workload_fingerprint: str
    hash_algorithm: str
    scale_matrix_fingerprint: str
    scale_matrix: dict[str, dict[str, int | str]]
    matrix_engine_fingerprint: str
    matrix_manifest: dict[str, Any]
    dimensions: dict[str, int]
    trial_index: int
    nonce: Optional[int]
    digest_hex: Optional[str]
    target_prefix_hex: str
    operations: int
    wall_time_ns: Optional[int]
    normalized_cost_us_per_operation: Optional[float]
    solution_found: bool
    verified: bool
    hardware_provenance: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _metric(spec: WorkloadSpecification, *, runner: str, kind: str, trial_index: int,
            nonce: Optional[int], found_digest: Optional[bytes], operations: int,
            wall_time_ns: Optional[int], solution_found: bool, provenance: str) -> BenchmarkMetric:
    candidate = BenchmarkMetric(
        runner=runner,
        kind=kind,
        workload_fingerprint=spec.fingerprint(),
        hash_algorithm=spec.hash_algorithm,
        scale_matrix_fingerprint=spec.scale_matrix.fingerprint(),
        scale_matrix=spec.scale_matrix.as_dict(),
        matrix_engine_fingerprint=spec.matrix_engine_fingerprint,
        matrix_manifest=spec.matrix_manifest,
        dimensions=spec.dimensions.as_dict(),
        trial_index=trial_index,
        nonce=nonce,
        digest_hex=found_digest.hex() if found_digest is not None else None,
        target_prefix_hex=spec.target_prefix.hex(),
        operations=operations,
        wall_time_ns=wall_time_ns,
        normalized_cost_us_per_operation=(wall_time_ns / operations / 1000.0)
        if wall_time_ns is not None and operations else None,
        solution_found=solution_found,
        verified=False,
        hardware_provenance=provenance,
    )
    return dataclasses.replace(candidate, verified=verify_metric(spec, candidate))


def run_classical(spec: WorkloadSpecification, trial_index: int = 0) -> BenchmarkMetric:
    start = time.perf_counter_ns()
    operations = 0
    for nonce in range(spec.nonce_min, spec.nonce_max):
        operations += 1
        candidate = spec.digest_for_nonce(nonce)
        if candidate.startswith(spec.target_prefix):
            return _metric(spec, runner="classical", kind="measured", trial_index=trial_index,
                           nonce=nonce, found_digest=candidate, operations=operations,
                           wall_time_ns=time.perf_counter_ns() - start, solution_found=True,
                           provenance="CPU_NATIVE_MEASURED")
    return _metric(spec, runner="classical", kind="measured", trial_index=trial_index,
                   nonce=None, found_digest=None, operations=operations,
                   wall_time_ns=time.perf_counter_ns() - start, solution_found=False,
                   provenance="CPU_NATIVE_MEASURED")


def _schedule_stride(spec: WorkloadSpecification) -> tuple[int, int]:
    schedule = spec.scale_matrix.lucas_power("schedule")
    stride = schedule.value
    while math.gcd(stride, spec.search_space) != 1:
        stride += 1
    return fibonacci(schedule.power) % spec.search_space, stride


def pqsc_nonce_order(spec: WorkloadSpecification) -> Iterable[int]:
    start, stride = _schedule_stride(spec)
    for offset in range(spec.search_space):
        yield spec.nonce_min + ((start + offset * stride) % spec.search_space)


def run_pqsc(spec: WorkloadSpecification, trial_index: int = 0) -> BenchmarkMetric:
    start_time = time.perf_counter_ns()
    operations = 0
    for nonce in pqsc_nonce_order(spec):
        operations += 1
        candidate = spec.digest_for_nonce(nonce)
        if candidate.startswith(spec.target_prefix):
            return _metric(spec, runner="pqsc", kind="measured", trial_index=trial_index,
                           nonce=nonce, found_digest=candidate, operations=operations,
                           wall_time_ns=time.perf_counter_ns() - start_time, solution_found=True,
                           provenance="CPU_NATIVE_MEASURED")
    return _metric(spec, runner="pqsc", kind="measured", trial_index=trial_index,
                   nonce=None, found_digest=None, operations=operations,
                   wall_time_ns=time.perf_counter_ns() - start_time, solution_found=False,
                   provenance="CPU_NATIVE_MEASURED")


def quadratic_query_bound(search_space: int) -> int:
    if search_space < 1:
        raise ValueError("search_space must be positive")
    root = math.isqrt(search_space)
    return root if root * root == search_space else root + 1


def run_quantum_model(spec: WorkloadSpecification, trial_index: int = 0) -> BenchmarkMetric:
    return _metric(spec, runner="quantum_model", kind="modeled", trial_index=trial_index,
                   nonce=None, found_digest=None, operations=quadratic_query_bound(spec.search_space),
                   wall_time_ns=None, solution_found=False,
                   provenance="UNPROVEN_NO_QPU_BACKEND")


def verify_metric(spec: WorkloadSpecification, metric: BenchmarkMetric) -> bool:
    if metric.workload_fingerprint != spec.fingerprint():
        return False
    if metric.hash_algorithm != spec.hash_algorithm:
        return False
    if metric.scale_matrix_fingerprint != spec.scale_matrix.fingerprint():
        return False
    if metric.scale_matrix != spec.scale_matrix.as_dict() or metric.dimensions != spec.dimensions.as_dict():
        return False
    if metric.matrix_engine_fingerprint != spec.matrix_engine_fingerprint:
        return False
    if metric.matrix_manifest != spec.matrix_manifest:
        return False
    if not spec.scale_matrix.engine().verify_workload_fingerprint(
        spec.matrix_manifest, spec.matrix_engine_fingerprint
    ):
        return False
    if metric.target_prefix_hex != spec.target_prefix.hex():
        return False
    if metric.kind == "modeled":
        return metric.operations == quadratic_query_bound(spec.search_space)
    if metric.kind != "measured" or not metric.solution_found:
        return False
    return metric.nonce is not None and metric.digest_hex is not None and metric.operations > 0 and spec.verify_solution(metric.nonce, metric.digest_hex)


def capture_environment() -> dict[str, Any]:
    return {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "source_sha256": sha256_hex(Path(__file__).read_bytes()),
    }


def _summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {"n": len(values), "min": min(values), "median": ordered[len(ordered) // 2], "max": max(values)}


def composite_fingerprint(workload_fp: str, matrix_fp: str) -> str:
    payload = {
        "workload_fingerprint_sha256": workload_fp,
        "matrix_fingerprint_sha256": matrix_fp,
        "schema_version": SCHEMA_VERSION,
        "composite_version": COMPOSITE_VERSION,
    }
    return sha256_hex(canonical_json_bytes(payload))


class BenchmarkHarness:
    def __init__(self, master_seed: bytes, *, nonce_bits: int, target_prefix_bytes: int,
                 scale_matrix: Optional[dict[str, int]] = None, trials: int = 3,
                 base_memory_units: int = 1, base_tensor_width: int = 1,
                 base_tensor_depth: int = 1, base_virtual_qubits: int = 1,
                 base_hardware_cores: int = 1, base_hardware_memory_units: int = 1,
                 base_intelligence_budget: int = 1, base_coherence_budget: int = 1) -> None:
        if trials < 1:
            raise ValueError("trials must be positive")
        self.master_seed = bytes(master_seed)
        self.nonce_bits = nonce_bits
        self.target_prefix_bytes = target_prefix_bytes
        self.scale_matrix = scale_matrix
        self.trials = trials
        self.dimension_args = {
            "base_memory_units": base_memory_units,
            "base_tensor_width": base_tensor_width,
            "base_tensor_depth": base_tensor_depth,
            "base_virtual_qubits": base_virtual_qubits,
            "base_hardware_cores": base_hardware_cores,
            "base_hardware_memory_units": base_hardware_memory_units,
            "base_intelligence_budget": base_intelligence_budget,
            "base_coherence_budget": base_coherence_budget,
        }

    def run(self, workload_id: str) -> dict[str, Any]:
        spec = make_workload(workload_id, self.master_seed, nonce_bits=self.nonce_bits,
                             target_prefix_bytes=self.target_prefix_bytes,
                             scale_matrix=self.scale_matrix, **self.dimension_args)
        results: list[BenchmarkMetric] = []
        for trial in range(self.trials):
            results.extend((run_classical(spec, trial), run_pqsc(spec, trial), run_quantum_model(spec, trial)))
        by_runner: dict[str, list[BenchmarkMetric]] = {}
        for result in results:
            by_runner.setdefault(result.runner, []).append(result)
        summary = {}
        for runner, group in by_runner.items():
            summary[runner] = {
                "kind": group[0].kind,
                "operations": _summary([float(r.operations) for r in group]),
                "wall_time_seconds": _summary([r.wall_time_ns / 1e9 for r in group if r.wall_time_ns]),
                "normalized_cost_us_per_operation": _summary([r.normalized_cost_us_per_operation for r in group if r.normalized_cost_us_per_operation is not None]),
                "all_verified": all(r.verified for r in group),
                "hardware_provenance": sorted({r.hardware_provenance for r in group}),
                "scale_matrix": spec.scale_matrix.as_dict(),
                "dimensions": spec.dimensions.as_dict(),
            }
        workload_public = spec.public_dict()
        workload_public["fingerprint_sha256"] = spec.fingerprint()
        matrix_fp = spec.matrix_engine_fingerprint
        artifact: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "composite_version": COMPOSITE_VERSION,
            "harness": {"name": HARNESS_NAME, "version": HARNESS_VERSION},
            "environment": capture_environment(),
            "master_seed_hex": self.master_seed.hex(),
            "configuration": {"trials": self.trials, "nonce_bits": self.nonce_bits,
                              "target_prefix_bytes": self.target_prefix_bytes,
                              "hash_algorithm": spec.hash_algorithm,
                              "cost_unit": "microseconds_per_executed_hash"},
            "workload": workload_public,
            "matrix_manifest": spec.matrix_manifest,
            "fingerprints": {
                "workload_sha256": spec.fingerprint(),
                "matrix_sha256": matrix_fp,
                "composite_sha256": composite_fingerprint(spec.fingerprint(), matrix_fp),
            },
            "results": [r.to_dict() for r in results],
            "verification": {"all_verified": all(r.verified for r in results), "quantum_hardware_executed": False},
            "summary": summary,
        }
        artifact["artifact_sha256"] = sha256_hex(canonical_json_bytes(artifact))
        return artifact


def verify_artifact(artifact: dict[str, Any]) -> bool:
    claimed = artifact.get("artifact_sha256")
    if not isinstance(claimed, str):
        return False
    body = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    return sha256_hex(canonical_json_bytes(body)) == claimed


def evaluate_targets(artifact: dict[str, Any], target_vector: dict[str, float], *, tolerance: float = 0.0) -> dict[str, Any]:
    if not verify_artifact(artifact):
        return {"status": "FAIL_ARTIFACT_TAMPERED"}
    if not artifact["verification"]["all_verified"]:
        return {"status": "FAIL_INVALID_SOLUTIONS"}
    measured = {}
    for runner in ("classical", "pqsc", "quantum_model"):
        measured[runner] = artifact["summary"].get(runner, {}).get("normalized_cost_us_per_operation", {}).get("median")
    result = {"status": "UNPROVEN_TARGETS_NOT_PROVIDED", "measured_costs": measured,
              "target_vector": dict(target_vector), "quantum_status": "UNPROVEN_NO_QPU_BACKEND"}
    if "classical_anchor" not in target_vector or "pqsc" not in target_vector:
        return result
    classical, pqsc = measured["classical"], measured["pqsc"]
    if classical is None or pqsc is None or classical <= 0:
        result["status"] = "FAIL_INVALID_SOLUTIONS"
        return result
    relative = {"classical": float(target_vector["classical_anchor"]),
                "pqsc": pqsc / classical * float(target_vector["classical_anchor"]),
                "quantum_model": None}
    result["relative_cost_units"] = relative
    result["pqsc_target_met"] = relative["pqsc"] <= float(target_vector["pqsc"]) + tolerance
    result["status"] = "PARTIAL_PASS_QUANTUM_UNPROVEN" if result["pqsc_target_met"] else "FAIL_COST_TARGET_NOT_MET"
    return result


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload-id", required=True)
    parser.add_argument("--seed-hex", required=True)
    parser.add_argument("--nonce-bits", type=int, required=True)
    parser.add_argument("--target-bytes", type=int, required=True)
    parser.add_argument("--scale-matrix-json")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--targets-json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    matrix_config = json.loads(Path(args.scale_matrix_json).read_text()) if args.scale_matrix_json else None
    matrix = matrix_config
    if matrix_config and "domains" in matrix_config:
        matrix = {domain: matrix_config["domains"][domain]["recurrence_index"] for domain in DOMAINS}
    artifact = BenchmarkHarness(bytes.fromhex(args.seed_hex), nonce_bits=args.nonce_bits,
                                target_prefix_bytes=args.target_bytes, scale_matrix=matrix,
                                trials=args.trials).run(args.workload_id)
    if args.targets_json:
        artifact["target_evaluation"] = evaluate_targets(artifact, json.loads(Path(args.targets_json).read_text()))
        artifact.pop("artifact_sha256", None)
        artifact["artifact_sha256"] = sha256_hex(canonical_json_bytes(artifact))
    Path(args.output).write_text(json.dumps(artifact, indent=2, sort_keys=True))
    print(json.dumps({"output": args.output, "artifact_sha256": artifact["artifact_sha256"]}))
    return 0 if artifact["verification"]["all_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
