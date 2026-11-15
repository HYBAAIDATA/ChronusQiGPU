"""Fail-closed, computed qualification manifest; no hardcoded pass counts."""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

@dataclass(frozen=True)
class GateResult:
    id: str
    requirement: str
    passed: bool
    detail: str

@dataclass
class Manifest:
    generated_at: str
    gates: list[GateResult] = field(default_factory=list)
    extra_blockers: list[str] = field(default_factory=list)
    @property
    def posture(self) -> str:
        # Local diagnostics can never confer production qualification.
        return "not_qualified"
    @property
    def passed(self) -> int:
        return sum(g.passed for g in self.gates)
    def to_dict(self) -> dict:
        return {"generated_at": self.generated_at, "posture": self.posture,
                "gates_total": len(self.gates), "gates_passed": self.passed,
                "gates": [asdict(g) for g in self.gates], "blockers": self.extra_blockers}

def _gate_signers() -> tuple[bool, str]:
    from chronus.security.signers import Ed25519Signer, MlDsaSigner
    ok, detail = Ed25519Signer().self_test()
    if not ok:
        return False, detail
    if not MlDsaSigner.conformant:
        return False, "Ed25519 self-test passes; ML-DSA-65 is unavailable"
    return True, "advertised signers conformant"

def _gate_receipts() -> tuple[bool, str]:
    from chronus.security.signers import Ed25519Signer
    from chronus.security.receipts import Receipt, ReceiptLog
    key = Ed25519Signer()
    log = ReceiptLog()
    signed = log.append(Receipt("gate", "tenant", "0" * 64, "local", 0, "2026-01-01T00:00:00Z", key.key_id), key)
    if not log.verify(signed, key.public_key) or log.verify(signed, key.public_key, {"result_digest": "1" * 64}):
        return False, "receipt verification or tamper rejection failed"
    return log.verify_chain(key.public_key)

def _gate_canonical_json() -> tuple[bool, str]:
    from chronus.security.canonical import canonical_bytes
    if canonical_bytes({"b": 2, "a": [1]}) != canonical_bytes({"a": [1], "b": 2}):
        return False, "key order changed canonical bytes"
    try:
        canonical_bytes({"x": 1.5})
    except TypeError:
        return True, "restricted canonical JSON stable; floats rejected"
    return False, "float accepted"

def _gate_purity() -> tuple[bool, str]:
    from scripts.ci.purity_gate import scan
    violations, scanned = scan()
    if violations:
        return False, "; ".join(violations[:5])
    return True, f"{len(scanned)} files scanned in declared scope"

def _gate_claim_audit() -> tuple[bool, str]:
    return False, "independent claim-evidence register verification not yet integrated"

GATES: tuple[tuple[str, str, Callable[[], tuple[bool, str]]], ...] = (
    ("G1", "signer conformance", _gate_signers),
    ("G2", "receipt integrity", _gate_receipts),
    ("G3", "canonical bytes", _gate_canonical_json),
    ("G4", "purity scan", _gate_purity),
    ("G5", "claim evidence audit", _gate_claim_audit),
)

def run() -> Manifest:
    manifest = Manifest(datetime.now(timezone.utc).isoformat())
    for id, requirement, fn in GATES:
        try:
            passed, detail = fn()
        except Exception as exc:
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        manifest.gates.append(GateResult(id, requirement, bool(passed), detail))
    manifest.extra_blockers.append("Local diagnostics are not attested CI qualification evidence")
    return manifest

def write(manifest: Manifest, path: str = "manifests/qualification_manifest.json") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")
    return target

def main() -> int:
    manifest = run()
    target = write(manifest)
    for gate in manifest.gates:
        print(f"[{'PASS' if gate.passed else 'FAIL'}] {gate.id}: {gate.detail}")
    print(f"{manifest.posture} ({manifest.passed}/{len(manifest.gates)}) -> {target}")
    return 0 if manifest.posture == "qualified" else 1

if __name__ == "__main__":
    raise SystemExit(main())
