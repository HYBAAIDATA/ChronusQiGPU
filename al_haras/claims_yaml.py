"""12.8 Claims <-> Release Gate: the claims.yaml transport.

Every claim in the registry carries a status and its evidence. VERIFIED
claims must name a reproduction command, an artifact hash, a baseline, and
an evidence pack. REFUTED claims need a negative-results log. PROHIBITED
claims must be absent from external material. HYPOTHESIS claims stay
isolated under experiments/. The release gate reproduces — it never trusts.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml


class ClaimLevel(str, Enum):
    REFUTED = "REFUTED"
    UNTESTED = "UNTESTED"
    HYPOTHESIS = "HYPOTHESIS"
    REFERENCE = "REFERENCE"
    VERIFIED = "VERIFIED"
    PILOT = "PILOT"
    PRODUCTION = "PRODUCTION"
    PROHIBITED = "PROHIBITED"


EXPERIMENT_ROOTS = ("experiments", "legacy", "reports", "bench")


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    text: str
    status: ClaimLevel
    test_command: str = ""
    artifact: str = ""
    artifact_hash: str = ""
    baseline: str = ""
    evidence_pack: str = ""
    negative_results_log: str = ""
    isolated_under: str = ""


@dataclass(frozen=True)
class ClaimsRegistry:
    version: int
    claims: tuple[ClaimRecord, ...]


@dataclass(frozen=True)
class ReleaseReport:
    passed: bool
    violations: tuple[str, ...]


def load_claims(path: str | Path) -> ClaimsRegistry:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    claims = tuple(
        ClaimRecord(
            claim_id=str(c.get("id", "")),
            text=str(c.get("text", "")),
            status=ClaimLevel(str(c.get("status", "UNTESTED"))),
            test_command=str(c.get("test_command", "") or ""),
            artifact=str(c.get("artifact", "") or ""),
            artifact_hash=str(c.get("artifact_hash", "") or ""),
            baseline=str(c.get("baseline", "") or ""),
            evidence_pack=str(c.get("evidence_pack", "") or ""),
            negative_results_log=str(c.get("negative_results_log", "") or ""),
            isolated_under=str(c.get("isolated_under", "") or ""),
        )
        for c in (document.get("claims") or [])
    )
    return ClaimsRegistry(version=int(document.get("version", 0) or 0), claims=claims)


def _external_text(root: Path, external_dirs: tuple[str, ...]) -> list[tuple[str, str]]:
    corpus: list[tuple[str, str]] = []
    for rel in external_dirs:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*") if base.is_dir() else [base]:
            if path.is_file() and path.suffix in (".md", ".txt", ".rst", ".html"):
                corpus.append((str(path.relative_to(root)), path.read_text(errors="replace")))
    return corpus


def _contract_violations(
    registry: ClaimsRegistry, root: Path, external_dirs: tuple[str, ...]
) -> list[str]:
    violations: list[str] = []
    corpus: list[tuple[str, str]] | None = None
    for claim in registry.claims:
        if not claim.claim_id or not claim.text:
            violations.append(f"{claim.claim_id or '?'}: claim missing id/text (C1)")
        if claim.status is ClaimLevel.VERIFIED:
            if not claim.test_command:
                violations.append(f"{claim.claim_id}: VERIFIED without test_command (C2)")
            if not claim.baseline:
                violations.append(f"{claim.claim_id}: VERIFIED without baseline (C4)")
            if claim.artifact and claim.artifact_hash:
                artifact = root / claim.artifact
                if not artifact.exists():
                    violations.append(f"{claim.claim_id}: artifact {claim.artifact} absent")
                elif (
                    hashlib.sha256(artifact.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                    != claim.artifact_hash
                ):
                    violations.append(f"{claim.claim_id}: artifact_hash mismatch (C3)")
            elif claim.artifact or claim.artifact_hash:
                violations.append(
                    f"{claim.claim_id}: artifact and artifact_hash must appear together"
                )
        if claim.status is ClaimLevel.REFUTED and not claim.negative_results_log:
            violations.append(f"{claim.claim_id}: REFUTED without negative results log (C5)")
        if claim.status is ClaimLevel.PROHIBITED:
            if corpus is None:
                corpus = _external_text(root, external_dirs)
            hits = [name for name, body in corpus if claim.text in body]
            if hits:
                violations.append(
                    f"{claim.claim_id}: PROHIBITED claim found in {sorted(set(hits))} (C6/G2)"
                )
        if claim.status is ClaimLevel.HYPOTHESIS:
            if not claim.isolated_under or not claim.isolated_under.startswith(EXPERIMENT_ROOTS):
                violations.append(
                    f"{claim.claim_id}: HYPOTHESIS not isolated under experiments/ (C7)"
                )
    return violations


def evaluate_release(
    registry: ClaimsRegistry,
    root: str | Path,
    *,
    external_dirs: tuple[str, ...] = ("docs", "README.md"),
    reproduce: bool = False,
    timeout: int = 120,
) -> ReleaseReport:
    """G1–G4: the gate passes only when every contract holds — and, when
    ``reproduce`` is set, every VERIFIED claim's test_command exits 0."""
    root = Path(root)
    violations = _contract_violations(registry, root, external_dirs)
    for claim in registry.claims:
        if claim.status in (ClaimLevel.PILOT, ClaimLevel.PRODUCTION) and not claim.evidence_pack:
            violations.append(f"{claim.claim_id}: promoted claim lacks evidence pack (G3)")
        if reproduce and claim.status is ClaimLevel.VERIFIED and claim.test_command:
            proc = subprocess.run(
                claim.test_command,
                shell=True,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode != 0:
                violations.append(
                    f"{claim.claim_id}: reproduction failed (G1) — "
                    f"{(proc.stderr or proc.stdout).strip()[:200]}"
                )
    return ReleaseReport(passed=not violations, violations=tuple(violations))


__all__ = [name for name in globals() if not name.startswith("_")]
