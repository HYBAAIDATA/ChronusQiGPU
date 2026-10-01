"""Offline-verifiable compliance evidence pack assembly."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Mapping

from hyba_contracts import AssurancePack
from hyba_contracts import PackManifest
from hyba_contracts import compose
from hyba_contracts import emit_gap_report


@dataclass(frozen=True)
class EvidenceGap:
    subject: str
    reason: str
    explained: bool


@dataclass(frozen=True)
class RegulatorEvidencePack:
    pack_id: str
    tenant: str
    window: tuple[int, int]
    controls: tuple[dict, ...]
    obligations: tuple[dict, ...]
    receipts: tuple[Any, ...]
    gaps: tuple[EvidenceGap, ...]
    signatures: tuple[dict, ...]
    verify_command: tuple[str, ...]


def assemble(
    tenant, window, controls, obligations, collect, signers: Mapping[str, Callable[[bytes], str]]
) -> RegulatorEvidencePack:
    receipts = []
    gaps = []
    for control in controls:
        try:
            receipt = collect(control["id"], tenant, window)
            if not receipt.get("verified"):
                raise ValueError(receipt.get("reason", "unverified"))
            receipts.append(receipt)
        except Exception as exc:
            gaps.append(EvidenceGap(control["id"], str(exc), True))
    pack_id = str(uuid.uuid4())
    body = {
        "pack_id": pack_id,
        "tenant": tenant,
        "window": window,
        "controls": tuple(controls),
        "obligations": tuple(obligations),
        "receipt_ids": tuple(r["receipt_id"] for r in receipts),
        "gaps": tuple(asdict(g) for g in gaps),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    signatures = tuple(
        {"signer": name, "signature": fn(raw), "payload_sha256": hashlib.sha256(raw).hexdigest()}
        for name, fn in signers.items()
    )
    return RegulatorEvidencePack(
        pack_id,
        tenant,
        tuple(window),
        tuple(controls),
        tuple(obligations),
        tuple(receipts),
        tuple(gaps),
        signatures,
        ("python", "verify_evidence_pack.py", f"{pack_id}.json"),
    )


def verify_offline(
    pack: RegulatorEvidencePack,
    verify_signature: Callable[[str, str, str], bool],
    verify_envelope: Callable[[Any], bool],
    verify_witness: Callable[[Any], bool],
) -> bool:
    body = {
        "pack_id": pack.pack_id,
        "tenant": pack.tenant,
        "window": pack.window,
        "controls": pack.controls,
        "obligations": pack.obligations,
        "receipt_ids": tuple(r["receipt_id"] for r in pack.receipts),
        "gaps": tuple(asdict(g) for g in pack.gaps),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    digest = hashlib.sha256(raw).hexdigest()
    if not pack.signatures or not all(
        s["payload_sha256"] == digest and verify_signature(s["signer"], s["signature"], digest)
        for s in pack.signatures
    ):
        return False
    if not all(verify_envelope(r["envelope"]) and verify_witness(r) for r in pack.receipts):
        return False
    return all(g.explained for g in pack.gaps)


def crosswalk(packs: Iterable[AssurancePack]) -> dict:
    result = {}
    for pack in packs:
        for m in pack.mappings:
            result[m.obligation_id] = {
                "controls": m.control_ids,
                "tests": m.test_ids,
                "evidence": m.evidence_ids,
                "notes": m.notes,
                "pack": pack.pack_id,
            }
    return result


@dataclass(frozen=True)
class ControlJob:
    control_id: str
    cadence_seconds: int
    run: Callable[[], dict]


def run_scheduled(
    jobs: Iterable[ControlJob],
    alert: Callable[[str, str], None],
    record_gap: Callable[[EvidenceGap], None],
):
    results = []
    for job in jobs:
        receipt = job.run()
        results.append(receipt)
        if not receipt.get("verified"):
            reason = receipt.get("reason", "unverified")
            alert(job.control_id, reason)
            record_gap(EvidenceGap(job.control_id, reason, True))
    return tuple(results)


class EvidenceRoom:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, pack: RegulatorEvidencePack, audience: str) -> Path:
        path = self.root / f"{pack.pack_id}.json"
        path.write_text(
            json.dumps(
                {"audience": audience, "pack": asdict(pack)}, sort_keys=True, indent=2, default=str
            )
        )
        path.chmod(0o444)
        return path

    def fetch(self, path: Path) -> dict:
        return json.loads(path.read_text())


def install_industry(
    pack: PackManifest,
    core: Mapping[str, Iterable],
    validate: Callable[[PackManifest], None],
    registries: Mapping[str, Callable[[Iterable], None]],
    assurance: AssurancePack,
    sign_gap: Callable[[dict], str],
):
    validate(pack)
    composed = compose(pack, core)
    for name, items in (
        ("ontology", composed.ontology),
        ("policy", composed.policy),
        ("controls", composed.controls),
        ("obligations", composed.obligations),
        ("workflows", composed.workflows),
        ("integrations", composed.integrations),
        ("evidence", composed.evidence),
        ("threat_model", composed.threat_model),
        ("benchmarks", composed.benchmarks),
    ):
        if name not in registries:
            raise ValueError(f"missing registry: {name}")
        registries[name](items)

    def available(items):
        return {x.get("id") for x in items if isinstance(x, dict) and x.get("id")}

    gap = emit_gap_report(
        assurance, available(composed.controls), set(), available(composed.evidence), sign_gap
    )
    return {"pack": pack.pack_id, "composed": composed, "gap_report": gap}
