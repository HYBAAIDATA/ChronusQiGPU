# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Fleet receipts: one signed, ledger-anchored record per job.

Construction:

1. ``body``: the work unit (by digest), the result digest, the lattice, the
   tier entitlement in force at admission (and the scale grant, if any), the
   backend record (requested, detected, preference, executed, reasons), every
   device's measured contribution, the verification and recovery record and
   the honesty statement.
2. ``receipt_id`` = SHA-256 of the canonical body. That digest is appended to
   the AL HARAS anchor ledger (P10) and the ledger position is added.
3. The ML-DSA-65 signature covers the canonical JSON of everything above.

``verify_receipt`` checks the signature (optionally against a pinned public
key), the receipt id, the ledger entry when a ledger is supplied, and the
result bytes when they are supplied. Any failure makes the receipt invalid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from chronus.fleet.canonical import canonical_json, digest_json, is_hex_digest, sha256_hex
from chronus.fleet.errors import SignerUnavailableError
from chronus.fleet.ledger import LEDGER_SCHEMA, AnchorLedger, verify_ledger
from chronus.fleet.signing import SIGNATURE_ALGORITHM, FleetSigner, key_id, verify_signature

RECEIPT_SCHEMA = "chronus.fleet.receipt/v1"

HONESTY = {
    "lattice": "virtual units are a scheduling lattice of logical tiles, not physical cores",
    "physical_cores_claimed": 0,
    "throughput_source": "timed runs on the executing device, with timestamps; never a datasheet",
    "routes": "a requested device route that is absent fails closed; executed_route names the adapter that ran",
    "backends": "the operator's --backend and --prefer chose the backend; every tile records what ran and why",
    "silicon": "each record names the physical silicon under its route: the Chronus iGPU (Mode A) on the host's "
    "general-purpose cores, host GPU routes (Mode B) on GPU silicon",
    "tier_entitlement": "the provisioned entitlement in force when the job was admitted; not a performance claim",
    "host_capacity": "worker-reported host probe values; not independently verified by the coordinator and not measured throughput",
    "verification": "results checked against the deterministic pure-Python reference as recorded below",
}


def sign_receipt(body: Mapping[str, Any], signer: FleetSigner, ledger: AnchorLedger) -> dict[str, Any]:
    """Anchor the body's digest in the ledger, then sign body + id + anchor."""
    receipt_id = digest_json(body)
    backend = body.get("backend") if isinstance(body.get("backend"), Mapping) else {}
    entry = ledger.append("receipt", receipt_id, {
        "job_id": body.get("job_id"),
        "fleet_id": body.get("fleet_id"),
        "requested_backend": backend.get("requested_backend"),
        "preference": backend.get("preference"),
        "executed_backends": backend.get("executed_backends"),
        "detected_backends": backend.get("detected_backends"),
        "fallback_reasons": backend.get("fallback_reasons"),
    })
    receipt = dict(body)
    receipt["receipt_id"] = receipt_id
    receipt["ledger_anchor"] = {
        "ledger": LEDGER_SCHEMA,
        "seq": entry["seq"],
        "entry_hash": entry["entry_hash"],
        "recorded_at": entry["recorded_at"],
    }
    signature = signer.describe()
    signature["value"] = signer.sign(canonical_json(receipt))
    receipt["signature"] = signature
    return receipt


@dataclass
class ReceiptCheck:
    valid: bool
    reasons: list[str] = field(default_factory=list)
    key_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "reasons": self.reasons, "key_id": self.key_id}


def verify_receipt(
    receipt: Mapping[str, Any],
    *,
    public_key: bytes | str | None = None,
    output: bytes | None = None,
    work_unit_digest: str | None = None,
    ledger_path: str | Path | None = None,
) -> ReceiptCheck:
    reasons: list[str] = []
    if not isinstance(receipt, Mapping) or receipt.get("schema") != RECEIPT_SCHEMA:
        return ReceiptCheck(False, ["not a chronus.fleet.receipt/v1 document"])
    signature = receipt.get("signature")
    if not isinstance(signature, Mapping) or signature.get("algorithm") != SIGNATURE_ALGORITHM:
        return ReceiptCheck(False, ["missing ML-DSA-65 signature"])
    try:
        embedded = bytes.fromhex(signature.get("public_key", ""))
    except (ValueError, TypeError):
        return ReceiptCheck(False, ["signature public key is not hex"])
    found_key = key_id(embedded)
    if signature.get("key_id") != found_key:
        reasons.append("key_id does not match the embedded public key")
    if public_key is not None:
        pinned = bytes.fromhex(public_key) if isinstance(public_key, str) else bytes(public_key)
        if pinned != embedded:
            reasons.append("receipt was signed by a different key than the pinned coordinator key")
    unsigned = {k: v for k, v in receipt.items() if k != "signature"}
    try:
        if not verify_signature(embedded, canonical_json(unsigned), str(signature.get("value", ""))):
            reasons.append("ML-DSA-65 signature does not verify")
    except SignerUnavailableError as exc:
        reasons.append(f"cannot verify: {exc}")
    body = {k: v for k, v in unsigned.items() if k not in ("receipt_id", "ledger_anchor")}
    if digest_json(body) != receipt.get("receipt_id"):
        reasons.append("receipt_id does not match the receipt body")
    result = receipt.get("result") or {}
    if output is not None and sha256_hex(output) != result.get("sha256"):
        reasons.append("result bytes do not match the signed result digest")
    if work_unit_digest is not None and (receipt.get("work_unit") or {}).get("digest") != work_unit_digest:
        reasons.append("work unit digest does not match the submitted work unit")
    anchor = receipt.get("ledger_anchor") or {}
    if not is_hex_digest(anchor.get("entry_hash")):
        reasons.append("ledger anchor is missing")
    elif ledger_path is not None:
        check = verify_ledger(ledger_path)
        if not check.valid:
            reasons.append(f"ledger fails verification: {check.reason}")
        else:
            ledger = AnchorLedger(ledger_path)
            entry = ledger.find(receipt.get("receipt_id", ""), seq=anchor.get("seq"))
            if entry is None or entry["seq"] != anchor.get("seq") or entry["entry_hash"] != anchor.get("entry_hash"):
                reasons.append("receipt is not anchored at the stated ledger position")
    return ReceiptCheck(not reasons, reasons, found_key)


def summarise(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """A short human-readable digest of a receipt for the CLI."""
    devices = receipt.get("devices", [])
    return {
        "job_id": receipt.get("job_id"),
        "kernel": (receipt.get("work_unit") or {}).get("kernel"),
        "result_sha256": (receipt.get("result") or {}).get("sha256"),
        "tiles": (receipt.get("lattice") or {}).get("tiles"),
        "devices": [
            {
                "node": d.get("label"),
                "routes": d.get("routes_executed"),
                "items": d.get("items"),
                "measured_items_per_second": d.get("items_per_second"),
                "silicon": d.get("silicon"),
            }
            for d in devices
        ],
        "verification": receipt.get("verification", {}).get("summary"),
        "recovery_incidents": len(receipt.get("recovery", [])),
        "receipt_id": receipt.get("receipt_id"),
        "signature": (receipt.get("signature") or {}).get("algorithm"),
    }
