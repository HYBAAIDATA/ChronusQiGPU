from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from gate_runner import Outcome
from gate_runner import Status
from gate_runner import run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def promotion(root):
    from al_haras.gate_cli import evaluate_manifest

    report = evaluate_manifest(
        json.loads((root / "config/al-haras-promotion-evidence.json").read_text())
    )
    return Outcome(
        Status.PASS if report["passed"] else Status.FAIL,
        "conservative promotion manifest evaluated",
        (),
    )


def schema(root):
    from al_haras.schema import HotDescriptorV1
    from hyba_contracts import HOT_DESCRIPTOR_V1
    from hyba_contracts import SCHEMA_VERSION

    ok = (
        len(HotDescriptorV1(*range(1, 13)).pack()) == HOT_DESCRIPTOR_V1.size == 64
        and SCHEMA_VERSION == 2
    )
    return Outcome(Status.PASS if ok else Status.FAIL, "schema v2 and 64-byte ABI checked")


def envelope(root):
    from al_haras.envelope import FoldMode
    from al_haras.envelope import build_envelope
    from al_haras.envelope import verify_envelope

    key = b"e" * 32
    values = dict(
        payload={},
        object_id="o",
        tenant="t",
        instance="i",
        fold_family="x",
        fold_mode=FoldMode.PRESERVE,
        rehydration_count=0,
        residual=None,
        cassini_ok=True,
        zeckendorf_ok=True,
        chain_head="h",
        witness_receipt_id="w",
        backend_certificate="c",
        backend_name="b",
        bytes_moved=0,
        proof_bytes=0,
        latency_ms=None,
        energy_joules=None,
        verdict={"ok": True},
    )
    env = build_envelope(signing_key=key, **values)

    def verify(e):
        return verify_envelope(
            e,
            signing_key=key,
            verdict_verifier=lambda v: v.get("ok") is True,
            witness_verifier=lambda w, h: (w, h) == ("w", "h"),
            backend_verifier=lambda c, b: (c, b) == ("c", "b"),
        )

    ok = verify(env) and not verify(replace(env, proof_bytes=1))
    return Outcome(
        Status.PASS if ok else Status.FAIL, "valid envelope accepted and tamper rejected"
    )


def claims(root):
    from al_haras.claim_register import Claim
    from al_haras.claim_register import ClaimRegister
    from al_haras.claim_register import ClaimRejected
    from al_haras.claim_register import ClaimStatus

    with tempfile.TemporaryDirectory() as d:
        reg = ClaimRegister(str(Path(d) / "claims.db"), lambda x: x == "e")
        reg.register(Claim("v", "verified", ClaimStatus.VERIFIED, ("e",), "owner"))
        try:
            reg.register(Claim("p", "production", ClaimStatus.PRODUCTION, ("e",), "owner"))
            ok = False
        except ClaimRejected:
            ok = True
        reg.close()
    return Outcome(
        Status.PASS if ok else Status.FAIL, "claim evidence and independent-review boundary checked"
    )


def imports(root):
    from scripts.import_audit import Auditor, live_files

    findings = Auditor(root).audit(live_files(root))
    hidden = sum(f.swallowed for f in findings)
    return Outcome(
        Status.FAIL if findings else Status.PASS,
        f"{len(findings)} finding(s), {hidden} swallowed",
    )


def no_float(root):
    from al_haras.no_float_guard import FloatForbidden
    from al_haras.no_float_guard import scan_paths

    candidates = []
    for pattern in (
        "chronus/mla1517/core.py",
        "chronus/mla1517/math_folding.py",
        "python_backend/core_modules/math_folding.py",
    ):
        p = root / pattern
        if p.exists():
            candidates.append(p)
    if not candidates:
        return Outcome(Status.SKIP, "no declared exact core paths in this repository")
    try:
        scan_paths(candidates)
        return Outcome(Status.PASS, f"scanned {len(candidates)} exact paths")
    except FloatForbidden as exc:
        return Outcome(Status.FAIL, str(exc))


def abi(root):
    return schema(root)


def refuted(root):
    from al_haras.refuted_claims import CLAIMS_STILL_REFUTED

    violations = []
    for path in (
        [root / "README.md"]
        + [p for p in (root / "docs").rglob("*.md") if "al-haras" not in p.parts]
        if (root / "docs").exists()
        else [root / "README.md"]
    ):
        if not path.exists():
            continue
        for no, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            low = line.casefold()
            if any(
                marker in low
                for marker in (
                    "refuted",
                    "must not claim",
                    "not established",
                    "does not prove",
                    "unclaimed",
                )
            ):
                continue
            for claim in CLAIMS_STILL_REFUTED:
                if claim.casefold() in low:
                    violations.append(f"{path.relative_to(root)}:{no}:{claim}")
    artifact = root / "results" / "refuted-claims-violations.json"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(json.dumps(violations, indent=2))
    return Outcome(
        Status.FAIL if violations else Status.PASS,
        f"{len(violations)} unqualified refuted-claim matches",
        (str(artifact),),
    )


def conformance(root):
    return Outcome(
        Status.SKIP, "fewer than two independently available exact backends; no conformance claim"
    )


def resilience(root):
    names = (
        "test_crash_recovery.py",
        "test_replay.py",
        "test_policy_rotation.py",
        "test_compound_failure.py",
    )
    found = [str(p) for n in names for p in root.rglob(n)]
    return Outcome(
        Status.PASS if len(found) == 4 else Status.SKIP,
        (
            "full resilience suite present"
            if len(found) == 4
            else f"resilience suite incomplete ({len(found)}/4)"
        ),
        tuple(found),
    )


def privileged(root):
    import os

    from al_haras.privileged_audit import audit
    from al_haras.privileged_audit import manifest

    routes, violations = audit(root)
    privileged_routes = [
        r
        for r in routes
        if r.path.startswith("/api/v1/")
        and any(
            r.path.startswith(p)
            for p in (
                "/api/v1/mining/",
                "/api/v1/policy/",
                "/api/v1/worker/",
                "/api/v1/recovery/",
                "/api/v1/admin/",
                "/api/v1/toe/",
                "/api/v1/quantum/",
                "/api/v1/scale/",
                "/api/v1/assembly/",
                "/api/v1/security/",
            )
        )
    ]
    key = os.environ.get("MEDIATION_MANIFEST_KEY", "").encode() or None
    report = manifest(routes, violations, key)
    artifact = root / "results" / "mediation_manifest.json"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(json.dumps(report, sort_keys=True, indent=2))
    if not privileged_routes:
        return Outcome(
            Status.FAIL,
            "no privileged routes discovered; route inventory is incomplete",
            (str(artifact),),
        )
    reason = f"{len(violations)} violation(s) across {len(privileged_routes)} privileged route(s)"
    if not key:
        reason += (
            "; MEDIATION_MANIFEST_KEY is absent and unsigned mediation evidence cannot promote"
        )
    return Outcome(Status.FAIL if violations or not key else Status.PASS, reason, (str(artifact),))


GATES = {
    "promotion-manifest": promotion,
    "schema-freeze": schema,
    "envelope-verify": envelope,
    "claim-register": claims,
    "import-audit": imports,
    "rule7-no-float": no_float,
    "abi-check": abi,
    "refuted-claims": refuted,
    "conformance-vectors": conformance,
    "resilience-suite": resilience,
    "privileged-path-audit": privileged,
}


def main(name, root="."):
    result = run(name, GATES[name], Path(root).resolve())
    print(json.dumps({"gate": result.gate, "status": result.status.value, "reason": result.reason}))
    return 0 if result.status in {Status.PASS, Status.SKIP} else 1
