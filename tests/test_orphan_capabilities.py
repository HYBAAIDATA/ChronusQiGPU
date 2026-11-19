"""Executable coverage for capabilities the 2026-11-18 wiring audit found orphaned.

Each module here was imported by nothing in src/, tests/ or scripts/. They are
kept because they carry a documented, legitimate capability; these tests wire
them into the suite so regressions are caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronus import verify_cli
from chronus.chain import GENESIS, Chain, ChainBroken, receipt_hash
from chronus.crypto import verify_bundle
from chronus.crypto.signers import DualSigner, Ed25519Signer, MlDsa65Signer, ml_dsa_available
from chronus.durable import DurableChain
from chronus.journal import Journal
from chronus.math import padovan_folded as pf

pytestmark = pytest.mark.real

requires_ml_dsa = pytest.mark.skipif(not ml_dsa_available(), reason="ML-DSA-65 unavailable in this OpenSSL stack")


def _signer() -> DualSigner:
    return DualSigner(Ed25519Signer.generate("inner"), MlDsa65Signer.generate("outer"))


def _write_keys(tmp_path: Path, signer: DualSigner) -> tuple[Path, Path]:
    inner, outer = tmp_path / "inner.pk", tmp_path / "outer.pk"
    inner.write_text(signer.inner.public_bytes().hex())
    outer.write_text(signer.outer.public_bytes().hex())
    return inner, outer


@requires_ml_dsa
def test_durable_chain_appends_and_resumes_after_signed_replay(tmp_path):
    signer = _signer()
    with Journal(tmp_path / "journal") as journal:
        durable = DurableChain(journal, Chain(signer))
        first = durable.append({"job": 1})
        second = durable.append({"job": 2})
    assert first["prev_hash"] == GENESIS
    assert second["prev_hash"] == receipt_hash(first)

    with Journal(tmp_path / "journal") as journal:
        resumed = DurableChain(journal, Chain(signer))
        resumed.resume(signer.inner.public_bytes(), signer.outer.public_bytes())
        third = resumed.append({"job": 3})
    assert third["seq"] == 2
    assert third["prev_hash"] == receipt_hash(second)


@requires_ml_dsa
def test_durable_chain_refuses_to_resume_from_foreign_keys(tmp_path):
    signer, other = _signer(), _signer()
    with Journal(tmp_path / "journal") as journal:
        DurableChain(journal, Chain(signer)).append({"job": 1})
    with Journal(tmp_path / "journal") as journal:
        resumed = DurableChain(journal, Chain(signer))
        with pytest.raises(ChainBroken):
            resumed.resume(other.inner.public_bytes(), other.outer.public_bytes())


@requires_ml_dsa
def test_verify_chain_cli_exit_codes(tmp_path, capsys):
    signer = _signer()
    chain = Chain(signer)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    prev = GENESIS
    for seq in range(3):
        receipt = chain.seal(seq, prev, {"n": seq})
        (bundle / f"{seq:04d}.json").write_text(json.dumps(receipt))
        prev = receipt_hash(receipt)
    inner, outer = _write_keys(tmp_path, signer)
    args = [str(bundle), "--inner-pk", str(inner), "--outer-pk", str(outer)]

    assert verify_cli.main(args) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "PASS", "receipts": 3}

    tampered = json.loads((bundle / "0001.json").read_text())
    tampered["payload"]["n"] = 99
    (bundle / "0001.json").write_text(json.dumps(tampered))
    assert verify_cli.main(args) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"

    empty = tmp_path / "empty"
    empty.mkdir()
    assert verify_cli.main([str(empty), "--inner-pk", str(inner), "--outer-pk", str(outer)]) == 2


@requires_ml_dsa
def test_verify_bundle_cli_accepts_valid_and_rejects_tampered(tmp_path, capsys):
    signer = _signer()
    message = b"chronus receipt body"
    signatures = signer.sign(message)
    bundle = {"message_hex": message.hex(), "signatures": {k: v.hex() for k, v in signatures.items()}}
    keys = {"Ed25519": signer.inner.public_bytes().hex(), "ML-DSA-65": signer.outer.public_bytes().hex()}
    bundle_path, keys_path = tmp_path / "bundle.json", tmp_path / "keys.json"
    bundle_path.write_text(json.dumps(bundle))
    keys_path.write_text(json.dumps(keys))

    assert verify_bundle.main(["--bundle", str(bundle_path), "--public-keys", str(keys_path)]) == 0
    assert capsys.readouterr().out.strip() == "VALID"

    bundle["message_hex"] = b"other body".hex()
    bundle_path.write_text(json.dumps(bundle))
    assert verify_bundle.main(["--bundle", str(bundle_path), "--public-keys", str(keys_path)]) == 1
    assert capsys.readouterr().out.startswith("INVALID_OR_UNAVAILABLE")


def _companion_power_reference(s: int) -> tuple[int, int, int]:
    """Direct recurrence P(n+3) = P(n+1) + P(n) mod 257 from (1, 1, 1)."""
    a, b, c = 1, 1, 1
    for _ in range(s):
        a, b, c = b, c, (a + b) % pf.MOD
    return a, b, c


def test_padovan_polynomial_is_irreducible_over_f257():
    assert all((x**3 - x - 1) % pf.MOD for x in range(pf.MOD))


def test_padovan_period_is_exact_minimal_period():
    identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert pf.PADOVAN_PERIOD == 257**2 + 257 + 1 == 61 * 1087
    assert pf.padovan_matrix_power(pf.PADOVAN_PERIOD) == identity
    # Minimal: no proper divisor of 61 * 1087 closes the cycle.
    for d in (1, 61, 1087):
        assert pf.padovan_matrix_power(d) != identity


@pytest.mark.parametrize("s", [0, 1, 2, 3, 257, 258, 1000, 66306, 66307, 66308, 200_000])
def test_padovan_state_matches_direct_recurrence(s):
    assert pf.padovan_state(s) == _companion_power_reference(s % pf.PADOVAN_PERIOD)


@pytest.mark.parametrize("s,high", [(0, 0), (66306, 0), (66307 * 12345 + 17, 0), (((1 << 64) + 5) * 66307 + 99, 1)])
def test_padovan_fold_unfold_is_bijective(s, high):
    record = pf.fold_padovan_index(s, flags=0x0A0B)
    assert len(record) == 16
    exact_s, state, flags = pf.unfold_padovan_record(record, high_q_limbs=high)
    assert exact_s == s
    assert state == pf.padovan_state(s)
    assert flags == 0x0A0B


def test_padovan_rejects_invalid_inputs():
    for bad in (-1, True, 1.5):
        with pytest.raises(ValueError):
            pf.padovan_state(bad)
    with pytest.raises(ValueError):
        pf.fold_padovan_index(1, flags=1 << 16)


def test_production_hr_api_v1_endpoints_execute_or_refuse_explicitly():
    from fastapi.testclient import TestClient

    from chronus.service.production_hr_api import app

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    init = client.post("/api/v1/tensor/init", json={})
    assert init.status_code == 200 and init.json()["status"] == "INITIALIZED"
    norm = client.post("/api/v1/tensor/optimize-query", json={"query_payload": {"operation": "norm"}})
    assert norm.status_code == 200
    assert norm.json()["result_norm_squared"] == pytest.approx(1.0)
    causal = client.post(
        "/api/v1/causal/analyze",
        json={"variable_x": "a", "variable_y": "b", "observational_correlation": 0.4, "confounding_indicators": {"z": 0.2}},
    )
    assert causal.status_code == 200
    counterfactual = client.post(
        "/api/v1/causal/counterfactual",
        json={"factual_features": {"x": 1.0, "y": 2.0}, "intervention_feature": "x", "target_value": 3.0},
    )
    assert counterfactual.status_code == 200
    # Index-targeted contraction is refused by the tensor layer, so the
    # endpoint must refuse rather than crash or fabricate a score.
    attrition = client.post("/api/v1/hr/attrition-risk", json={"employee_id": "e1"})
    assert attrition.status_code == 501
    assert "contraction objective" in attrition.json()["detail"]
