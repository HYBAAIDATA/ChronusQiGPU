"""Fail-closed OpenCL conformance gate for any device Chronus executes on.

The Intel UHD 620 evidence run is one instance of this suite, not a bespoke
script: the same identity negative, the same certified float32 operations, the
same non-tile-aligned boundary shapes, the same dtype rejection and the same
tolerance apply to any OpenCL implementation Chronus is asked to trust. A gate
that can bind the wrong device is not a gate, so the identity negative runs
first and a single unbound device fails the whole run.

Nothing here claims performance beyond the exact workload executed: device time
comes from the OpenCL command queue, wall time from the host clock, and every
number is derived from the run that produced it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

import numpy as np

SCHEMA = "chronus-opencl-conformance-v1"

#: Requested identity that must be refused rather than silently substituted.
NEGATIVE_DEVICE = "NONEXISTENT-CHRONUS-GPU"

#: Set in the gate's own subprocesses so a nested gate does not recurse.
CHILD_MARKER = "CHRONUS_CONFORMANCE_CHILD"

#: Software tests that must pass before hardware evidence means anything.
SOFTWARE_TEST_TARGETS = (
    "chronus/tests/test_chronus_tensor_compute.py",
    "chronus/tests/test_chronus_igpu_runtime.py",
)

_PASS = "PASS"
_FAIL = "FAIL"

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, text: str) -> str:
    """Write text byte-exactly and return the digest of what is on disk.

    Newline translation is disabled on purpose: a digest taken over the string
    while the file was written as CRLF would not verify, and the whole point of
    the manifest is that a reader can re-check it.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return _sha256(path.read_bytes())


def _array_digest(array: np.ndarray) -> str:
    return _sha256(np.ascontiguousarray(array).tobytes())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class GateCheck:
    """One gate assertion and the evidence that decided it."""

    name: str
    status: str
    detail: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == _PASS

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateResult:
    """Verdict of one conformance run, bound to its evidence by digest."""

    target: str
    status: str
    device: Mapping[str, Any]
    checks: tuple[GateCheck, ...]
    artifact_dir: str = ""
    evidence_files: Mapping[str, str] = field(default_factory=dict)
    hash_chain: str = ""
    manifest_sha256: str = ""

    @property
    def passed(self) -> bool:
        """True only when every check passed; an absent check is not a pass."""
        return bool(self.checks) and all(check.passed for check in self.checks)

    def check(self, name: str) -> GateCheck | None:
        for item in self.checks:
            if item.name == name:
                return item
        return None

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks if not check.passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "target": self.target,
            "status": self.status,
            "passed": self.passed,
            "device": dict(self.device),
            "checks": [check.as_dict() for check in self.checks],
            "failures": list(self.failures),
            "artifact_dir": self.artifact_dir,
            "evidence_files": dict(self.evidence_files),
            "hash_chain": self.hash_chain,
            "manifest_sha256": self.manifest_sha256,
        }


