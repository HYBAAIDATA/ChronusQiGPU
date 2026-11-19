"""The five modules wired by the 2026-11-18 audit, exercised through their
production execution paths from an installed wheel in a clean venv.

| Module | Production path exercised here |
|---|---|
| chronus.durable | an evaluator process appends receipts, restarts, resumes after signed replay, appends again; the bundle is then checked by the installed ``chronus-verify-chain`` |
| chronus.verify_cli | installed console script ``chronus-verify-chain`` (exit 0 / 2) |
| chronus.crypto.verify_bundle | installed console script ``chronus-verify-bundle`` (exit 0 / 1) |
| chronus.service.production_hr_api | installed console script ``chronus-hr-api`` starts a real uvicorn server; routes are called over TCP |
| chronus.math.padovan_folded | library API of the installed package (it has no runtime caller; see docs/audits) |
"""
from __future__ import annotations

import json
import socket
import subprocess
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tests_installed.conftest import clean_env

pytestmark = pytest.mark.real


def _py(venv_bin, code: str, cwd: Path) -> str:
    out = subprocess.run([str(venv_bin("python")), "-c", textwrap.dedent(code)], cwd=cwd, env=clean_env(),
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_installed_package_comes_from_the_wheel_not_the_source_tree(venv_bin, tmp_path):
    location = _py(venv_bin, "import chronus; print(chronus.__file__)", tmp_path).strip()
    assert "site-packages" in location
    assert not Path(location).resolve().is_relative_to(Path(__file__).resolve().parents[1] / "src")
    for script in ("chronus-verify-chain", "chronus-verify-bundle", "chronus-hr-api"):
        assert venv_bin(script).exists(), script


_SIGNER = """
import json, sys
from pathlib import Path
from chronus.crypto.signers import DualSigner, Ed25519Signer, MlDsa65Signer, ml_dsa_available
if not ml_dsa_available():
    sys.exit("ML-DSA-65 unavailable in the installed cryptography wheel")
"""


def _evaluator_run(venv_bin, work: Path, payloads: list[int], resume: bool) -> None:
    """One evaluator process: (resume and) append receipts durably, export the bundle."""
    _py(venv_bin, _SIGNER + f"""
from chronus.chain import Chain
from chronus.durable import DurableChain
from chronus.journal import Journal
work = Path({str(work)!r})
from cryptography.hazmat.primitives import serialization as ser
keys = work / "keys"
if keys.exists():
    # A restarted evaluator reloads its own keys (in production: from custody).
    load = lambda name: ser.load_pem_private_key((keys / name).read_bytes(), None)
    signer = DualSigner(Ed25519Signer("Ed25519", "inner", load("inner.pem")),
                        MlDsa65Signer("ML-DSA-65", "outer", load("outer.pem")))
else:
    signer = DualSigner(Ed25519Signer.generate("inner"), MlDsa65Signer.generate("outer"))
    keys.mkdir()
    for name, s in (("inner.pem", signer.inner), ("outer.pem", signer.outer)):
        (keys / name).write_bytes(s._key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8,
                                                       ser.NoEncryption()))
    (work / "inner.pk").write_text(signer.inner.public_bytes().hex())
    (work / "outer.pk").write_text(signer.outer.public_bytes().hex())
bundle = work / "bundle"
bundle.mkdir(exist_ok=True)
with Journal(work / "journal") as journal:
    durable = DurableChain(journal, Chain(signer))
    if {resume!r}:
        durable.resume(signer.inner.public_bytes(), signer.outer.public_bytes())
    for n in {payloads!r}:
        receipt = durable.append({{"job": n}})
        (bundle / f"{{receipt['seq']:04d}}.json").write_text(json.dumps(receipt))
""", work)


def _verify_chain(venv_bin, work: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(venv_bin("chronus-verify-chain")), str(work / "bundle"),
                           "--inner-pk", str(work / "inner.pk"), "--outer-pk", str(work / "outer.pk")],
                          cwd=work, env=clean_env(), capture_output=True, text=True, timeout=120)


