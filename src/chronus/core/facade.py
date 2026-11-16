"""Chronus verification facade.

Runs bounded local diagnostics. Does not certify production qualification or
assert unverified architectural invariants.
"""

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GateResult:
    """One locally evaluated qualification prerequisite."""

    id: str
    requirement: str
    passed: bool
    detail: str


@dataclass
class Manifest:
    """Fail-closed local diagnostic manifest.

    Local checks are useful evidence, but they cannot independently confer a
    production qualification posture.
    """

    generated_at: str
    gates: list[GateResult] = field(default_factory=list)
    extra_blockers: list[str] = field(default_factory=list)

    @property
    def posture(self) -> str:
        return "not_qualified"

    @property
    def passed(self) -> int:
        return sum(gate.passed for gate in self.gates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "posture": self.posture,
            "gates_total": len(self.gates),
            "gates_passed": self.passed,
            "gates": [asdict(gate) for gate in self.gates],
            "blockers": self.extra_blockers,
        }


def _gate_signers() -> tuple[bool, str]:
    from chronus.security.signers import Ed25519Signer, MlDsaSigner

    ok, detail = Ed25519Signer().self_test()
    if not ok:
        return False, detail
    if not MlDsaSigner.conformant:
        return False, "Ed25519 self-test passes; ML-DSA-65 is unavailable"
    return True, "advertised signers conformant"


def _gate_receipts() -> tuple[bool, str]:
    from chronus.crypto.signers import Ed25519Signer
    from chronus.security.receipts import Receipt, ReceiptLog

    key = Ed25519Signer.generate("qualification-gate")
    log = ReceiptLog()
    receipt = Receipt(
        "gate",
        "tenant",
        "0" * 64,
        "local",
        0,
        "2026-01-01T00:00:00Z",
        key.key_id,
    )
    signed = log.append(receipt, key)
    public_key = key.public_bytes()
    if not log.verify(signed, public_key):
        return False, "receipt signature verification failed"
    if log.verify(signed, public_key, {"result_digest": "1" * 64}):
        return False, "tampered receipt was accepted"
    return log.verify_chain(public_key)


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
    from chronus.core.purity_scanner import scan_installed_package

    count, violations = scan_installed_package()
    if violations:
        return False, "; ".join(violations[:5])
    if count == 0:
        return False, "installed purity scope is empty"
    return True, f"{count} installed package files scanned"


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
    """Run local diagnostics and convert every exception into a failed gate."""

    manifest = Manifest(datetime.now(timezone.utc).isoformat())
    for gate_id, requirement, check in GATES:
        try:
            passed, detail = check()
        except Exception as exc:
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        manifest.gates.append(GateResult(gate_id, requirement, bool(passed), detail))
    manifest.extra_blockers.append(
        "Local diagnostics are not attested CI qualification evidence"
    )
    return manifest


def write(
    manifest: Manifest, path: str = "manifests/qualification_manifest.json"
) -> Path:
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

# Where the release manifest is written. The repository is the default; an
# override lets a caller collect the artefact somewhere disposable.
MANIFEST_OUT_DIR = os.environ.get("CHRONUS_MANIFEST_OUT_DIR")


class ChronusVerificationOrchestrator:
    """Compatibility facade for evidence-led local qualification diagnostics."""

    @classmethod
    def run_complete_verification_suite(cls) -> dict[str, Any]:
        """Return observed local gates without inventing release qualification."""
        observed = run()
        record = observed.to_dict()
        record.update({
            "version": "chronus_gpiu-v36.0",
            "qualification_status": "NOT_QUALIFIED",
            "execution_mode": "LOCAL_DIAGNOSTIC_ONLY",
            "total_release_gates_evaluated": len(observed.gates),
            "release_gates_passed": observed.passed,
            "total_invariants_evaluated": None,
            "invariants_passed": None,
            "invariant_summary": "UNAVAILABLE: independent invariant evidence not verified",
        })
        target = (
            Path(__file__).resolve().parents[3]
            / "manifests"
            / "qualification_manifest_v36.json"
        )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            # Local diagnostic remains usable on read-only installed packages,
            # but missing manifest persistence is always reported as a blocker.
            record["blockers"].append(
                f"Local qualification manifest unavailable: {type(exc).__name__}"
            )
        return record


if __name__ == "__main__":
    raise SystemExit(main())