class OpenCLConformanceSuite:
    """The gate every OpenCL device must pass before Chronus executes on it.

    ``probe_fn``, ``runtime_factory``, ``report_fn`` and ``negative_runner`` are
    injection points: the suite's own logic is exercised without a GPU, so a
    change to the gate is testable on any host while the evidence it produces is
    only ever taken from a real device.
    """

    required_ops: tuple[str, ...] = ("matmul", "add", "scale", "kron", "hadamard")
    #: (m, k, n) matmul shapes. None is tile-aligned at 16x16 on purpose: those
    #: are where a naive local-memory kernel writes out of bounds.
    boundary_shapes: tuple[tuple[int, int, int], ...] = (
        (31, 37, 29),
        (7, 13, 9),
        (17, 33, 19),
        (63, 65, 67),
        (1, 1, 1),
        (256, 128, 256),
    )
    elementwise_shapes: tuple[tuple[int, ...], ...] = (
        (47, 53),
        (41, 37),
        (29, 31),
        (1, 1),
        (256, 256),
    )
    dtypes: tuple[str, ...] = ("float32",)
    rejected_dtypes: tuple[str, ...] = ("float64",)
    rtol: float = 1e-4
    atol: float = 1e-5
    timing_samples: int = 10
    device_env_var: str = "CHRONUS_OPENCL_DEVICE"
    platform_env_var: str = "CHRONUS_OPENCL_PLATFORM"

    def __init__(
        self,
        target: str = "chronus",
        artifact_dir: str | os.PathLike[str] = "artifacts/chronus",
        seed: int = 20261002,
        software_tests: bool = True,
        findings: Sequence[Mapping[str, Any]] = (),
        probe_fn: Callable[[], Any] | None = None,
        runtime_factory: Callable[[], Any] | None = None,
        report_fn: Callable[[], Mapping[str, Any]] | None = None,
        negative_runner: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        self.target = target
        self.artifact_dir = Path(artifact_dir)
        self.seed = int(seed)
        self.software_tests = bool(software_tests)
        self.findings = list(findings)
        self._probe_fn = probe_fn
        self._runtime_factory = runtime_factory
        self._report_fn = report_fn
        self._negative_runner = negative_runner
        self._payloads: dict[str, str] = {}

    # ---- injected seams -------------------------------------------------
    def probe(self) -> Any:
        if self._probe_fn is not None:
            return self._probe_fn()
        from chronus.tensor_compute import probe

        return probe()

    def runtime(self) -> Any:
        if self._runtime_factory is not None:
            return self._runtime_factory()
        from chronus.tensor_compute import get_runtime

        return get_runtime()

    def report(self) -> Mapping[str, Any]:
        if self._report_fn is not None:
            return self._report_fn()
        from chronus.report import report

        return report()

    # ---- payloads -------------------------------------------------------
    def _emit(self, name: str, text: str) -> None:
        self._payloads[name] = text

    def _emit_json(self, name: str, payload: Any) -> None:
        self._emit(name, json.dumps(payload, indent=2, default=str) + "\n")

    def _rng(self, offset: int) -> np.random.Generator:
        return np.random.default_rng(self.seed + offset)

    def _compare(self, result: np.ndarray, expected: np.ndarray) -> tuple[bool, float]:
        ok = bool(np.allclose(result, expected, rtol=self.rtol, atol=self.atol))
        return ok, float(np.max(np.abs(result - expected)))

    # ---- workloads ------------------------------------------------------
    def _matmul_case(self, runtime: Any, m: int, k: int, n: int, offset: int) -> dict[str, Any]:
        rng = self._rng(offset)
        a = rng.random((m, k), dtype=np.float32)
        b = rng.random((k, n), dtype=np.float32)
        expected = np.matmul(a, b).astype(np.float32)
        result, evidence = runtime.execute_with_evidence(
            "matmul", [a, b], [a.shape, b.shape], expected.shape
        )
        ok, max_abs = self._compare(result, expected)
        return {
            "case": "matmul",
            "op": "matmul",
            "shape_a": (m, k),
            "shape_b": (k, n),
            "shape_c": (m, n),
            "tile_aligned": m % 16 == 0 and k % 16 == 0 and n % 16 == 0,
            "seed": self.seed + offset,
            "digest_a": _array_digest(a),
            "digest_b": _array_digest(b),
            "digest_expected": _array_digest(expected),
            "digest_actual": _array_digest(result),
            "max_abs_error": max_abs,
            "correctness": _PASS if ok else _FAIL,
            "evidence": evidence.as_dict(),
        }

    def _elementwise_case(
        self, runtime: Any, op: str, shape: tuple[int, ...], offset: int
    ) -> dict[str, Any]:
        rng = self._rng(offset)
        a = rng.random(shape, dtype=np.float32)
        if op in ("add", "hadamard"):
            b = rng.random(shape, dtype=np.float32)
            inputs, input_shapes = [a, b], [shape, shape]
            expected = (a + b if op == "add" else a * b).astype(np.float32)
        elif op == "scale":
            b = np.array([2.5], dtype=np.float32)
            inputs, input_shapes = [a, b], [shape, (1,)]
            expected = (a * b[0]).astype(np.float32)
        else:
            raise ValueError(op)
        result, evidence = runtime.execute_with_evidence(
            op, inputs, input_shapes, expected.shape
        )
        ok, max_abs = self._compare(result, expected)
        return {
            "case": op,
            "op": op,
            "shape": shape,
            "seed": self.seed + offset,
            "digest_expected": _array_digest(expected),
            "digest_actual": _array_digest(result),
            "max_abs_error": max_abs,
            "correctness": _PASS if ok else _FAIL,
            "evidence": evidence.as_dict(),
        }

    def _kron_case(self, runtime: Any, rank: int, offset: int) -> dict[str, Any]:
        rng = self._rng(offset)
        if rank == 1:
            a = rng.random((7,), dtype=np.float32)
            b = rng.random((5,), dtype=np.float32)
        else:
            a = rng.random((3, 4), dtype=np.float32)
            b = rng.random((2, 5), dtype=np.float32)
        expected = np.kron(a, b).astype(np.float32)
        result, evidence = runtime.execute_with_evidence(
            "kron", [a, b], [a.shape, b.shape], expected.shape
        )
        ok, max_abs = self._compare(result, expected)
        return {
            "case": f"kron{rank}d",
            "op": "kron",
            "rank": rank,
            "shape_a": tuple(a.shape),
            "shape_b": tuple(b.shape),
            "seed": self.seed + offset,
            "digest_expected": _array_digest(expected),
            "digest_actual": _array_digest(result),
            "max_abs_error": max_abs,
            "correctness": _PASS if ok else _FAIL,
            "evidence": evidence.as_dict(),
        }

    def _timing_samples(self, runtime: Any, m: int, k: int, n: int) -> list[dict[str, Any]]:
        rng = self._rng(900)
        a = rng.random((m, k), dtype=np.float32)
        b = rng.random((k, n), dtype=np.float32)
        expected = np.matmul(a, b).astype(np.float32)
        samples = []
        for index in range(self.timing_samples):
            result, evidence = runtime.execute_with_evidence(
                "matmul", [a, b], [a.shape, b.shape], expected.shape
            )
            ok, max_abs = self._compare(result, expected)
            samples.append(
                {
                    "run_index": index,
                    "operation": "matmul",
                    "matrix_shape": (m, k, n),
                    "kernel": evidence.kernel,
                    "global_size": list(evidence.global_size),
                    "local_size": list(evidence.local_size),
                    "device_time_ns": evidence.device_time_ns,
                    "wall_time_ns": evidence.wall_time_ns,
                    "device_id": evidence.device_id,
                    "profiling_available": evidence.profiling_available,
                    "hardware_executed": evidence.hardware_executed,
                    "max_abs_error": max_abs,
                    "correctness": _PASS if ok else _FAIL,
                }
            )
        return samples

    def _dtype_rejection(self, runtime: Any) -> dict[str, Any]:
        """Certification-negative: an uncertified dtype must be refused."""
        for dtype in self.rejected_dtypes:
            a = np.ones((4, 4), dtype=dtype)
            b = np.ones((4, 4), dtype=dtype)
            try:
                runtime.execute("matmul", [a, b], [a.shape, b.shape], (4, 4))
            except Exception as exc:
                return {
                    "dtype": dtype,
                    "claimed": f"{dtype} not certified",
                    "result": "REJECTED",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            return {
                "dtype": dtype,
                "claimed": f"{dtype} not certified",
                "result": "UNEXPECTED_PASS",
            }
        return {"dtype": "", "result": "REJECTED", "reason": "no uncertified dtype probed"}

    # ---- checks ---------------------------------------------------------
    def _negative_subprocess(self) -> Mapping[str, Any]:
        """Ask a fresh interpreter for the tensor path under a bogus identity."""
        env = dict(os.environ)
        env[self.device_env_var] = NEGATIVE_DEVICE
        env[CHILD_MARKER] = "1"
        completed = subprocess.run(
            [sys.executable, "-m", "chronus.report"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {
                "returncode": completed.returncode,
                "parsed": False,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-2000:],
            }
        return {
            "returncode": completed.returncode,
            "parsed": True,
            "tensor": payload.get("tensor", {}),
        }

    def check_identity_negative(self) -> GateCheck:
        """A device the gate did not ask for must be refused, not substituted.

        Runs first and out of process: an in-process probe could reuse an
        already-bound runtime, and a gate that cannot prove it refuses the wrong
        device is not a gate.
        """
        payload = (
            self._negative_runner()
            if self._negative_runner is not None
            else self._negative_subprocess()
        )
        tensor = payload.get("tensor", {}) if payload.get("parsed", True) else {}
        available = tensor.get("available")
        reason = str(tensor.get("reason", ""))
        refused = available is False and "identity not found" in reason
        return GateCheck(
            name="identity_negative",
            status=_PASS if refused else _FAIL,
            detail=(
                "refused the unrequested device identity"
                if refused
                else f"gate did not fail closed: available={available!r} reason={reason!r}"
            ),
            evidence={
                "requested_device": NEGATIVE_DEVICE,
                "available": available,
                "reason": reason,
                "parsed": payload.get("parsed", True),
                "returncode": payload.get("returncode"),
            },
        )

    def _software_test_subprocess(self) -> tuple[int, str]:
        env = dict(os.environ)
        env[CHILD_MARKER] = "1"
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *SOFTWARE_TEST_TARGETS],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        return completed.returncode, (completed.stdout + completed.stderr)

    def check_software_tests(self) -> GateCheck:
        """The harness must be sound before hardware evidence means anything."""
        if not self.software_tests:
            return GateCheck(
                name="software_tests",
                status=_FAIL,
                detail="software tests disabled: the harness must be exercised first",
            )
        if CHILD_MARKER in os.environ or "PYTEST_CURRENT_TEST" in os.environ:
            return GateCheck(
                name="software_tests",
                status=_FAIL,
                detail="not run: a gate may not recurse into its own software tests",
            )
        returncode, output = self._software_test_subprocess()
        self._emit("software-tests.txt", output)
        return GateCheck(
            name="software_tests",
            status=_PASS if returncode == 0 else _FAIL,
            detail=f"pytest {' '.join(SOFTWARE_TEST_TARGETS)} exit={returncode}",
            evidence={"targets": list(SOFTWARE_TEST_TARGETS), "returncode": returncode},
        )

    def check_work_group_planning(self, cases: Sequence[Mapping[str, Any]]) -> GateCheck:
        """Every launch must fit the kernel's own work-group ceiling.

        ``CL_KERNEL_WORK_GROUP_SIZE`` can sit below the device maximum once
        register pressure and local memory are accounted for; a launch planned
        from the device maximum alone is a latent CL_INVALID_WORK_GROUP_SIZE.
        """
        offenders: list[dict[str, Any]] = []
        ceilings: set[int] = set()
        for case in cases:
            evidence = dict(case.get("evidence", {}))
            local = list(evidence.get("local_size", []))
            ceiling = evidence.get("kernel_max_work_group_size")
            if not local or not ceiling:
                continue
            ceilings.add(int(ceiling))
            if max(local) > int(ceiling):
                offenders.append(
                    {
                        "case": case.get("case"),
                        "local_size": local,
                        "kernel_max_work_group_size": ceiling,
                    }
                )
        return GateCheck(
            name="work_group_planning",
            status=_PASS if not offenders else _FAIL,
            detail=(
                f"{len(cases)} launches within kernel ceilings {sorted(ceilings)}"
                if not offenders
                else f"{len(offenders)} launch(es) exceed the kernel work-group limit"
            ),
            evidence={"offenders": offenders, "kernel_ceilings": sorted(ceilings)},
        )

    def check_in_process_report(self, device_id: str) -> GateCheck:
        """The report must carry this run's evidence for the same device.

        ``chronus.report`` is process-local, so the report has to be taken in
        the process that executed: a report from another process shows
        ``Unavailable`` and proves nothing about this run.
        """
        report = self.report()
        tensor = dict(report.get("tensor", {})) if isinstance(report, Mapping) else {}
        last = tensor.get("last_execution_evidence")
        evidence = {
            "last_execution_evidence": last,
            "report_device_id": tensor.get("device_id"),
            "expected_device_id": device_id,
        }
        if not isinstance(last, Mapping):
            return GateCheck(
                name="in_process_report",
                status=_FAIL,
                detail="report carries no execution evidence for this run",
                evidence=evidence,
            )
        bound = last.get("device_id") == device_id and bool(last.get("hardware_executed"))
        return GateCheck(
            name="in_process_report",
            status=_PASS if bound else _FAIL,
            detail=(
                f"report evidence bound to {device_id}"
                if bound
                else "report evidence is missing or bound to another device"
            ),
            evidence=evidence,
        )

    # ---- run ------------------------------------------------------------
    def run(self) -> GateResult:
        """Execute the gate and write its evidence. Fails closed at every step."""
        self._payloads = {}
        checks: list[GateCheck] = []

        # 1. Identity negative, before anything binds a device.
        negative = self.check_identity_negative()
        checks.append(negative)
        self._emit_json("identity-negative.json", negative.as_dict())
        if not negative.passed:
            return self._finish(checks, {})

        # 2. The harness, before the hardware it measures.
        checks.append(self.check_software_tests())

        # 3. Device identity as Chronus independently enumerates it.
        probe = self.probe()
        probe_info = probe.as_dict() if hasattr(probe, "as_dict") else dict(probe)
        if not probe_info.get("available"):
            checks.append(
                GateCheck(
                    name="device_identity",
                    status=_FAIL,
                    detail=f"tensor probe unavailable: {probe_info.get('reason', '')}",
                    evidence=probe_info,
                )
            )
            return self._finish(checks, probe_info)
        self._emit_json("chronus-report-before.json", self.report())
        checks.append(
            GateCheck(
                name="device_identity",
                status=_PASS,
                detail=f"{probe_info.get('device_name')} on {probe_info.get('platform_name')}",
                evidence=probe_info,
            )
        )

        # 4. Certified operations, including non-tile-aligned boundaries.
        runtime = self.runtime()
        device_id = getattr(runtime, "device_id", probe_info.get("device_id", ""))
        cases: list[dict[str, Any]] = []
        for offset, (m, k, n) in enumerate(self.boundary_shapes):
            cases.append(self._matmul_case(runtime, m, k, n, offset))
        for index, op in enumerate(("add", "scale", "hadamard")):
            for shape_index, shape in enumerate(self.elementwise_shapes):
                cases.append(
                    self._elementwise_case(runtime, op, shape, 10 + index * 10 + shape_index)
                )
        for rank in (1, 2):
            cases.append(self._kron_case(runtime, rank, 40 + rank))
        correctness = {
            "probe": probe_info,
            "required_ops": list(self.required_ops),
            "tolerance": {"rtol": self.rtol, "atol": self.atol},
            "dtypes": list(self.dtypes),
            "cases": cases,
        }
        self._emit_json("tensor-correctness.json", correctness)
        failures = [case["case"] for case in cases if case["correctness"] != _PASS]
        checks.append(
            GateCheck(
                name="tensor_correctness",
                status=_PASS if not failures else _FAIL,
                detail=(
                    f"{len(cases)} cases within tolerance "
                    f"(rtol={self.rtol}, atol={self.atol})"
                    if not failures
                    else f"failing cases: {failures}"
                ),
                evidence={
                    "cases": len(cases),
                    "max_abs_error": max(
                        (case["max_abs_error"] for case in cases), default=0.0
                    ),
                    "non_tile_aligned": [
                        case["case"] for case in cases if case.get("tile_aligned") is False
                    ],
                    "failing": failures,
                },
            )
        )
        checks.append(self.check_work_group_planning(cases))

        # 5. Certification-negative: an uncertified dtype must be refused.
        dtype_negative = self._dtype_rejection(runtime)
        self._emit_json("dtype-negative.json", dtype_negative)
        checks.append(
            GateCheck(
                name="dtype_rejection",
                status=_PASS if dtype_negative.get("result") == "REJECTED" else _FAIL,
                detail=f"{dtype_negative.get('dtype')} -> {dtype_negative.get('result')}",
                evidence=dtype_negative,
            )
        )

        # 6. On-device profiling over a sustained load.
        samples = self._timing_samples(runtime, 31, 37, 29)
        self._emit(
            "profiling-samples.jsonl",
            "".join(json.dumps(sample, default=str) + "\n" for sample in samples),
        )
        profiled = [
            s
            for s in samples
            if s["profiling_available"]
            and s["device_time_ns"]
            and s["device_time_ns"] > 0
            and s["hardware_executed"]
        ]
        device_times = [int(s["device_time_ns"]) for s in profiled]
        wall_times = [int(s["wall_time_ns"]) for s in samples]
        timing = {
            "samples": len(samples),
            "device_time_ns": {
                "min": min(device_times) if device_times else None,
                "median": int(np.median(device_times)) if device_times else None,
                "max": max(device_times) if device_times else None,
                "mean": float(np.mean(device_times)) if device_times else None,
            },
            "wall_time_ns": {
                "min": min(wall_times) if wall_times else None,
                "median": int(np.median(wall_times)) if wall_times else None,
                "max": max(wall_times) if wall_times else None,
            },
            "all_samples_correct": all(s["correctness"] == _PASS for s in samples),
        }
        self._emit_json("timing-summary.json", timing)
        checks.append(
            GateCheck(
                name="on_device_profiling",
                status=_PASS if samples and len(profiled) == len(samples) else _FAIL,
                detail=(
                    f"{len(profiled)}/{len(samples)} samples carry on-device time"
                    if samples
                    else "no timing samples were taken"
                ),
                evidence={"profiled": len(profiled), "samples": len(samples)},
            )
        )

        # 7. The report, in the process that executed.
        self._emit_json("chronus-report-after.json", self.report())
        checks.append(self.check_in_process_report(device_id))
        return self._finish(checks, probe_info)

    # ---- artifacts ------------------------------------------------------
    def _finish(
        self, checks: Sequence[GateCheck], device: Mapping[str, Any]
    ) -> GateResult:
        """Write the evidence, bind it by digest, and return the verdict."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        digests: dict[str, str] = {}
        for name, text in sorted(self._payloads.items()):
            digests[name] = _write(self.artifact_dir / name, text)
        # A chain over the whole set, so dropping or swapping a file breaks it.
        chain = _sha256(
            "\n".join(f"{name}  {digests[name]}" for name in sorted(digests)).encode("utf-8")
        )
        verdict = GateResult(
            target=self.target,
            status=_PASS if all(c.passed for c in checks) else _FAIL,
            device=dict(device),
            checks=tuple(checks),
            artifact_dir=str(self.artifact_dir),
            evidence_files=digests,
            hash_chain=chain,
        )
        manifest = dict(verdict.as_dict())
        manifest.update(
            {
                "generated_at": _now(),
                "software_findings": list(self.findings),
                "contract": {
                    "required_ops": list(self.required_ops),
                    "boundary_shapes": [list(s) for s in self.boundary_shapes],
                    "elementwise_shapes": [list(s) for s in self.elementwise_shapes],
                    "dtypes": list(self.dtypes),
                    "rejected_dtypes": list(self.rejected_dtypes),
                    "tolerance": {"rtol": self.rtol, "atol": self.atol},
                    "timing_samples": self.timing_samples,
                },
            }
        )
        manifest_text = json.dumps(manifest, indent=2, default=str) + "\n"
        manifest_digest = _write(self.artifact_dir / "manifest.json", manifest_text)
        # sha256sums.txt covers evidence and manifest, in `sha256sum -c` form.
        lines = [f"{digests[name]}  {name}" for name in sorted(digests)]
        lines.append(f"{manifest_digest}  manifest.json")
        _write(
            self.artifact_dir / "sha256sums.txt",
            "\n".join(lines) + "\n",
        )
        bound = GateResult(
            target=verdict.target,
            status=verdict.status,
            device=verdict.device,
            checks=verdict.checks,
            artifact_dir=verdict.artifact_dir,
            evidence_files=digests,
            hash_chain=chain,
            manifest_sha256=manifest_digest,
        )
        _write(self.artifact_dir / "STATUS.md", self._status_markdown(bound))
        return bound

    def _status_markdown(self, verdict: GateResult) -> str:
        device = dict(verdict.device)
        lines = [
            f"# Chronus OpenCL conformance gate — {verdict.target}",
            "",
            f"**Status: {verdict.status}**",
            "",
            f"- Device: {device.get('device_name', 'unknown')}",
            f"- Device id: `{device.get('device_id', '')}`",
            f"- Platform: {device.get('platform_name', '')}",
            f"- Catalog family: {device.get('family', '') or 'unverified'}",
            f"- Evidence: `{verdict.artifact_dir}`",
            f"- Hash chain: `{verdict.hash_chain}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in verdict.checks:
            lines.append(f"| `{check.name}` | {check.status} | {check.detail} |")
        lines += ["", "## Evidence files", "", "| File | SHA256 |", "|---|---|"]
        for name, digest in sorted(verdict.evidence_files.items()):
            lines.append(f"| `{name}` | `{digest}` |")
        lines += [
            f"| `manifest.json` | `{verdict.manifest_sha256}` |",
            "",
            "Timing is measured on the device by the OpenCL runtime for the exact",
            "workload above. No performance is claimed beyond it.",
            "",
        ]
        return "\n".join(lines)


def verify_artifacts(artifact_dir: str | os.PathLike[str]) -> tuple[bool, list[str]]:
    """Re-hash a gate's evidence and report anything that no longer matches.

    The tamper-evidence claim is only worth making if it can be re-checked, so
    this reads ``sha256sums.txt`` and compares it against the files on disk.
    """
    root = Path(artifact_dir)
    sums = root / "sha256sums.txt"
    if not sums.is_file():
        return False, [f"missing {sums}"]
    problems: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, name = line.partition("  ")
        path = root / name
        if not path.is_file():
            problems.append(f"missing evidence file: {name}")
            continue
        if _sha256(path.read_bytes()) != digest:
            problems.append(f"digest mismatch: {name}")
    manifest = root / "manifest.json"
    if manifest.is_file():
        try:
            recorded = json.loads(manifest.read_text(encoding="utf-8")).get("hash_chain")
        except json.JSONDecodeError:
            problems.append("manifest.json is not valid JSON")
            recorded = None
        if recorded:
            digests = {
                line.partition("  ")[2]: line.partition("  ")[0]
                for line in sums.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.endswith("manifest.json")
            }
            chain = _sha256(
                "\n".join(f"{n}  {digests[n]}" for n in sorted(digests)).encode("utf-8")
            )
            if chain != recorded:
                problems.append("hash chain does not match the evidence set")
    return not problems, problems


__all__ = [
    "CHILD_MARKER",
    "NEGATIVE_DEVICE",
    "SCHEMA",
    "SOFTWARE_TEST_TARGETS",
    "GateCheck",
    "GateResult",
    "OpenCLConformanceSuite",
    "verify_artifacts",
]
