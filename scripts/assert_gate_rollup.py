"""Fail-closed validation of the existing assurance-gate evidence path.

An assurance PASS is not an API production-readiness certificate.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

try:
    from scripts.gate_runner import artifact_digest, canonical_digest, current_commit
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from gate_runner import artifact_digest, canonical_digest, current_commit

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON_BYTES = 4 * 1024 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path):
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("oversized JSON")
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )


def load_manifest(path: Path) -> list[str]:
    payload = read_json(path)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("invalid manifest schema")
    gates = payload.get("mandatory_gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("mandatory gates must be a nonempty list")
    if any(not isinstance(g, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", g)
           for g in gates):
        raise ValueError("invalid mandatory gate identity")
    if len(set(gates)) != len(gates):
        raise ValueError("duplicate mandatory gate")
    return gates


def _validate(payload: dict, root: Path, commit: str) -> None:
    if payload.get("schema_version") != 2:
        raise ValueError("unsupported evidence schema")
    gate = payload.get("gate")
    if not isinstance(gate, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", gate):
        raise ValueError("invalid gate identity")
    if payload.get("status") not in {"PASS", "FAIL", "SKIP", "ERROR"}:
        raise ValueError("invalid gate status")
    if payload.get("source_commit") != commit:
        raise ValueError("stale or missing source commit")
    if not isinstance(payload.get("execution"), str) or not payload["execution"].strip():
        raise ValueError("missing execution identity")
    if not isinstance(payload.get("reason"), str):
        raise ValueError("missing reason")
    begin, finish = payload.get("started_at"), payload.get("finished_at")
    if type(begin) is not int or type(finish) is not int or begin <= 0 or finish < begin:
        raise ValueError("invalid execution timestamps")
    digest = payload.get("evidence_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("missing evidence digest")
    if canonical_digest(payload) != digest:
        raise ValueError("evidence digest mismatch")
    artifacts, digests = payload.get("artifacts"), payload.get("artifact_digests")
    if not isinstance(artifacts, list) or not isinstance(digests, dict):
        raise ValueError("invalid artifact evidence")
    if any(not isinstance(p, str) or not p for p in artifacts):
        raise ValueError("invalid artifact path")
    if len(set(artifacts)) != len(artifacts) or set(artifacts) != set(digests):
        raise ValueError("artifact coverage mismatch")
    for path in artifacts:
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("non-canonical artifact path")
        if artifact_digest(root, path) != digests[path]:
            raise ValueError("artifact missing or tampered")


def evaluate(results_dir: Path, *, repo_root: Path = ROOT,
             expected_commit: str | None = None, manifest_path: Path | None = None) -> dict:
    root = repo_root.resolve()
    errors: list[str] = []
    observed: dict[str, dict] = {}
    duplicates: list[str] = []
    ignored: list[str] = []
    required: list[str] = []
    commit = expected_commit or ""
    try:
        head = current_commit(root)
        commit = expected_commit or head
        if commit != head:
            raise ValueError("requested commit differs from checkout")
        required = load_manifest(manifest_path or root / "config/assurance-gates.json")
    except Exception as exc:
        # Fail closed even when git itself is absent or crashes; don't expose its output.
        errors.append(f"configuration: {type(exc).__name__}")
    seen: set[str] = set()
    for path in sorted(results_dir.glob("*.json")):
        try:
            payload = read_json(path)
            if not isinstance(payload, dict):
                raise ValueError("gate evidence must be an object")
            if "gate" not in payload and path.stem not in required:
                ignored.append(path.name)
                continue
            gate = payload.get("gate")
            if isinstance(gate, str):
                if gate in seen:
                    duplicates.append(gate)
                seen.add(gate)
            _validate(payload, root, commit)
            if gate not in required:
                raise ValueError("gate not declared in manifest")
            if path.name != f"{gate}.json":
                raise ValueError("non-canonical gate result filename")
            observed[gate] = payload
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    missing = sorted(set(required) - set(observed))
    failed = sorted(g for g, p in observed.items() if p["status"] in {"FAIL", "ERROR"})
    skipped = sorted(g for g, p in observed.items() if p["status"] == "SKIP")
    return {
        "scope": "assurance_only_not_api_production_certification",
        "source_commit": commit, "required": required, "observed": sorted(observed),
        "missing": missing, "failed": failed, "skipped": skipped,
        "duplicates": sorted(set(duplicates)), "malformed": errors,
        "ignored_files": ignored,
        "evidence_digests": {g: p["evidence_digest"] for g, p in observed.items()},
        "passed": bool(required) and not (missing or failed or skipped or duplicates or errors),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--commit")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    report = evaluate(Path(args.results_dir), expected_commit=args.commit,
                      manifest_path=args.manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
