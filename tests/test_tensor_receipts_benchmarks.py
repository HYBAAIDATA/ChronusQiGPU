"""Phase 8: receipts bind identity/work/residency/timing; benchmark matrix."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tensor.api import TensorRuntime
from tensor.benchmarks import run_benchmarks
from tensor.contracts import TruthClass


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_lifted_receipt_binds_all_fields_with_zero_decode():
    rt = TensorRuntime()
    a = np.linspace(-1, 1, 64)
    rt.store_tensor("a", a)
    rt.store_tensor("b", np.linspace(0.5, 1.5, 64))
    record = rt.execute("add", ["a", "b"], out="c")
    receipt = record["receipt"]

    assert receipt["schema_version"] == "tensor.receipt/1"
    # Identity + routing
    assert receipt["request_id"] == record["request_id"]
    assert receipt["operation"] == "add"
    assert receipt["backend"] == "tensor.folded:add"
    assert receipt["device"] == "aethel-resident"
    assert receipt["path"] == "lifted"
    # Inputs/outputs bound by hash
    assert len(receipt["input_hashes"]) == 2
    assert receipt["output_hash"] == rt.store.content_hash("c")
    # Residency vs analytical distinct: measured decode is zero, the
    # dense estimate is not.
    assert receipt["bytes_decoded"] == 0
    assert receipt["bytes_transferred"] == 0
    assert receipt["bytes_resident"] > 0
    assert receipt["bytes_analytical"] == (
        receipt["bytes_logical_inputs"] + receipt["bytes_logical_output"]
    )
    # Timing + truth
    assert receipt["timing_scope"] == "end_to_end"
    assert receipt["truth_class"] == TruthClass.MEASURED.value
    assert receipt["correctness"] == "unvalidated"
    assert receipt["elapsed_ns"] >= 1


def test_materialized_receipt_reports_full_decode():
    rt = TensorRuntime()
    rt.store_tensor("a", np.eye(8))
    rt.store_tensor("b", np.eye(8) * 2)
    record = rt.execute("matmul", ["a", "b"], out="c")
    receipt = record["receipt"]
    assert receipt["path"] == "materialized"
    assert receipt["bytes_decoded"] == receipt["bytes_logical_inputs"] > 0
    assert receipt["fallback_used"] is True
    assert "declared materializing" in receipt["fallback_reason"]


def test_backend_receipt_identifies_real_backend_and_device():
    rt = TensorRuntime()
    record = rt.execute(
        "matmul", [np.eye(4), np.eye(4) * 3], backend_required="numpy-cpu"
    )
    receipt = record["receipt"]
    assert receipt["backend"] == "numpy-cpu"
    assert receipt["device"].startswith("cpu")
    assert receipt["bytes_transferred"] == (
        receipt["bytes_logical_inputs"] + receipt["bytes_logical_output"]
    )
    assert receipt["truth_class"] == TruthClass.MEASURED.value


def test_mixed_resident_operand_counts_decode_cost():
    rt = TensorRuntime()
    rt.store_tensor("a", np.arange(16, dtype=np.float64).reshape(4, 4))
    record = rt.execute("matmul", ["a", np.eye(4)])
    receipt = record["receipt"]
    # One operand had to be decoded out of custody — the receipt says so.
    assert receipt["bytes_decoded"] == 16 * 8


def test_benchmark_matrix_validates_every_output():
    report = run_benchmarks(
        operations=["add", "transpose"],
        sizes=((16, 16), (64, 64)),
        dtypes=("float64", "complex128"),
        layouts=("C", "F"),
        repeats=2,
    )
    payload = report.as_dict()
    assert payload["schema_version"] == "tensor.benchmark/1"
    assert payload["truth_class"] == "measured"
    assert payload["timing_scope"] == "end_to_end"
    assert report.all_valid and report.failed_outputs == 0
    # Cold/warm and resident/nonresident are both represented.
    modes = {(r["residency"], r["temperature"]) for r in payload["rows"]}
    assert ("resident", "cold") in modes
    assert ("resident", "warm") in modes
    assert ("nonresident", "cold") in modes
    # Lifted rows measured zero decoded bytes; analytical estimate nonzero.
    lifted = [r for r in payload["rows"] if r["path"] == "lifted"]
    assert lifted and all(r["bytes_decoded"] == 0 for r in lifted)
    assert all(r["bytes_analytical"] > 0 for r in lifted)


def test_benchmark_matrix_materializing_ops_decode():
    report = run_benchmarks(
        operations=["matmul"],
        sizes=((16, 16),),
        dtypes=("float64",),
        layouts=("C",),
        repeats=1,
    )
    assert report.all_valid
    assert all(r.path == "materialized" for r in report.rows)
    assert all(r.bytes_decoded == r.bytes_logical_inputs
               if hasattr(r, "bytes_logical_inputs") else r.bytes_decoded > 0
               for r in report.rows)


def test_cli_benchmark_emits_report(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "tensor", "--store-path",
         str(tmp_path / "s.npz"), "benchmark", "add", "--repeats", "1",
         "--size", "16"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] and payload["correct"] is True
    assert payload["report"]["all_valid"] is True
    assert payload["promotion"]["promoted"] is True
    assert payload["report"]["failed_outputs"] == 0
