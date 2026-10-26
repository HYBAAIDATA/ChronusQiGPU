"""Execute native Chronus, then challenge its exactness and authority boundaries."""
from dataclasses import replace
import pytest
from chronus.virtual_igpu.abi import Workload, WorkloadKind
from chronus.virtual_igpu.adapters import ChronusSoftwareFabricAdapter, AdapterUnavailable
from chronus.virtual_igpu.runtime import RuntimeDaemon, AdmissionDenied
from chronus.virtual_igpu.verifier import verify_workload_result


def request(wid="native", **kw):
    return Workload(id=wid, kind=WorkloadKind.LUCAS_TRANSFORM,
                    execution_policy="standalone_software", input={"n": 10}, **kw)


@pytest.fixture
def native(tmp_path):
    return RuntimeDaemon(adapters=[ChronusSoftwareFabricAdapter()], store_dir=tmp_path)


@pytest.mark.parametrize("kind", [WorkloadKind.LUCAS_TRANSFORM, WorkloadKind.PISOT_TRANSFORM])
@pytest.mark.parametrize("n", [True, False, 1.5, "10", None])
def test_exact_index_rejects_lossy_coercion(native, kind, n):
    w = Workload(id="invalid", kind=kind, execution_policy="standalone_software", input={"n": n})
    with pytest.raises(AdapterUnavailable, match="integer"):
        native.submit(w)


@pytest.mark.parametrize("value", [123.5, 123.0, "123"])
def test_independent_oracle_rejects_noninteger_lucas(native, value):
    w = request()
    result = native.submit(w)
    forged = replace(result, output={**result.output, "lucas": value})
    assert verify_workload_result(w, forged)["verdict"] == "mismatch"


def test_replay_rechecks_authority(native):
    admitted = [True]
    native.admission_policy = lambda w: admitted[0]
    w = request(idempotency_key="once")
    assert native.submit(w).status == "ok"
    admitted[0] = False
    with pytest.raises(AdmissionDenied):
        native.submit(w)


def test_mutated_request_cannot_replay_stale_content_hash(native):
    w = request(idempotency_key="once")
    native.submit(w)
    w.input["n"] = 20
    with pytest.raises(ValueError, match="content_hash"):
        native.submit(w)


def test_replay_receipt_is_not_caller_mutable(native):
    w = request(idempotency_key="once")
    first = native.submit(w)
    first.output["lucas"] = -999
    second = native.submit(w)
    assert second.output["lucas"] == 123
    second.output["lucas"] = -123
    assert native.submit(w).output["lucas"] == 123


def test_tenants_have_independent_idempotency_namespaces(native):
    a = native.submit(request(tenant="alice", idempotency_key="same-key"))
    b = native.submit(request(tenant="bob", idempotency_key="same-key"))
    assert a.status == b.status == "ok"
    assert a.receipt["attempt_id"] != b.receipt["attempt_id"]


@pytest.mark.parametrize("n", [0, 1, 2, 10, 12, 15, 18, 20, 31, 50, 76, 2000, 10000])
def test_native_exact_lucas_matches_independent_fibonacci_identity(native, n):
    w = request(wid=f"lucas-{n}")
    w.input = {"n": n}
    # Construct a new canonical request rather than retaining an old content hash.
    w = Workload(id=w.id, kind=w.kind, execution_policy=w.execution_policy, input=w.input)
    result = native.submit(w)
    f0, f1 = 0, 1
    for _ in range(n):
        f0, f1 = f1, f0 + f1
    assert result.output["lucas"] == 2 * f1 - f0
    assert result.output["lucas"] ** 2 - 5 * f0 ** 2 == 4 * (-1) ** n
    assert result.receipt["verification"]["verdict"] == "match"
    assert result.actual_adapter_id == "chronus-software-fabric"
    assert result.hardware_rooted is False