def test_durable_chain_survives_restart_and_is_verified_by_the_installed_cli(venv_bin, tmp_path):
    _evaluator_run(venv_bin, tmp_path, [1, 2], resume=False)
    _evaluator_run(venv_bin, tmp_path, [3], resume=True)  # a new process: signed replay, then append
    ok = _verify_chain(venv_bin, tmp_path)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout) == {"status": "PASS", "receipts": 3}

    receipt = json.loads((tmp_path / "bundle" / "0001.json").read_text())
    receipt["payload"]["job"] = 99
    (tmp_path / "bundle" / "0001.json").write_text(json.dumps(receipt))
    bad = _verify_chain(venv_bin, tmp_path)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)["status"] == "FAIL"


def test_installed_verify_bundle_accepts_valid_and_rejects_tampered(venv_bin, tmp_path):
    _py(venv_bin, _SIGNER + f"""
work = Path({str(tmp_path)!r})
signer = DualSigner(Ed25519Signer.generate("inner"), MlDsa65Signer.generate("outer"))
message = b"chronus receipt body"
sigs = signer.sign(message)
(work / "bundle.json").write_text(json.dumps({{"message_hex": message.hex(),
    "signatures": {{k: v.hex() for k, v in sigs.items()}}}}))
(work / "keys.json").write_text(json.dumps({{"Ed25519": signer.inner.public_bytes().hex(),
    "ML-DSA-65": signer.outer.public_bytes().hex()}}))
""", tmp_path)
    cmd = [str(venv_bin("chronus-verify-bundle")), "--bundle", str(tmp_path / "bundle.json"),
           "--public-keys", str(tmp_path / "keys.json")]
    ok = subprocess.run(cmd, env=clean_env(), capture_output=True, text=True, timeout=120)
    assert (ok.returncode, ok.stdout.strip()) == (0, "VALID"), ok.stderr
    bundle = json.loads((tmp_path / "bundle.json").read_text())
    bundle["message_hex"] = b"other body".hex()
    (tmp_path / "bundle.json").write_text(json.dumps(bundle))
    bad = subprocess.run(cmd, env=clean_env(), capture_output=True, text=True, timeout=120)
    assert bad.returncode == 1
    assert bad.stdout.startswith("INVALID_OR_UNAVAILABLE")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _call(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"},
                                     method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def test_hr_api_console_script_serves_routes_from_a_real_server_process(venv_bin, tmp_path):
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen([str(venv_bin("chronus-hr-api")), "--port", str(port)], cwd=tmp_path,
                              env=clean_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.monotonic() + 60
        while True:
            assert server.poll() is None, server.stdout.read()
            try:
                status, health = _call(base, "/health")
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.25)
        assert status == 200
        status, init = _call(base, "/api/v1/tensor/init", {})
        assert (status, init["status"]) == (200, "INITIALIZED")
        status, norm = _call(base, "/api/v1/tensor/optimize-query", {"query_payload": {"operation": "norm"}})
        assert status == 200 and norm["result_norm_squared"] == pytest.approx(1.0)
        status, _ = _call(base, "/api/v1/causal/analyze", {"variable_x": "a", "variable_y": "b",
                          "observational_correlation": 0.4, "confounding_indicators": {"z": 0.2}})
        assert status == 200
        status, _ = _call(base, "/api/v1/causal/counterfactual", {"factual_features": {"x": 1.0, "y": 2.0},
                          "intervention_feature": "x", "target_value": 3.0})
        assert status == 200
        # The tensor layer refuses this contraction objective; the server must refuse, not crash.
        status, attrition = _call(base, "/api/v1/hr/attrition-risk", {"employee_id": "e1"})
        assert status == 501 and "contraction objective" in attrition["detail"]
    finally:
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


def test_padovan_fold_record_round_trips_in_the_installed_package(venv_bin, tmp_path):
    out = _py(venv_bin, """
from chronus.math import padovan_folded as pf
s = 66307 * 12345 + 17
record = pf.fold_padovan_index(s, flags=0x0A0B)
exact_s, state, flags = pf.unfold_padovan_record(record)
print(len(record), exact_s == s, state == pf.padovan_state(s), flags,
      pf.padovan_matrix_power(pf.PADOVAN_PERIOD) == ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
""", tmp_path)
    assert out.split() == ["16", "True", "True", str(0x0A0B), "True"]
