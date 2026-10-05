"""Canonical TensorRuntime: custody + folded/backend execution + publication."""

import json
import subprocess
import sys
import threading
from pathlib import Path
from http import HTTPStatus

import numpy as np
import pytest

from tensor.api import TensorRuntime
from tensor.errors import TensorCancelledError


REPO_ROOT = Path(__file__).resolve().parents[1]
PY_DIR = REPO_ROOT / "chronus/mla1517_platform" / "python"


def _runtime():
    return TensorRuntime()


def test_store_then_folded_execute_publishes_block_and_receipt():
    rt = _runtime()
    a = np.linspace(-1, 1, 64)
    b = np.linspace(0.5, 1.5, 64)
    rt.store_tensor("a", a)
    rt.store_tensor("b", b)
    record = rt.execute("add", ["a", "b"], out="c")
    assert record["path"] == "lifted"
    assert record["decoded_bytes"] == 0
    np.testing.assert_array_equal(rt.read_tensor("c"), a + b)
    # Atomic publication: the same record is retrievable by request id.
    assert rt.result(record["request_id"]) == record
    assert record["output_hash"] == rt.store.content_hash("c")


def test_backend_path_over_arrays():
    rt = _runtime()
    a = np.arange(12, dtype=np.float64).reshape(3, 4)
    b = np.arange(8, dtype=np.float64).reshape(4, 2)
    record = rt.execute("matmul", [a, b])
    assert record["path"] == "backend"
    np.testing.assert_array_equal(np.asarray(record["output"]), a @ b)
    assert record["truth_class"] == "measured"


def test_mixed_operands_route_to_backend():
    rt = _runtime()
    rt.store_tensor("a", np.arange(8, dtype=np.float64))
    record = rt.execute("add", ["a", np.arange(8)])
    assert record["path"] == "backend"


def test_concurrent_executions_publish_atomically():
    rt = _runtime()
    rt.store_tensor("a", np.arange(64, dtype=np.float64))
    rt.store_tensor("b", np.arange(64, dtype=np.float64))
    records, errors = [], []

    def worker(n):
        try:
            records.append(rt.execute("add", ["a", "b"], out=f"out{n}"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(records) == 8
    assert all(rt.result(r["request_id"]) for r in records)
    assert len([n for n in rt.tensor_names() if n.startswith("out")]) == 8


def test_cancel_unknown_request_is_honest():
    rt = _runtime()
    assert rt.cancel("no-such-id") is False
    token_store = _runtime()
    token_store.store_tensor("a", np.arange(4, dtype=np.float64))
    # A token cancelled before execute fails closed, not silently.
    from tensor.runtime import CancellationToken

    token = CancellationToken()
    token.cancel()
    with pytest.raises(TensorCancelledError):
        token_store.execute(
            "add", [np.ones(4), np.ones(4)], cancel_token=token
        )


def test_capabilities_surface_is_honest():
    rt = _runtime()
    caps = rt.capabilities()
    assert caps["operators"]["add"]["path"] == "lifted"
    assert caps["operators"]["matmul"]["path"] == "materialized"
    assert "numpy-cpu" in caps["backends"]
    assert caps["schema_version"] == "tensor.capabilities/1"


def test_folded_pilot_runs_through_runtime():
    from tensor.folded_inference import FoldedLinearPilot, FoldedWeightState

    weights = np.arange(48, dtype=np.float64).reshape(6, 8) / 10.0
    x = np.arange(8, dtype=np.float64).reshape(1, 8)
    rt = _runtime()
    pilot = FoldedLinearPilot(FoldedWeightState.from_array(weights, depth=2), runtime=rt)
    out = pilot.run(x, chunk_rows=4)
    np.testing.assert_allclose(out["output"], x @ weights.T)
    assert "folded-linear-weights" in rt.capabilities()["residency"]["external_custody"]


# -- production control-API surface -----------------------------------------


def test_control_api_tensor_endpoints():
    sys.path.insert(0, str(PY_DIR))
    import control_api

    # Capabilities is the honest catalogue, guardian-mediated on GET.
    caps = control_api.tensor_capabilities_payload()
    assert caps["schema_version"] == "tensor.capabilities/1"

    # Execute over inline tensors: custody taken, folded path used.
    code, payload = control_api._tensor_execute(
        {
            "operation": "add",
            "tensors": {
                "x": [[1.0, 2.0], [3.0, 4.0]],
                "y": [[0.5, 0.5], [0.5, 0.5]],
            },
        }
    )
    assert code == HTTPStatus.OK
    np.testing.assert_array_equal(
        np.asarray(payload["values"]), np.array([[1.5, 2.5], [3.5, 4.5]])
    )
    assert payload["path"] in {"lifted", "materialized"}
    assert payload["truth_class"] == "measured"

    # Inline arrays take the backend path.
    code, payload = control_api._tensor_execute(
        {
            "operation": "matmul",
            "operands": [[[1.0, 0.0], [0.0, 1.0]], [[2.0, 0.0], [0.0, 2.0]]],
        }
    )
    assert code == HTTPStatus.OK
    assert payload["path"] == "backend"
    np.testing.assert_array_equal(
        np.asarray(payload["output"]), np.eye(2) * 2.0
    )


def test_tensor_prefix_is_guardian_privileged():
    sys.path.insert(0, str(PY_DIR))
    import control_api

    assert "/api/v1/tensor/" in control_api._PRIVILEGED_PREFIXES
    assert "/api/v1/tensor/execute" in control_api._Handler._POST_TABLE


# -- python -m tensor CLI ---------------------------------------------------


def _cli(tmp_path, *argv):
    proc = subprocess.run(
        [sys.executable, "-m", "tensor", "--store-path",
         str(tmp_path / "store.npz"), *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    return json.loads(proc.stdout)


def test_cli_store_run_report_roundtrip(tmp_path):
    out = _cli(tmp_path, "store", "a", "--shape", "8x8", "--seed", "7")
    assert out["ok"] and out["name"] == "a"
    _cli(tmp_path, "store", "b", "--shape", "8x8", "--seed", "9")
    record = _cli(tmp_path, "run", "add", "a", "b", "--out", "c")
    assert record["ok"] and record["path"] == "lifted"
    report = _cli(tmp_path, "report")
    assert report["ok"]
    assert "c" in report["capabilities"]["residency"]["blocks"]
    bench = _cli(tmp_path, "benchmark", "add", "--repeats", "2", "--size", "16")
    assert bench["ok"] and bench["correct"]


def test_cli_errors_are_json_and_nonzero(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "tensor", "--store-path",
         str(tmp_path / "s.npz"), "run", "add", "missing"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
