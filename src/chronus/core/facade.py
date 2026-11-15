"""Chronus verification facade.

Local diagnostic gates remain available for compatibility and operator
troubleshooting. They are not production authority. Production admission is
derived only from the attested mandatory product gates in
:mod:`chronus.core.qualification`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping

from chronus.core.claims import dispositions
from chronus.core.qualification import MANDATORY, qualify
from chronus.security import canonical
from chronus.security.receipts import ReceiptLog, VerificationError
from chronus.security.signers import MlDsaSigner
from scripts.ci import purity_gate


@dataclass
class GateResult:
    name: str
    passed: bool
    details: str = ""


@dataclass
class Manifest:
    posture: str
    gates: Dict[str, GateResult]
    blockers: list[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "posture": self.posture,
                "gates": {name: asdict(value) for name, value in self.gates.items()},
                "blockers": list(self.blockers),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _gate_signers() -> GateResult:
    # The legacy signer name is intentionally non-conformant. Production
    # signing is checked by the executable CO-SIGN product gate instead.
    try:
        signer = MlDsaSigner()
        if not getattr(signer, "conformant", False):
            return GateResult(
                "G1_SIGNERS",
                False,
                "legacy ML-DSA compatibility signer is not production conformant",
            )
        return GateResult("G1_SIGNERS", False, "legacy signer must not grant production credit")
    except Exception as exc:
        return GateResult("G1_SIGNERS", False, f"legacy signer unavailable: {exc}")


def _gate_receipts() -> GateResult:
    try:
        from tempfile import TemporaryDirectory

        from chronus.security.signers import Ed25519Signer

        with TemporaryDirectory() as directory:
            signer = Ed25519Signer()
            log = ReceiptLog(Path(directory) / "receipts.jsonl", signer)
            first = log.append(
                workload_id="w1",
                tenant_id="t1",
                result_digest="a" * 64,
                node_id="n1",
                backend="reference",
            )
            log.append(
                workload_id="w2",
                tenant_id="t1",
                result_digest="b" * 64,
                node_id="n1",
                backend="reference",
            )
            assert len(log.verify_all(signer.get_public_key())) == 2
            raw = (Path(directory) / "receipts.jsonl").read_text(encoding="utf-8")
            (Path(directory) / "receipts.jsonl").write_text(
                raw.replace(first.result_digest, "c" * 64, 1),
                encoding="utf-8",
            )
            try:
                log.verify_all(signer.get_public_key())
                return GateResult("G2_RECEIPTS", False, "tampering was not rejected")
            except VerificationError:
                return GateResult("G2_RECEIPTS", True)
    except Exception as exc:
        return GateResult("G2_RECEIPTS", False, str(exc))


def _gate_canonical() -> GateResult:
    try:
        left = canonical.dumps({"b": 2, "a": [1, "x"]})
        right = canonical.dumps({"a": [1, "x"], "b": 2})
        if left != right:
            return GateResult("G3_CANONICAL", False, "non-deterministic encoding")
        try:
            canonical.dumps({"x": 1.1})
            return GateResult("G3_CANONICAL", False, "float was accepted")
        except (TypeError, ValueError):
            return GateResult("G3_CANONICAL", True)
    except Exception as exc:
        return GateResult("G3_CANONICAL", False, str(exc))


def _gate_purity() -> GateResult:
    try:
        rc = purity_gate.main()
        return GateResult(
            "G4_PURITY",
            rc == 0,
            "scripts/ci/purity_gate.py" if rc == 0 else "purity gate reported violations",
        )
    except Exception as exc:
        return GateResult("G4_PURITY", False, str(exc))


def _gate_claims() -> GateResult:
    # Local diagnostic only. The production FN-CLAIMS gate parses the actual
    # claim register and is separately attested.
    return GateResult(
        "G5_CLAIMS",
        False,
        "production claim evidence is evaluated by the attested FN-CLAIMS gate",
    )


GATES: tuple[Callable[[], GateResult], ...] = (
    _gate_signers,
    _gate_receipts,
    _gate_canonical,
    _gate_purity,
    _gate_claims,
)


def run() -> Manifest:
    results: Dict[str, GateResult] = {}
    blockers: list[str] = []
    for gate in GATES:
        try:
            result = gate()
        except Exception as exc:
            result = GateResult(getattr(gate, "__name__", "unknown"), False, str(exc))
        results[result.name] = result
        if not result.passed:
            blockers.append(f"{result.name}: {result.details or 'failed'}")
    return Manifest("not_qualified", results, blockers)


def write(manifest: Manifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json() + "\n", encoding="utf-8")


class ChronusVerificationOrchestrator:
    """Compatibility API over the production qualification contract."""

    @classmethod
    def run_complete_verification_suite(
        cls,
        *,
        ci_gates: Mapping[str, str] | None = None,
        attestation_verified: bool = False,
        key_provider: str = "local-memory",
        require_pq: bool = True,
    ) -> dict:
        diagnostic = run()
        verdict = qualify(
            require_pq=require_pq,
            ci_gates=ci_gates,
            attestation_verified=attestation_verified,
            key_provider=key_provider,
        )
        gates = dict(ci_gates or {})
        blockers = list(verdict.unqualified)
        result = {
            "version": "chronus-current",
            "qualification_status": (
                "PRODUCTION_QUALIFIED" if verdict.status == "PASS" else "UNQUALIFIED"
            ),
            "production_admitted": verdict.status == "PASS",
            "total_release_gates_evaluated": len(MANDATORY),
            "release_gates_passed": sum(
                1 for gate in MANDATORY if gates.get(gate) == "PASS"
            ),
            "release_gate_status": {
                gate: gates.get(gate, "UNQUALIFIED") for gate in MANDATORY
            },
            "attestation_verified": bool(attestation_verified),
            "key_provider": key_provider,
            "blockers": blockers,
            "claims": dispositions(gates, bool(attestation_verified)),
            "diagnostic_manifest": json.loads(diagnostic.to_json()),
            "diagnostic_qualification_credit": False,
        }

        manifest_path = (
            Path(__file__).resolve().parents[3]
            / "manifests"
            / "qualification_manifest_v36.json"
        )
        try:
            write(
                Manifest(
                    posture="production_admitted" if verdict.status == "PASS" else "not_qualified",
                    gates={
                        gate: GateResult(
                            gate,
                            gates.get(gate) == "PASS",
                            gates.get(gate, "UNQUALIFIED"),
                        )
                        for gate in MANDATORY
                    },
                    blockers=blockers,
                ),
                manifest_path,
            )
        except OSError:
            result["blockers"].append(
                "qualification manifest unavailable: write failed"
            )
            result["production_admitted"] = False
            result["qualification_status"] = "UNQUALIFIED"
        return result


def main() -> int:
    manifest = run()
    path = Path.cwd() / "manifests" / "qualification_manifest_v36.json"
    try:
        write(manifest, path)
    except OSError as exc:
        manifest.blockers.append(
            f"qualification manifest unavailable: {type(exc).__name__}: {exc}"
        )
        try:
            write(manifest, path)
        except OSError:
            pass
    return 0 if manifest.posture == "production_qualified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
