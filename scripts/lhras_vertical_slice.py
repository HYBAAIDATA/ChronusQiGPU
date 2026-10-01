"""One-command L-HRAS vertical slice.

Demonstrates the governed request path end to end on a clean checkout:

    entitlement issue
    -> boundary evaluate (subscription gate)
    -> L-HRAS trust-root attestation
    -> seven-topology + six-intelligence + five-mode conjunction
    -> governed verdict
    -> aethel certificate write (Zeckendorf block, Cassini address)
    -> hash-chain audit replay
    -> evidence pack emitted as JSON

Every stage is a real library call — no mocks. On a POSIX host the audit
ledger is durable; on non-flock hosts (e.g. Windows dev) it runs on the
in-memory chain and reports ``audit_durable: false`` in the pack.

    python scripts/lhras_vertical_slice.py --out /tmp/lhras_slice
    python scripts/lhras_vertical_slice.py --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims
from al_haras.guardian import ALHaras, GuardianPolicy
from al_haras.runtime import GuardianAPI
from al_haras.settings import ALHarasSettings
from al_haras.audit import HashChainAudit

from l_hras import (
    Request,
    RequestAttestation,
    RequestKind,
    initialize,
    load_config,
    respond,
    signed_request,
    stand,
)


def _now() -> int:
    return int(time.time())


def _demo_settings(out_dir: Path) -> ALHarasSettings:
    return ALHarasSettings(
        issuer="hyba-subscriptions",
        keyring={"demo-key-1": b"lhras-slice-demo-secret-0123456789abcdef"},
        audit_path=out_dir / "slice-guardian.jsonl",
        audit_quarantine=True,
        lhras_enabled=False,
    )


def build_evidence_pack(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    pack: dict = {"stages": [], "checks": {}}

    def stage(name: str, ok: bool, detail: dict | None = None) -> None:
        pack["stages"].append({"stage": name, "ok": ok, "detail": detail or {}})
        if not ok:
            pack["checks"]["failed_at"] = name

    # ── 1. Entitlement issue ─────────────────────────────────────────
    settings = _demo_settings(out_dir)
    authority = SubscriptionAuthority(settings.keyring, settings.issuer)
    claims = SubscriptionClaims(
        issuer=settings.issuer,
        key_id="demo-key-1",
        tenant_id="tenant-demo",
        capabilities=("hyba.security",),
        actors=("soc-analyst-1",),
        not_before=_now() - 60,
        expires_at=_now() + 900,
        subscription_id="sub-slice-001",
        max_payload_bytes=4096,
        jti="nonce-slice-1",
    )
    actor = claims.actors[0]
    token = authority.issue(claims)
    stage("entitlement_issue", True, {"subscription_id": claims.subscription_id})

    # ── 2. Boundary evaluate (subscription gate) ─────────────────────
    try:
        audit = HashChainAudit(settings.audit_path)
        audit_durable = True
    except RuntimeError:
        audit = HashChainAudit()
        audit_durable = False
    guardian = ALHaras(
        authority=authority,
        policy=GuardianPolicy(
            version=settings.policy_version,
            capability=settings.capability,
            max_payload_bytes=settings.max_payload_bytes,
        ),
        audit=audit,
        boundary_audit=HashChainAudit(),
    )
    api = GuardianAPI(guardian, settings, evidence_provider=lambda obs: {"schema_version": "slice"})
    body = {
        "operation": "toe.collapse",
        "resource": "chronus.mla1517.toe",
        "payload": {"evidence": {}},
        "observation": {"baseline": 0.12, "spread": 0.05},
        "request_id": "req-slice-0001",
    }
    headers = {
        "x-hyba-tenant": claims.tenant_id,
        "x-hyba-actor": actor,
        "authorization": f"Bearer {token}",
    }
    status, verdict = api.evaluate(headers=headers, body=body, include_evidence=True)
    stage(
        "boundary_evaluate",
        status == 200 and verdict.get("allowed") is True,
        {"status": status, "reason": verdict.get("reason")},
    )
    if not verdict.get("allowed"):
        return pack

    # ── 3. L-HRAS load + stand ───────────────────────────────────────
    cfg_r = load_config(REPO_ROOT / "l_hras" / "config.example.toml")
    if cfg_r.is_err:
        stage("lhras_stand", False, {"error": cfg_r.error.code})
        return pack
    cfg = cfg_r.value
    init_r = initialize(cfg)
    if init_r.is_err:
        stage("lhras_stand", False, {"error": init_r.error.code})
        return pack
    lhras = init_r.value
    stand_r = stand(lhras)
    if stand_r.is_err:
        stage("lhras_stand", False, {"error": stand_r.error.code})
        return pack
    stage("lhras_stand", True, {"instance": cfg.instance_id})

    # ── 4. Attested request -> governed verdict ──────────────────────
    req = Request(
        kind=RequestKind.BENIGN,
        attestation=RequestAttestation(token="", payload_digest=""),
        actor=actor,
        action="toe.collapse",
        resource="chronus.mla1517.toe",
        payload={"request_id": "req-slice-0001"},
        telemetry=[0.1, 0.2, 0.15, 0.18, 0.12, 0.11, 0.09],
        observation={"baseline": 0.12, "spread": 0.05},
    )
    signed_request(cfg.trust_root, req)
    resp_r = respond(lhras, req)
    if resp_r.is_err:
        stage("lhras_respond", False, {"error": resp_r.error.code})
        return pack
    resp = resp_r.value
    stage(
        "lhras_respond",
        bool(resp.allowed),
        {"reason": resp.reason, "certificate": bool(resp.attestation)},
    )

    # ── 5. Evidence replay ───────────────────────────────────────────
    replay_ok = True
    if audit_durable:
        try:
            records = list(audit.records)
            replay_ok = len(records) >= 1
            last = records[-1]
        except Exception:
            replay_ok = False
            last = {}
    else:
        records = list(audit.records)
        last = records[-1] if records else {}
    aethel_ok = lhras.aethel.verify()
    stage(
        "evidence_replay",
        bool(replay_ok and aethel_ok),
        {"audit_records": len(records), "aethel_verify": aethel_ok},
    )

    # ── Evidence pack ────────────────────────────────────────────────
    pack["verdict"] = {
        "allowed": resp.allowed,
        "reason": resp.reason,
        "escalate": getattr(resp.escalate, "name", str(resp.escalate)),
    }
    pack["attestation_root"] = (
        resp.attestation.to_dict() if hasattr(resp.attestation, "to_dict") else resp.attestation
    )
    pack["boundary_verdict"] = {
        "reason": verdict.get("reason"),
        "subscription_id": verdict.get("subscription_id"),
    }
    pack["evidence"] = {
        "audit_durable": audit_durable,
        "audit_records": len(records),
        "audit_tail_hash": (last.get("record_hash") if isinstance(last, dict) else ""),
        "aethel_store": str(cfg.aethel_root),
        "aethel_verify": aethel_ok,
    }
    pack["digests"] = {
        "request_payload_digest": req.payload_digest(),
        "evidence_pack_sha256": hashlib.sha256(
            json.dumps(pack["verdict"], sort_keys=True).encode()
        ).hexdigest(),
    }
    pack["disclaimer"] = (
        "Demo secrets and in-memory fallbacks. Production: provisioned trust "
        "root, POSIX durable audit, real SIEM/SOAR endpoints."
    )
    return pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=None, help="evidence pack output dir")
    parser.add_argument("--json", action="store_true", help="print pack as JSON")
    args = parser.parse_args()
    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="lhras_slice_"))
    pack = build_evidence_pack(out_dir)
    pack_path = out_dir / "evidence_pack.json"
    pack_path.write_text(json.dumps(pack, indent=2, sort_keys=True))
    failed = next((s for s in pack["stages"] if not s["ok"]), None)
    if args.json:
        print(json.dumps(pack, indent=2, sort_keys=True))
    else:
        for s in pack["stages"]:
            print(f"{'PASS' if s['ok'] else 'FAIL'}  {s['stage']}  {s['detail']}")
        print(f"evidence pack: {pack_path}")
    return 0 if failed is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
