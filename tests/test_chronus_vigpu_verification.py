"""Independent recompute verification on the virtual_igpu submit route.

Audit item (Chronus first-workload readiness, patch plan): execution →
verification was the first broken transition — receipts certified *that*
work ran, not that the output was right.  ``verify_workload_result`` is
the control-plane oracle; these tests pin both directions:

  * correct adapter output -> verdict ``match`` recorded in the receipt
  * corrupted adapter output -> ``verification_failed``, never a silent ok
"""
from __future__ import annotations

import time
from dataclasses import replace

import pytest

from chronus.virtual_igpu.abi import (
    ExecutionPolicy,
    Workload,
    WorkloadKind,
)
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon
from chronus.virtual_igpu.verifier import (
    VERIFY_MAX_CGEMV_ELEMS,
    verify_workload_result,
)

_EASY_TARGET = "f" * 64  # first nonce always meets target


def _sha_workload(wid: str = "w-sha", count: int = 1) -> Workload:
    header = bytes(range(76)) + (7).to_bytes(4, "little")
    return Workload(
        id=wid,
        kind=WorkloadKind.SHA256D_SCAN,
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        input={
            "header80_hex": header.hex(),
            "target_hex": _EASY_TARGET,
            "start_nonce": 7,
            "count": count,
        },
    )


class _CorruptingShaAdapter(CPUEmulatorAdapter):
    """Adapter double that returns a wrong digest_int — dishonest output."""

    id = "cpu-corrupt-double"

    def execute(self, workload: Workload):
        result = super().execute(workload)
        output = dict(result.output or {})
        hits = [dict(h) for h in output.get("hits") or []]
        if hits:
            hits[0]["digest_int"] = int(hits[0]["digest_int"]) + 1
            output["hits"] = hits
        else:
            output["checked"] = int(output.get("checked", 0)) + 1
        return replace(result, output=output)


class _ErrorAdapter(CPUEmulatorAdapter):
    """Adapter double reporting an honest non-ok status."""

    id = "cpu-error-double"

    def execute(self, workload: Workload):
        return self._result(
            workload,
            {"note": "injected failure"},
            time.time_ns(),
            status="error",
            error="injected failure",
        )


def test_sha256d_scan_recomputed_match_recorded(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "sha"
    )
    result = daemon.submit(_sha_workload())
    assert result.status == "ok"
    verification = result.receipt["verification"]
    assert verification["recomputed"] is True
    assert verification["verdict"] == "match"
    assert verification["verifier"] == "recompute:sha256d_scan:hashlib"


def test_corrupting_adapter_result_is_rejected(tmp_path) -> None:
    """Audit's exact check: adapter returns wrong digest_int -> rejected."""
    daemon = RuntimeDaemon(
        adapters=[_CorruptingShaAdapter()], store_dir=tmp_path / "corrupt"
    )
    result = daemon.submit(_sha_workload())
    assert result.status != "ok"
    assert result.status == "verification_failed"
    assert "digest_int" in (result.error or "")
    verification = result.receipt["verification"]
    assert verification["recomputed"] is True
    assert verification["verdict"] == "mismatch"
    # The dishonest attempt is ledgered as forensic evidence, not hidden.
    records = daemon.ledger.list_records()
    assert records[-1].result["status"] == "verification_failed"
    assert records[-1].receipt["verification"]["verdict"] == "mismatch"


def test_lucas_transform_exact_recompute(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "lucas"
    )
    result = daemon.submit(
        Workload(
            id="w-lucas",
            kind=WorkloadKind.LUCAS_TRANSFORM,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"n": 20},
        )
    )
    assert result.status == "ok"
    assert result.output["lucas"] == 15127
    assert result.receipt["verification"]["verdict"] == "match"


def test_cgemv_recomputed_with_recorded_tolerance(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "cgemv"
    )
    result = daemon.submit(
        Workload(
            id="w-cgemv",
            kind=WorkloadKind.CGEMV,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={
                "a": [[1.0, 0.0], [0.0, 2.0]],
                "x": [1.0, 1.0],
            },
        )
    )
    assert result.status == "ok"
    assert result.output["data"] == [[1.0, 0.0], [2.0, 0.0]]
    verification = result.receipt["verification"]
    assert verification["verdict"] == "match"
    assert verification["tolerance"] == {"rtol": 1e-9, "atol": 1e-12}


