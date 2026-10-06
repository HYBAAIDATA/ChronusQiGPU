"""Fail closed if the canonical PYTHIA structured-search doctrine drifts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "canonical_mining_search.yaml"
DOCTRINE = ROOT / "docs" / "CANONICAL_PYTHIA_SEARCH_DOCTRINE.md"
README = ROOT / "README.md"
MINING_README = ROOT / "README_MINING.md"


class CanonicalSearchDoctrineError(RuntimeError):
    """Raised when an owner-locked mining-search invariant drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanonicalSearchDoctrineError(message)


def validate(root: Path = ROOT) -> None:
    policy = yaml.safe_load((root / POLICY.relative_to(ROOT)).read_text(encoding="utf-8"))
    doctrine = (root / DOCTRINE.relative_to(ROOT)).read_text(encoding="utf-8")
    readme = (root / README.relative_to(ROOT)).read_text(encoding="utf-8")
    mining_readme = (root / MINING_README.relative_to(ROOT)).read_text(encoding="utf-8")

    _require(policy["status"] == "CANONICAL_OWNER_LOCKED", "canonical status changed")
    _require(
        policy["change_control"]["explicit_owner_approval_required"] is True,
        "owner approval requirement removed",
    )
    _require(
        policy["change_control"]["default_on_conflict"] == "REJECT_CHANGE",
        "conflicting changes no longer fail closed",
    )

    search = policy["search"]
    _require(search["classification"] == "STRUCTURED_SEARCH", "structured search demoted")
    _require(search["default_algorithm"] == "Hendrix", "Hendrix is no longer default")
    _require(search["coverage"] == "FULL_NONCE_ESTATE", "full nonce coverage removed")
    _require(
        search["flat_search_may_replace_canonical_default"] is False,
        "flat search may replace canonical default",
    )
    _require(
        search["itinerary"] == ["32-face", "11D", "H4/600", "Turing/Hilbert"],
        "canonical structured itinerary drifted",
    )
    _require(
        search["complexity_objective"]["value"] == "O(1)",
        "O(1) structure-directed design objective removed",
    )

    _require(
        policy["authority"]["mining_intelligence"] == "PYTHIA"
        and policy["authority"]["final_search_plan"] == "PYTHIA",
        "PYTHIA mining/SearchPlan authority drifted",
    )
    _require(
        policy["proof"]["share_validity_authority"] == "SHA256d_plus_negotiated_target",
        "SHA256d/target proof boundary changed",
    )
    _require(
        policy["proof"]["pool_acceptance_authority"] == "literal_pool_acknowledgement",
        "literal pool outcome boundary changed",
    )
    _require(policy["proof"]["resonance_is_proof_predicate"] is False, "resonance became proof")

    resonance = policy["resonance"]
    artifact = root / resonance["evidence_artifact"]
    evidence = json.loads(artifact.read_text(encoding="utf-8"))
    _require(evidence["scoring"]["threshold"] == resonance["structural_band"]["threshold_gte"],
             "R_phi threshold drifted from bound evidence")
    _require(evidence["corpus"]["n"] == resonance["real_corpus"]["n"],
             "real corpus size drifted from bound evidence")
    _require(evidence["scoring"]["winner_hits"] == "122/200",
             "real-corpus hit count changed; update only with owner-reviewed evidence")
    _require(evidence["scoring"]["winner_rate"] == resonance["real_corpus"]["rate"],
             "real-corpus rate drifted from bound evidence")
    _require(evidence["baseline"]["n"] == resonance["uniform_control"]["n"],
             "uniform-control size drifted from bound evidence")
    _require(evidence["baseline"]["rate"] == resonance["uniform_control"]["rate"],
             "uniform-control rate drifted from bound evidence")

    for text in (
        "CANONICAL — OWNER-LOCKED",
        "structured-search system with complete nonce-estate coverage",
        "canonical production search identity is **Hendrix**",
        "O(1) candidate",
        "SHA256d",
    ):
        _require(text in doctrine, f"canonical doctrine phrase missing: {text}")

    link = "docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md"
    _require(link in readme, "root README no longer points to canonical search doctrine")
    _require(link in mining_readme, "mining README no longer points to canonical search doctrine")
    _require("Hendrix" in readme and "structured" in readme.lower(),
             "root README no longer exposes structured Hendrix search")
    _require("Hendrix" in mining_readme and "structured" in mining_readme.lower(),
             "mining README no longer exposes structured Hendrix search")


def main() -> int:
    try:
        validate()
    except (CanonicalSearchDoctrineError, KeyError, OSError, ValueError) as exc:
        print(f"FAIL — canonical PYTHIA structured-search doctrine: {exc}")
        return 1
    print("PASS — canonical PYTHIA structured-search doctrine is intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
