"""Build executable product-gate evidence for a declared release profile.

The software-base profile qualifies the distributable software itself. It does
not imply physical accelerator performance, external customer key custody,
multi-region HA, customer deployment, or regulatory accreditation.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from chronus.chain import Chain, ChainBroken, GENESIS, receipt_hash, verify_chain
from chronus.core.qualification import MANDATORY
from chronus.crypto.signers import (
    DualSigner,
    Ed25519Signer,
    MlDsa65Signer,
    SignerUnavailable,
)
from chronus.service.api import claims as claims_api
from chronus.triad import ProductionTriad


def _gate(status: str, detail: str, **evidence) -> dict:
    return {"status": status, "detail": detail, "evidence": evidence}


def _receipt_fixture() -> tuple[list[dict], bytes, bytes]:
    inner = Ed25519Signer.generate("qualification-ed25519")
    outer = MlDsa65Signer.generate("qualification-ml-dsa-65")
    chain = Chain(DualSigner(inner=inner, outer=outer))
    receipts: list[dict] = []
    previous = GENESIS
    for sequence in range(3):
        receipt = chain.seal(
            sequence,
            previous,
            {"kind": "qualification", "sequence": sequence},
        )
        receipts.append(receipt)
        previous = receipt_hash(receipt)
    return receipts, inner.public_bytes(), outer.public_bytes()


def verify_signing(receipts: list[dict], inner_pk: bytes, outer_pk: bytes) -> dict:
    try:
        verify_chain(receipts, inner_pk, outer_pk)
    except (ChainBroken, SignerUnavailable, ValueError) as exc:
        return _gate("UNQUALIFIED", f"dual-signature verification unavailable: {exc}")
    return _gate(
        "PASS",
        "Ed25519 + ML-DSA-65 receipt chain verified",
        algorithm="ML-DSA-65",
        implementation="cryptography/OpenSSL",
        fips_module_validation_claimed=False,
    )


def verify_receipt_integrity(receipts: list[dict], inner_pk: bytes, outer_pk: bytes) -> dict:
    changed = json.loads(json.dumps(receipts))
    changed[0]["payload"]["sequence"] = 999
    try:
        verify_chain(changed, inner_pk, outer_pk)
    except ChainBroken:
        return _gate("PASS", "payload tampering rejected by signed receipt chain")
    except SignerUnavailable as exc:
        return _gate("UNQUALIFIED", f"signature provider unavailable: {exc}")
    return _gate("FAIL", "tampered receipt chain was accepted")


def verify_replay(receipts: list[dict], inner_pk: bytes, outer_pk: bytes) -> dict:
    reordered = list(receipts)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    try:
        verify_chain(reordered, inner_pk, outer_pk)
    except ChainBroken:
        return _gate("PASS", "receipt reordering rejected")
    except SignerUnavailable as exc:
        return _gate("UNQUALIFIED", f"signature provider unavailable: {exc}")
    return _gate("FAIL", "reordered receipt chain was accepted")


def verify_claims_register() -> dict:
    try:
        claims_api.reset_cache()
        audit = claims_api.load_audit()
    except Exception as exc:
        return _gate("FAIL", f"claim audit failed validation: {type(exc).__name__}: {exc}")
    supported = [claim.id for claim in audit.claims if claim.disposition == "supported"]
    unverified = [claim.id for claim in audit.claims if claim.disposition == "unverified"]
    withdrawn = [claim.id for claim in audit.claims if claim.disposition == "withdrawn"]
    return _gate(
        "PASS",
        "claim register parsed under fail-closed evidence/reviewer rules",
        reviewed_at=audit.reviewed_at.isoformat(),
        supported_claims=supported,
        unverified_claims=unverified,
        withdrawn_claims=withdrawn,
        open_blockers=[b.id for b in audit.blockers if b.status != "closed"],
    )


def verify_base_custody() -> dict:
    try:
        with tempfile.TemporaryDirectory(prefix="chronus-product-gate-") as folder:
            path = os.path.join(folder, "triad.sqlite3")
            first = ProductionTriad(path)
            receipt = first.put("qualification", b"chronus-production-custody-gate")
            first_value = first.materialise(receipt)
            reopened = ProductionTriad(path)
            second_value = reopened.materialise(receipt)
            continuity = reopened.theseus.verify_journal_continuity("qualification")
            evidence = reopened.theseus.evidence()
            if (
                first_value != b"chronus-production-custody-gate"
                or second_value != first_value
                or not continuity
                or evidence.get("integrity") != "PASS"
                or evidence.get("durable") is not True
            ):
                return _gate("FAIL", "durable custody/restart verification did not satisfy contract")
    except Exception as exc:
        return _gate("FAIL", f"durable custody verification failed: {type(exc).__name__}: {exc}")
    return _gate(
        "PASS",
        "THESEUS durable local custody survived fresh reopen with journal continuity",
        authority="THESEUS",
        mechanism="sqlite-wal",
        scope="software-base",
        external_customer_key_custody=False,
        multi_region=False,
    )


def build(profile: str) -> dict:
    if profile != "software-base":
        return {
            "schema": "chronus-product-gates-v1",
            "deployment_profile": profile,
            "commit": os.environ.get("GITHUB_SHA", "UNAVAILABLE"),
            "run_id": os.environ.get("GITHUB_RUN_ID", "UNAVAILABLE"),
            "gates": {gate: "UNQUALIFIED" for gate in MANDATORY},
            "gate_details": {
                gate: _gate(
                    "UNQUALIFIED",
                    f"profile {profile!r} requires a profile-specific verifier/receipt",
                )
                for gate in MANDATORY
            },
            "facts": {
                "profile": {
                    "name": profile,
                    "verified": False,
                    "software_base_only": False,
                }
            },
            "status": "UNQUALIFIED",
        }

    try:
        receipts, inner_pk, outer_pk = _receipt_fixture()
        results = {
            "CO-SIGN": verify_signing(receipts, inner_pk, outer_pk),
            "RS-RECEIPT": verify_receipt_integrity(receipts, inner_pk, outer_pk),
            "RS-REPLAY": verify_replay(receipts, inner_pk, outer_pk),
            "FN-CLAIMS": verify_claims_register(),
            "FN-CUSTODY": verify_base_custody(),
        }
    except SignerUnavailable as exc:
        results = {
            gate: _gate("UNQUALIFIED", f"required signing provider unavailable: {exc}")
            for gate in MANDATORY
        }

    gates = {gate: results[gate]["status"] for gate in MANDATORY}
    all_pass = all(status == "PASS" for status in gates.values())
    return {
        "schema": "chronus-product-gates-v1",
        "deployment_profile": "software-base",
        "commit": os.environ.get("GITHUB_SHA", "UNAVAILABLE"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "UNAVAILABLE"),
        "status": "PASS" if all_pass else "UNQUALIFIED",
        "gates": gates,
        "gate_details": results,
        "facts": {
            "profile": {
                "name": "software-base",
                "verified": all_pass,
                "software_base_only": True,
            },
            "post_quantum_signer": {
                "algorithm": "ML-DSA-65",
                "verified": gates["CO-SIGN"] == "PASS",
                "implementation": "cryptography/OpenSSL",
                "fips_module_validation_claimed": False,
            },
            "custody": {
                "authority": "THESEUS",
                "mechanism": "sqlite-wal",
                "profile": "software-base",
                "verified": gates["FN-CUSTODY"] == "PASS",
                "external_customer_key_custody": False,
                "multi_region": False,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="software-base")
    parser.add_argument("--output", default="evidence/product-gates.json")
    args = parser.parse_args()
    result = build(args.profile)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
