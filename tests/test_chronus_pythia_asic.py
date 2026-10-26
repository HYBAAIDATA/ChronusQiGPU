"""PYTHIA specialization preserves the original ordered scan and receipt contracts."""

import hashlib
import pytest
from chronus.virtual_igpu.abi import Workload, WorkloadKind
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter, ChronusSoftwareFabricAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon
from chronus.virtual_igpu.verifier import verify_workload_result
from chronus.virtual_igpu.pythia_asic import GOLDEN_STRIDE


@pytest.mark.parametrize("count", [1, 8, 4097])
def test_prepared_no_hit_streams_exactly_and_reuses_one_midstate(tmp_path, count):
    value = {
        "header80_hex": bytes(range(80)).hex(),
        "target_hex": "00" * 32,
        "nonces": [(1337 + i * GOLDEN_STRIDE) & 0xFFFFFFFF for i in range(count)],
    }
    workload = Workload(
        id="scan",
        tenant="pythia",
        kind="sha256d_scan",
        input=value,
        execution_policy="standalone_software",
    )
    runtime = RuntimeDaemon(adapters=[ChronusSoftwareFabricAdapter()], store_dir=tmp_path)
    result = runtime.submit(workload)
    reference = CPUEmulatorAdapter().execute(workload)
    assert result.output["hits"] == reference.output["hits"] == []
    assert result.output["checked"] == reference.output["checked"] == count
    assert result.output["compression_blocks_executed"] == 1 + 2 * count
    assert result.output["first_blocks_prepared"] == 1
    assert result.receipt["verification"]["verdict"] == "match"
    assert result.actual_adapter_id == "chronus-software-fabric"
    assert result.attestation["kind"] == "software"


def test_prepared_winner_uses_submitted_order_and_independent_host_oracle(tmp_path):
    prefix = bytes(range(76))
    nonces = [99, 3, 11, 0, 17]
    digests = [
        hashlib.sha256(hashlib.sha256(prefix + n.to_bytes(4, "little")).digest()).digest()
        for n in nonces
    ]
    target = min(int.from_bytes(d, "little") for d in digests)
    index = next(i for i, d in enumerate(digests) if int.from_bytes(d, "little") == target)
    request = Workload(
        id="winner",
        kind=WorkloadKind.SHA256D_SCAN,
        input={"prefix_hex": prefix.hex(), "target": target, "nonces": nonces},
    )
    result = ChronusSoftwareFabricAdapter().execute(request)
    assert result.output["checked"] == index + 1
    assert result.output["hits"][0]["nonce"] == nonces[index]
    assert verify_workload_result(request, result)["verdict"] == "match"
    result.output["checked"] += 1
    assert verify_workload_result(request, result)["verdict"] == "mismatch"


def test_specialized_hasher_does_not_call_software_a_physical_gpu(tmp_path, monkeypatch):
    from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher
    from chronus.mla1517_platform.python import runtime_config

    monkeypatch.setattr(runtime_config, "load", lambda: {"execution": {"mode": "independent"}})
    runtime = RuntimeDaemon(adapters=[ChronusSoftwareFabricAdapter()], store_dir=tmp_path)
    hasher = ChronusVirtualIGPUHasher(client=runtime)
    hasher.self_check()
    assert hasher.last_result["output"]["asic_like"]
    assert not hasher.physical_device_executed
    assert hasher.last_verification["status"] == "passed"


def test_prepared_accounting_is_part_of_verification():
    workload = Workload(
        id="accounting",
        kind="sha256d_scan",
        input={
            "header80_hex": bytes(range(80)).hex(),
            "target_hex": "ff" * 32,
            "nonces": [7, 9, 11],
        },
    )
    result = ChronusSoftwareFabricAdapter().execute(workload)
    result.output["sha256d_evaluations"] = 3
    assert verify_workload_result(workload, result)["verdict"] == "mismatch"


def test_pythia_opencl_cpu_executes_gold_and_recovers_when_available(tmp_path):
    cl = pytest.importorskip("pyopencl")
    from chronus.virtual_igpu.pythia_asic import PythiaMiningAdapter

    try:
        platforms = cl.get_platforms()
    except cl.LogicError as exc:
        if exc.code == -1001:
            pytest.skip("optional OpenCL ICD is not installed")
        raise
    if not any(p.get_devices(device_type=cl.device_type.CPU) for p in platforms):
        pytest.skip("optional OpenCL CPU device is not installed")
    adapter = PythiaMiningAdapter("opencl_cpu")
    runtime = RuntimeDaemon(adapters=[adapter], store_dir=tmp_path)
    for iteration in range(2):
        nonces = [(1337 + i * GOLDEN_STRIDE) & 0xFFFFFFFF for i in range(8)]
        value = {"header80_hex": bytes(range(80)).hex(), "target_hex": "ff" * 32, "nonces": nonces}
        workload = Workload(
            id=str(iteration),
            kind="sha256d_scan",
            input=value,
            execution_policy="standalone_software",
        )
        result = runtime.submit(workload)
        assert result.receipt["verification"]["verdict"] == "match"
        assert result.output["checked"] == 1 and result.output["sha256d_evaluations"] == 8
        assert result.output["golden_launches"] == 1
        assert result.attestation["kind"] == "software"
        runtime.recover()
