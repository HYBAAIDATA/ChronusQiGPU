"""Fail-closed verification of a deployment-authority signed promotion bundle.

This verifies signature, freshness and retained artefact binding. It does not
assert that a reviewer's assertions are true, or generate its own approval.
"""

import base64
import hashlib
import json
from pathlib import Path
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .control import Unavailable, canonical

GATES = frozenset(
    {
        "runtime_integration",
        "identity_security",
        "recovery_load",
        "package_qualification",
        "commercial_approval",
    }
)


def verify_bundle(
    directory, public_key, commit, *, publication=False, now=None, allow_waivers=False
):
    root = Path(directory).resolve()
    now = int(time.time()) if now is None else now
    try:
        envelope = json.loads((root / "approval.json").read_text())
        manifest = envelope["manifest"]
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True)).verify(
            base64.b64decode(envelope["signature"], validate=True), canonical(manifest).encode()
        )
        if (
            manifest["schema"] != "turing.promotion.v1"
            or manifest.get("billing_scope") != "deferred"
            or manifest["commit"] != commit
            or not commit
        ):
            raise ValueError("promotion identity mismatch")
        if (
            not 0 <= now - manifest["issued_at"] <= 7 * 86400
            or not now < manifest["expires_at"] <= manifest["issued_at"] + 7 * 86400
        ):
            raise ValueError("promotion approval stale")
        required = GATES | ({"publication_rights"} if publication else set())
        for gate in required:
            entry = manifest["gates"][gate]
            state = entry["state"]
            if state == "PASS":
                if not entry["reviewer"] or not 0 <= now - entry["executed_at"] <= 7 * 86400:
                    raise ValueError("gate not freshly accepted")
            elif state == "WAIVED" and allow_waivers is True and gate in GATES:
                # A signed risk decision is NOT execution evidence. Runtime
                # authorization, custody checks and source binding stay intact.
                acceptance = entry["risk_acceptance"]
                for field in ("approver", "reason", "authorization_reference"):
                    value = acceptance[field]
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError("waiver has no accountable authorization")
                if (
                    type(acceptance["accepted_at"]) is not int
                    or not 0 <= now - acceptance["accepted_at"] <= 7 * 86400
                    or "executed_at" in entry
                ):
                    raise ValueError("waiver is stale or misrepresented as execution")
            else:
                raise ValueError("gate not accepted under configured policy")
            relative = Path(entry["artifact"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("invalid artifact path")
            path = root / relative
            if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
                raise ValueError("artifact not retained")
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("evidence hash mismatch")
        return manifest
    except Exception:
        raise Unavailable("signed promotion evidence is missing, stale or invalid") from None
