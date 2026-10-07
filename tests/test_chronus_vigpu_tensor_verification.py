"""Virtual iGPU tensor verification is delegated to the canonical ``tensor`` layer.

Regression: the control-plane verifier compared nested (2-D) results with a flat float() loop, so
every correct 2-D matmul/scale/add was marked ``verification_failed``. Found by running Chronus
on real workloads (scripts/chronus_capability_probe.py).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from chronus.virtual_igpu import verifier
from chronus.virtual_igpu.abi import ExecutionPolicy, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon

RNG = np.random.default_rng(20261006)


def _daemon(tmp_path, adapter=None):
    return RuntimeDaemon(adapters=[adapter or CPUEmulatorAdapter()], store_dir=tmp_path / "rt")


def _submit(daemon, wid, payload):
    return daemon.submit(
        Workload(
            id=wid,
            kind=WorkloadKind.TENSOR_OP,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input=payload,
        )
    )


@pytest.mark.parametrize("n", [2, 17, 96])
def test_correct_2d_matmul_is_verified_not_rejected(tmp_path, n) -> None:
    a, b = RNG.standard_normal((n, n)), RNG.standard_normal((n, n))
    result = _submit(
        _daemon(tmp_path), f"mm{n}", {"op": "matmul", "a": a.tolist(), "b": b.tolist()}
    )
    assert result.status == "ok"
    assert result.receipt["verification"]["verdict"] == "match"
    assert np.max(np.abs(np.asarray(result.output["data"]) - a @ b)) < 1e-9


def test_rectangular_matmul_scale_and_broadcast_add_verify(tmp_path) -> None:
    daemon = _daemon(tmp_path)
    a, b = RNG.standard_normal((5, 7)), RNG.standard_normal((7, 3))
    assert (
        _submit(daemon, "rect", {"op": "matmul", "a": a.tolist(), "b": b.tolist()}).status == "ok"
    )
    assert _submit(daemon, "sc", {"op": "scale", "a": a.tolist(), "scalar": -2.5}).status == "ok"
    row = RNG.standard_normal(7)
    r = _submit(daemon, "bc", {"op": "add", "a": a.tolist(), "b": row.tolist()})
    assert r.status == "ok" and r.receipt["verification"]["verdict"] == "match"


class _Corrupting(CPUEmulatorAdapter):
    id = "cpu-corrupt-tensor"

    def execute(self, workload):
        result = super().execute(workload)
        data = np.asarray(result.output["data"], dtype=np.float64)
        data.flat[0] += 1e-3  # one wrong element in an otherwise correct matrix
        return replace(result, output={**result.output, "data": data.tolist()})


def test_single_wrong_element_in_a_2d_result_is_rejected(tmp_path) -> None:
    a, b = RNG.standard_normal((8, 8)), RNG.standard_normal((8, 8))
    result = _submit(
        _daemon(tmp_path, _Corrupting()), "bad", {"op": "matmul", "a": a.tolist(), "b": b.tolist()}
    )
    assert result.status == "verification_failed"
    assert "folded_resident_recompute" in (result.error or "")


def test_wrong_shape_is_rejected(tmp_path) -> None:
    a = RNG.standard_normal((3, 4))

    class Flatten(CPUEmulatorAdapter):
        def execute(self, workload):
            result = super().execute(workload)
            flat = np.asarray(result.output["data"]).ravel().tolist()
            return replace(result, output={**result.output, "data": flat, "shape": [12]})

    result = _submit(
        _daemon(tmp_path, Flatten()), "shape", {"op": "scale", "a": a.tolist(), "scalar": 2.0}
    )
    assert result.status == "verification_failed"


def test_verification_is_delegated_to_the_tensor_layer(monkeypatch) -> None:
    import tensor.verification as tv

    calls = []
    real = tv.verify_backend_output

    def spy(operation, arrays, data):
        calls.append(operation)
        return real(operation, arrays, data)

    monkeypatch.setattr(tv, "verify_backend_output", spy)
    a = RNG.standard_normal((4, 4))
    out = {"data": (a @ a).tolist(), "shape": [4, 4]}
    assert verifier._verify_tensor_op({"op": "matmul", "a": a.tolist(), "b": a.tolist()}, out) == []
    assert calls == ["matmul"]


def test_local_recompute_still_runs_when_the_tensor_layer_cannot(monkeypatch) -> None:
    import tensor.verification as tv

    def broken(*_a, **_k):
        raise RuntimeError("tensor layer unavailable")

    monkeypatch.setattr(tv, "verify_backend_output", broken)
    a = RNG.standard_normal((4, 4))
    good = {"data": (a @ a).tolist(), "shape": [4, 4]}
    bad = {"data": (a @ a + 1e-3).tolist(), "shape": [4, 4]}
    payload = {"op": "matmul", "a": a.tolist(), "b": a.tolist()}
    assert verifier._verify_tensor_op(payload, good) == []
    assert verifier._verify_tensor_op(payload, bad) == ["matmul output mismatch"]


def test_nd_tolerance_compare_helper() -> None:
    m = RNG.standard_normal((3, 3))
    assert verifier._seq_close(m.tolist(), m)
    assert not verifier._seq_close(m.tolist(), m + 1e-6)
    assert not verifier._seq_close(m.ravel().tolist(), m)  # shape matters
    assert not verifier._seq_close([[1.0, "x"]], [[1.0, 2.0]])
