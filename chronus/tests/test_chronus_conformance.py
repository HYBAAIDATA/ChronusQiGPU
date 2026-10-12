"""Conformance-gate regression tests (no GPU required).

The suite's logic is exercised through its injection points, so a change to the
gate is testable on any host. The evidence it produces on a real device is never
fabricated here: the fake runtime stands in for the launch, and claims about
silicon are left to the real run.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from chronus.conformance import (
    NEGATIVE_DEVICE,
    SCHEMA,
    GateCheck,
    GateResult,
    OpenCLConformanceSuite,
    verify_artifacts,
)
from chronus.tensor_compute import (
    ChronusTensorValidationError,
    TensorExecutionEvidence,
    plan_work_group,
)

DEVICE_ID = "opencl:Intel(R) OpenCL HD Graphics:Intel(R) UHD Graphics 620"


class _Runtime:
    """NumPy stand-in with the real runtime's execution-evidence surface."""

    device_id = DEVICE_ID

    def __init__(self, perturb: float = 0.0) -> None:
        self.perturb = perturb
        self.last_evidence = None

    @staticmethod
    def _reference(operation, arrays):
        if operation == "matmul":
            return np.matmul(arrays[0], arrays[1])
        if operation == "add":
            return arrays[0] + arrays[1]
        if operation == "hadamard":
            return arrays[0] * arrays[1]
        if operation == "scale":
            return arrays[0] * arrays[1][0]
        if operation == "kron":
            return np.kron(arrays[0], arrays[1])
        raise AssertionError(operation)

    def _evidence(self, operation, shape):
        return TensorExecutionEvidence(
            operation=operation,
            device_id=self.device_id,
            kernel=f"tensor_{operation}_f32",
            global_size=tuple(shape),
            local_size=(min(16, max(1, max(shape))),),
            output_shape=tuple(shape),
            device_time_ns=30_166,
            wall_time_ns=2_693_700,
            profiling_available=True,
            device_max_work_group_size=256,
            kernel_max_work_group_size=256,
        )

    def execute_with_evidence(self, operation, inputs, input_shapes, output_shape):
        arrays = []
        for value, shape in zip(inputs, input_shapes):
            array = np.asarray(value)
            if array.dtype != np.float32:
                raise ChronusTensorValidationError(
                    f"unsupported dtype {array.dtype}; only float32 is certified"
                )
            if tuple(array.shape) != tuple(shape):
                raise ChronusTensorValidationError("input shape disagrees")
            arrays.append(array)
        expected = self._reference(operation, arrays).astype(np.float32)
        if self.perturb:
            expected = (expected + self.perturb).astype(np.float32)
        self.last_evidence = self._evidence(operation, expected.shape)
        return expected, self.last_evidence

    def execute(self, operation, inputs, input_shapes, output_shape):
        result, _ = self.execute_with_evidence(operation, inputs, input_shapes, output_shape)
        return result


def _probe(available=True, reason=""):
    return SimpleNamespace(
        as_dict=lambda: {
            "available": available,
            "device_id": DEVICE_ID,
            "device_name": "Intel(R) UHD Graphics 620",
            "platform_name": "Intel(R) OpenCL HD Graphics",
            "family": "intel-uhd-620",
            "reason": reason,
        }
    )


def _negative(refused=True):
    return {
        "parsed": True,
        "returncode": 0,
        "tensor": {
            "available": not refused,
            "reason": (
                f"requested OpenCL GPU identity not found: {{'device': '{NEGATIVE_DEVICE}'}}"
                if refused
                else ""
            ),
        },
    }


def _suite(tmp_path, runtime=None, **kwargs):
    runtime = runtime or _Runtime()
    return OpenCLConformanceSuite(
        target="intel-uhd-620",
        artifact_dir=tmp_path / "evidence",
        software_tests=False,
        probe_fn=_probe,
        runtime_factory=lambda: runtime,
        report_fn=lambda: {
            "tensor": {
                "available": True,
                "device_id": DEVICE_ID,
                "last_execution_evidence": (
                    runtime.last_evidence.as_dict() if runtime.last_evidence else "Unavailable"
                ),
            }
        },
        negative_runner=lambda: _negative(),
        **kwargs,
    )


def _cases(tmp_path):
    payload = json.loads((tmp_path / "evidence" / "tensor-correctness.json").read_text("utf-8"))
    return payload["cases"]


def test_gate_passes_on_a_conforming_runtime(tmp_path):
    result = _suite(tmp_path).run()
    # software_tests is the one check the suite refuses to fake: under pytest it
    # declines to recurse, so it reports FAIL rather than quietly skipping.
    assert result.failures == ("software_tests",)
    assert all(c.passed for c in result.checks if c.name != "software_tests")
    assert (tmp_path / "evidence" / "manifest.json").is_file()


def test_every_certified_operation_and_boundary_shape_is_exercised(tmp_path):
    suite = _suite(tmp_path)
    result = suite.run()
    assert result.check("tensor_correctness").passed
    covered = {case["op"] for case in _cases(tmp_path)}
    assert set(suite.required_ops) <= covered
    aligned = [case for case in _cases(tmp_path) if case.get("tile_aligned") is True]
    assert aligned, "at least one tile-aligned control case is required"
    assert len(aligned) < len(_cases(tmp_path)), "boundary shapes must not all be aligned"