def test_cgemv_above_verify_bound_is_declared_unverified(tmp_path) -> None:
    """Inputs beyond the verify bound are labelled, never silently trusted."""
    n = VERIFY_MAX_CGEMV_ELEMS + 1  # (n, 1) complex matrix exceeds the bound
    mat = [[0.0]] * n
    x = [1.0]
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "cgemv-big"
    )
    result = daemon.submit(
        Workload(
            id="w-cgemv-big",
            kind=WorkloadKind.CGEMV,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"a": mat, "x": x},
        )
    )
    assert result.status == "ok"
    verification = result.receipt["verification"]
    assert verification["recomputed"] is False
    assert verification["verdict"] == "out_of_verify_bound"


def test_fold_output_verified_by_inverse_decode(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "fold"
    )
    result = daemon.submit(
        Workload(
            id="w-fold",
            kind=WorkloadKind.FOLD,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"payload_utf8": "pythia-fold-payload"},
        )
    )
    assert result.status == "ok"
    assert result.receipt["verification"]["verdict"] == "match"


def test_probe_kind_declared_unverifiable(tmp_path) -> None:
    """Kinds with no oracle are recorded honestly — not implied verified."""
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "probe"
    )
    result = daemon.submit(
        Workload(
            id="w-probe",
            kind=WorkloadKind.PROBE,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        )
    )
    assert result.status == "ok"
    verification = result.receipt["verification"]
    assert verification["recomputed"] is False
    assert verification["verdict"] == "unverifiable_kind"


def test_non_ok_result_skips_recompute(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[_ErrorAdapter()], store_dir=tmp_path / "err"
    )
    result = daemon.submit(_sha_workload())
    assert result.status == "error"
    verification = result.receipt["verification"]
    assert verification["recomputed"] is False
    assert verification["verdict"] == "skipped_not_ok"


def test_verifier_unit_entrypoint(tmp_path) -> None:
    """verify_workload_result works standalone for receipt-side callers."""
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "unit"
    )
    w = _sha_workload()
    result = daemon.submit(w)
    report = verify_workload_result(w, result)
    assert report["verdict"] == "match"
    assert report["recomputed"] is True


class _CorruptLucasAdapter(CPUEmulatorAdapter):
    id = "cpu-corrupt-lucas"

    def execute(self, workload: Workload):
        result = super().execute(workload)
        output = dict(result.output or {})
        if "lucas" in output:
            output["lucas"] = int(output["lucas"]) + 1
        return replace(result, output=output)


def test_lucas_corruption_rejected(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[_CorruptLucasAdapter()], store_dir=tmp_path / "lucas-corrupt"
    )
    result = daemon.submit(
        Workload(
            id="w-lucas-corrupt",
            kind=WorkloadKind.LUCAS_TRANSFORM,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"n": 10},
        )
    )
    assert result.status == "verification_failed"
    assert "lucas" in (result.error or "")


def _lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def test_pisot_transform_is_exact_integer_beyond_float_range(tmp_path) -> None:
    """n=2000 exceeds the float64 ceiling — pisot_nearest stays exact (L_n)."""
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "pisot"
    )
    result = daemon.submit(
        Workload(
            id="w-pisot",
            kind=WorkloadKind.PISOT_TRANSFORM,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={"n": 2000},
        )
    )
    assert result.status == "ok"
    assert result.output["pisot_nearest"] == _lucas(2000)
    assert result.output["phi_pow"] is None  # declared, never silent inf
    assert result.receipt["verification"]["verdict"] == "match"


def test_pisot_boundary_cases_match_literal_rounding(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "pisot-edge"
    )
    for n, expected in ((0, 1), (1, 2), (5, 11)):
        result = daemon.submit(
            Workload(
                id=f"w-pisot-{n}",
                kind=WorkloadKind.PISOT_TRANSFORM,
                execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
                input={"n": n},
            )
        )
        assert result.status == "ok"
        assert result.output["pisot_nearest"] == expected
        assert result.receipt["verification"]["verdict"] == "match"


def test_phi_transform_refuses_beyond_float64_domain(tmp_path) -> None:
    """n>1474 is outside the declared numeric domain — typed refusal, no crash."""
    from chronus.virtual_igpu.adapters import AdapterUnavailable

    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()], store_dir=tmp_path / "phi"
    )
    with pytest.raises(AdapterUnavailable, match="float64"):
        daemon.submit(
            Workload(
                id="w-phi-oob",
                kind=WorkloadKind.PHI_TRANSFORM,
                execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
                input={"n": 2000},
            )
        )
