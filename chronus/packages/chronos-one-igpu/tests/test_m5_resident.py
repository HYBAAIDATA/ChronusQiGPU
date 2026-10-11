"""Actual exact resident work; descriptor arithmetic is never device evidence."""
import copy
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import replace

import pytest
from chronos_one_igpu import OneIGPU, ResidentConfig
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.igpu.m5 import M5ResidentRuntime, model_digest
from chronos_one_igpu.igpu.resident import canonical
from chronos_one_igpu.m5_ultra import m5_ultra_fabric, elevate_pads


@pytest.mark.parametrize("units", [80, 800, 8000])
def test_combined_model_and_actual_exact_work(units):
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident(ResidentConfig(host_binding="native", virtual_units=units))
        manifest = session.manifest()
        assert manifest["model_digest"] == model_digest(m5_ultra_fabric())
        assert manifest["model_is_execution_evidence"] is False
        assert manifest["resident"]["mode"] == "independent"
        assert manifest["resident"]["scaling"]["virtual_units"] == units
        assert manifest["resident"]["physical_compute_units"] is None
        payload = {"rungs": [1, 2, 10, 18, 31]}
        receipt = session.execute("lucas", payload)
        assert session.verify(receipt, payload)
        assert receipt["execution"]["completed_items"] == 5
        assert receipt["execution"]["hardware_throughput_multiplier"] is None
        assert all(tile["backend"] == "cpu_reference" for tile in receipt["execution"]["completed_tiles"])


def test_model_identity_survives_fresh_process():
    # -I: neither repo root nor PYTHONPATH can supply the imported package.
    cmd = [sys.executable, "-I", "-c", "from chronos_one_igpu.m5_ultra import m5_ultra_fabric; from chronos_one_igpu.igpu.m5 import model_digest; print(model_digest(m5_ultra_fabric()))"]
    digest = subprocess.check_output(cmd, text=True).strip()
    assert digest == model_digest(m5_ultra_fabric())


def test_custom_elevation_has_separate_model_identity():
    model = elevate_pads(10, topology="mesh")
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident(model=model)
        assert session.manifest()["model_digest"] == model_digest(model)
        assert session.manifest()["model_digest"] != model_digest(m5_ultra_fabric())
        assert session.manifest()["resident"]["physical_compute_units"] is None


def test_cannot_promote_model_into_measurement():
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        with pytest.raises(ValueError, match="not execution evidence"):
            gpu.m5_resident(model=replace(m5_ultra_fabric(), measured_by_chronus=True))
        with pytest.raises(TypeError):
            gpu.m5_resident(model={"gpu_cores": 8000})


def test_manifest_mutation_does_not_mutate_session():
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident()
        first = session.manifest()
        first["model"].clear()
        assert session.manifest()["model"]


@pytest.mark.parametrize("field", ["model_digest", "model_is_execution_evidence", "schema"])
def test_resealed_identity_substitution_rejected(field):
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident()
        payload = {"rungs": [10]}
        receipt = session.execute("lucas", payload)
        receipt[field] = True if field == "model_is_execution_evidence" else "substituted"
        body = dict(receipt); body.pop("receipt_digest")
        receipt["receipt_digest"] = hashlib.sha256(canonical(body)).hexdigest()
        with pytest.raises(ValueError):
            session.verify(receipt, payload)


def test_independent_result_check_rejects_resealed_corruption():
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident()
        payload = {"rungs": [10]}
        receipt = session.execute("lucas", payload)
        inner = receipt["execution"]
        inner["completed_tiles"][0]["output"][0] += 1
        body = dict(inner); body.pop("receipt_digest")
        inner["receipt_digest"] = hashlib.sha256(canonical(body)).hexdigest()
        body = dict(receipt); body.pop("receipt_digest")
        receipt["receipt_digest"] = hashlib.sha256(canonical(body)).hexdigest()
        with pytest.raises(ValueError, match="host verification"):
            session.verify(receipt, payload)


def test_required_physical_execution_never_uses_model_cores():
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident()
        with pytest.raises(BackendAbsent):
            session.execute("lucas", {"rungs": [10]}, require_host_gpu=True)


def test_explicit_metal_fails_without_apple_host():
    if platform.system() == "Darwin":
        pytest.skip("Linux negative-binding test; device qualification is separate")
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        with pytest.raises(BackendAbsent):
            gpu.m5_resident(ResidentConfig(host_binding="metal"))


def test_receipt_restart_replay(tmp_path):
    payload = {"rungs": [1, 10, 31]}
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident()
        receipt = session.execute("lucas", payload)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({"receipt": receipt, "payload": payload}))
    code = """import json,sys
from chronos_one_igpu import OneIGPU
x=json.load(open(sys.argv[1]))
with OneIGPU(working_width=32,prime_rom_limit=1000) as gpu:
 assert gpu.m5_resident().verify(x['receipt'],x['payload'])
print('REPLAY_VERIFIED')
"""
    assert "REPLAY_VERIFIED" in subprocess.check_output([sys.executable, "-I", "-c", code, str(path)], text=True)


def test_cli_installed_name_and_m5_manifest():
    version = json.loads(subprocess.check_output([sys.executable, "-I", "-m", "chronos_one_igpu.release_cli", "version"], text=True))
    from importlib.metadata import version as installed_version
    assert version["version"] == installed_version("hyba-chronos-one-igpu")
    result = json.loads(subprocess.check_output([sys.executable, "-I", "-m", "chronos_one_igpu.release_cli", "m5-info"], text=True))
    assert result["model_is_execution_evidence"] is False
    assert result["resident"]["mode"] == "independent"


def test_doctor_does_not_require_reference_approval():
    result = json.loads(subprocess.check_output([sys.executable, "-I", "-m", "chronos_one_igpu.release_cli", "doctor"], text=True))
    assert result["passed"]
    assert "not production certification" in result["scope"]