def test_wrong_result_fails_the_gate(tmp_path):
    result = _suite(tmp_path, runtime=_Runtime(perturb=0.5)).run()
    assert result.passed is False
    assert "tensor_correctness" in result.failures
    assert result.check("tensor_correctness").evidence["failing"]


def test_identity_negative_must_refuse_before_anything_executes(tmp_path):
    suite = _suite(tmp_path)
    suite._negative_runner = lambda: _negative(refused=False)
    result = suite.run()
    assert result.failures[0] == "identity_negative"
    # Nothing executed, so no correctness evidence exists to be fooled by.
    assert not (tmp_path / "evidence" / "tensor-correctness.json").exists()


def test_missing_check_is_not_a_pass():
    result = GateResult(target="t", status="PASS", device={}, checks=())
    assert result.passed is False
    assert GateCheck(name="x", status="PASS").passed is True
    assert GateCheck(name="x", status="FAIL").passed is False


def test_report_evidence_must_come_from_the_executing_process(tmp_path):
    suite = _suite(tmp_path)
    suite._report_fn = lambda: {
        "tensor": {"available": True, "last_execution_evidence": "Unavailable"}
    }
    result = suite.run()
    assert "in_process_report" in result.failures


def test_launch_above_the_kernel_ceiling_is_caught(tmp_path):
    """A launch planned from the device maximum alone must not pass the gate."""
    runtime = _Runtime()
    inner = runtime.execute_with_evidence

    def _oversized(operation, inputs, input_shapes, output_shape):
        result, evidence = inner(operation, inputs, input_shapes, output_shape)
        object.__setattr__(evidence, "local_size", (64, 64))
        object.__setattr__(evidence, "kernel_max_work_group_size", 32)
        return result, evidence

    runtime.execute_with_evidence = _oversized
    result = _suite(tmp_path, runtime=runtime).run()
    planning = result.check("work_group_planning")
    assert planning.status == "FAIL"
    assert planning.evidence["offenders"]


def test_evidence_set_is_hash_bound_and_reverifiable(tmp_path):
    result = _suite(tmp_path).run()
    root = tmp_path / "evidence"
    ok, problems = verify_artifacts(root)
    assert ok, problems
    assert result.manifest_sha256 and result.hash_chain
    (root / "timing-summary.json").write_text("{}", encoding="utf-8")
    ok, problems = verify_artifacts(root)
    assert not ok and any("digest mismatch" in p for p in problems)
    (root / "timing-summary.json").unlink()
    ok, problems = verify_artifacts(root)
    assert not ok and any("missing evidence file" in p for p in problems)


def test_manifest_records_the_contract_it_enforced(tmp_path):
    _suite(tmp_path).run()
    manifest = json.loads((tmp_path / "evidence" / "manifest.json").read_text("utf-8"))
    assert manifest["schema"] == SCHEMA
    contract = manifest["contract"]
    assert contract["dtypes"] == ["float32"]
    assert contract["rejected_dtypes"] == ["float64"]
    assert contract["required_ops"] == list(OpenCLConformanceSuite.required_ops)
    assert (31, 37, 29) in [tuple(s) for s in contract["boundary_shapes"]]
    assert manifest["hash_chain"]


def test_wrapper_binds_the_uhd620_identity_and_closes_the_findings():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "uhd_gate", root / "chronus" / "scripts" / "chronus_uhd620_evidence_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.parse_args([])
    assert args.device == "UHD Graphics 620"
    assert args.vendor == "Intel"
    assert args.alias == "intel,uhd"
    assert args.require_hyba == "0"
    assert {f["id"] for f in module.RESOLVED_FINDINGS} == {
        "HYBA_DEVICE_ALIAS-fatal-without-HYBA",
        "generic-graphics-match",
        "matmul-wg-planning",
    }
    assert all(f["disposition"] == "fixed" for f in module.RESOLVED_FINDINGS)


# ---- Finding 3: kernel-aware work-group planning -------------------------


def _cl():
    return SimpleNamespace(kernel_work_group_info=SimpleNamespace(WORK_GROUP_SIZE=0x11B0))


def test_work_group_is_the_minimum_of_device_and_kernel_limits():
    cl, device = _cl(), SimpleNamespace(max_work_group_size=256)
    for kernel_limit, expected in ((256, 256), (64, 64), (1024, 256), (1, 1)):
        kernel = SimpleNamespace(get_work_group_info=lambda p, d, k=kernel_limit: k)
        assert plan_work_group(kernel, device, cl) == expected


def test_work_group_falls_back_to_the_device_limit_when_unqueryable():
    cl, device = _cl(), SimpleNamespace(max_work_group_size=256)

    def _boom(param, dev):
        raise RuntimeError("CL_KERNEL_WORK_GROUP_SIZE unsupported")

    assert plan_work_group(SimpleNamespace(get_work_group_info=_boom), device, cl) == 256
    assert plan_work_group(SimpleNamespace(), device, cl) == 256


@pytest.mark.parametrize("ceiling,expected_tile", ((64, 8), (256, 16)))
def test_matmul_tile_shrinks_with_the_kernel_ceiling(ceiling, expected_tile):
    from chronus.tensor_compute import _plan_matmul

    _global, local = _plan_matmul(31, 17, ceiling, 32 << 10)
    assert local == (expected_tile, expected_tile)
