"""Package-level qualification facade.

This facade never self-certifies production readiness. Diagnostic invariants may
be loaded from legacy compatibility code, but production qualification is
derived only from explicit gate results plus externally verified attestation.
"""

import importlib.util
import json
import os
from typing import Any, Dict, Mapping

from chronus.core.qualification import MANDATORY, qualify


class ChronusVerificationOrchestrator:
    """Compatibility facade over the evidence-based qualification contract."""

    @classmethod
    def run_complete_verification_suite(
        cls,
        *,
        ci_gates: Mapping[str, str] | None = None,
        attestation_verified: bool = False,
        key_provider: str = "local-memory",
        require_pq: bool = True,
    ) -> Dict[str, Any]:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        v36_path = os.path.join(repo_root, "src", "chronus", "chronus_gpiu-v36.py")

        diagnostic: Dict[str, Any] = {}
        if os.path.exists(v36_path):
            try:
                spec = importlib.util.spec_from_file_location("chronus_gpiu_v36", v36_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    legacy = getattr(mod, "ChronusVerificationOrchestrator", None)
                    if legacy is not None:
                        diagnostic = dict(legacy.run_complete_verification_suite())
            except Exception as exc:
                diagnostic = {"diagnostic_error": str(exc)}

        verdict = qualify(
            require_pq=require_pq,
            ci_gates=ci_gates,
            attestation_verified=attestation_verified,
            key_provider=key_provider,
        )
        gates = dict(ci_gates or {})
        passed = sum(1 for gate in MANDATORY if gates.get(gate) == "PASS")
        result: Dict[str, Any] = {
            "version": diagnostic.get("version", "chronus-current"),
            "qualification_status": "PRODUCTION_QUALIFIED" if verdict.status == "PASS" else "UNQUALIFIED",
            "production_admitted": verdict.status == "PASS",
            "total_release_gates_evaluated": len(MANDATORY),
            "release_gates_passed": passed,
            "release_gate_status": {gate: gates.get(gate, "UNQUALIFIED") for gate in MANDATORY},
            "attestation_verified": bool(attestation_verified),
            "key_provider": key_provider,
            "blockers": list(verdict.unqualified),
            "diagnostic_invariants": {
                "evaluated": diagnostic.get("total_invariants_evaluated"),
                "passed": diagnostic.get("invariants_passed"),
                "summary": diagnostic.get("invariant_summary"),
                "qualification_credit": False,
            },
        }

        manifest_path = os.path.join(repo_root, "manifests", "qualification_manifest_v36.json")
        try:
            os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, sort_keys=True)
                f.write("\n")
        except OSError:
            pass
        return result
