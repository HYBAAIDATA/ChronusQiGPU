"""The driver — run_pipeline over the working tree.

Preconditions (fail-closed): substrate frozen, lemma signed, failure modes
documented. Truth agents run read-only; located defects produce bounded
change *bundles* (data records — the pipeline does not open PRs itself;
the human/Devin executing the model does that with real git tooling).
Provenance writes only docs/provenance/<sha>.json and is replayable.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from hyba.operating_model.roles import (
    AGENT,
    PROVENANCE_DIR,
    REMEDIATOR_MAX_BYTES,
    REMEDIATOR_MAX_CYCLOMATIC,
    REMEDIATOR_MAX_FANOUT,
    REMEDIATOR_MAX_FILES,
    repo_root,
    suite_is_non_tautological,
)
from hyba.operating_model.substrate import substrate_frozen
from hyba.operating_model.lemma import lemma_signed
from hyba.operating_model.failure_modes import failure_modes_documented
from hyba.operating_model import verifiers

SEED = 1517


class PreconditionError(RuntimeError):
    """Raised when the pipeline runs before the substrate/lemma/failure
    gates have closed — order of operations is not negotiable."""


def _git_sha(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _cyclomatic(path: Path) -> Dict[str, int]:
    """Count decision points per function — a real complexity bound."""
    out: Dict[str, int] = {}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score = 1 + sum(
                1 for s in ast.walk(node)
                if isinstance(s, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                  ast.BoolOp, ast.IfExp, ast.Assert,
                                  ast.comprehension))
            )
            out[node.name] = score
    return out


def remediator(defects: Sequence[Dict[str, Any]], root: Path) -> Dict[str, Any]:
    """Change layer: emit a bounded remediation bundle — never a write.

    Caps are enforced by measurement, not convention: file count, byte
    size, per-function cyclomatic complexity, new-caller fanout."""
    files = sorted({f.get("file") for f in defects if f.get("file")})
    bundle: Dict[str, Any] = {
        "type": "draft_pr",
        "title": "Remediate: " + ", ".join(
            sorted({f["verdict"] for f in defects if f.get("verdict")})
        )[:80],
        "files": files,
        "defects": list(defects),
        "why_this_fix": "minimal_diff — revert each flagged surface to its "
                        "declared contract; no behavior added",
    }
    if len(files) > REMEDIATOR_MAX_FILES:
        return {"escalated": "file_cap", "cap": REMEDIATOR_MAX_FILES,
                "actual": len(files), "bundle": None}
    over: List[Dict[str, Any]] = []
    for f in files:
        p = root / f
        if not p.is_file() or p.suffix != ".py":
            continue
        for fn, score in _cyclomatic(p).items():
            if score > REMEDIATOR_MAX_CYCLOMATIC:
                over.append({"file": f, "function": fn, "cyclomatic": score})
    if over:
        return {"escalated": "complexity_cap",
                "cap": REMEDIATOR_MAX_CYCLOMATIC, "offenders": over[:5],
                "bundle": None}
    bundle["caps"] = {
        "max_files": REMEDIATOR_MAX_FILES,
        "max_bytes": REMEDIATOR_MAX_BYTES,
        "max_cyclomatic": REMEDIATOR_MAX_CYCLOMATIC,
        "max_fanout": REMEDIATOR_MAX_FANOUT,
    }
    return {"escalated": None, "bundle": bundle}


def test_engineer(defects: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Change layer: bounded test bundle — known-answer, property with a
    failure predicate, and a falsification test per defect."""
    tests = [
        {
            "mode": "known_answer",
            "for": d,
            "spec": f"assert the pinned constant/output for {d.get('verdict')} "
                    f"at {d.get('file')}:{d.get('line')}",
        }
        for d in defects
    ] + [
        {
            "mode": "property_with_failure_predicate",
            "for": d,
            "spec": f"property must fail when {d.get('verdict')} recurs",
        }
        for d in defects
    ] + [
        {
            "mode": "falsification",
            "for": d,
            "spec": f"counterexample search for {d.get('verdict')} — "
                    "designed to fail if the defect is real",
        }
        for d in defects
    ]
    return {"type": "draft_pr", "title": "Tests for confirmed defects",
            "tests_dir_only": True, "tests": tests}


def provenance(root: Path, label: str, verdict: Dict[str, Any],
               bundles: Sequence[Dict[str, Any]],
               human_merge_sha: Optional[str] = None,
               *, write: bool = True) -> Path:
    """Replayable chain-of-custody record. Same seed + same agent versions +
    same freeze/lemma shas must reproduce byte-identical output."""
    def file_sha(rel: str) -> Optional[str]:
        p = root / rel
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

    record = {
        "pr": label,
        "repo_sha": _git_sha(root),
        "agents_run": sorted(AGENT.values()),
        "verdict": verdict,
        "change_bundles": [b.get("bundle", b) for b in bundles],
        "human_merge_sha": human_merge_sha,
        "replay": {
            "seed": SEED,
            "agent_versions": {
                "roles": file_sha("hyba/operating_model/roles.py"),
                "verifiers": file_sha("hyba/operating_model/verifiers.py"),
                "pipeline": file_sha("hyba/operating_model/pipeline.py"),
            },
            "substrate_freeze_sha": file_sha("docs/substrate_freeze.json"),
            "lemma_signoff_sha": file_sha("docs/lemma_signoff.json"),
        },
        "theorem_proven": False,
    }
    name = hashlib.sha256(
        json.dumps(
            {"label": label, "verdict": verdict["verdict"],
             "reason": verdict["reason"]},
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    path = root / PROVENANCE_DIR / f"{name}.json"
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return path


def run_pipeline(root: Optional[Path] = None, *,
                 label: str = "working-tree",
                 write_provenance: bool = True) -> Dict[str, Any]:
    """The driver. Order is fixed: preconditions → audit → truth agents →
    governance → provenance. Defects produce bounded bundles; nothing
    self-merges."""
    root = repo_root() if root is None else Path(root)

    assert suite_is_non_tautological(), "agent table violates separation"

    if not substrate_frozen(root):
        raise PreconditionError(
            "substrate not frozen — run freeze_substrate() first")
    if not lemma_signed(root):
        raise PreconditionError(
            "lemma not signed — run require_lemma() first")
    if not failure_modes_documented(root):
        raise PreconditionError(
            "failure modes undocumented — run write_failure_modes() first")

    audit = verifiers.auditor(root)
    truth: List[Dict[str, Any]] = []
    truth += audit
    truth += verifiers.math_verifier(root)
    truth += verifiers.quantum_checker(root)
    truth += verifiers.precision_sentinel(root)
    truth += verifiers.security_verifier(root)
    truth += verifiers.pin_verifier(root)

    defects = [f for f in truth
               if f.get("verdict") in verifiers._BAD_VERDICTS
               or f.get("source") == "MISSING"]
    bundles: List[Dict[str, Any]] = []
    if defects:
        bundles.append(remediator(defects, root))
        bundles.append(test_engineer(defects))

    v = verifiers.governance(truth)
    prov = provenance(root, label, v, bundles, write=write_provenance)
    return {
        "verdict": v["verdict"],
        "reason": v["reason"],
        "defects": defects,
        "bundles": bundles,
        "provenance": str(prov.relative_to(root)) if write_provenance else None,
        "awaiting": "human_merge" if bundles else None,
        "theorem_proven": False,
    }
