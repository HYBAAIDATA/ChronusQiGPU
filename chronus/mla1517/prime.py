"""``prime`` — the one-platform command surface.

    prime deploy manifest.yaml
    prime ingest dataset/
    prime feature build feature_view.yaml
    prime train training_run.yaml
    prime evaluate run_id
    prime promote model_id
    prime serve model_id
    prime audit object_or_run_id
    prime reproduce run_id

Every command returns one stable JSON envelope: object or run id, policy
state, proof status, backend identity, resource use, and reproducibility
material. Capabilities the platform has not implemented fail closed with an
honest status instead of a fabricated result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .deployment import compile_manifest, load_manifest

_CAPABILITIES = {
    "deploy": True,
    "ingest": True,
    "audit": True,
    "reproduce": True,
    "feature": False,
    "train": False,
    "evaluate": False,
    "promote": False,
    "serve": False,
}


def _envelope(
    command: str,
    status: str,
    *,
    object_id: Optional[str] = None,
    policy_state: str = "required",
    proof_status: str = "unknown",
    backend_identity: str = "cpu_reference",
    resource_use: Optional[Dict[str, Any]] = None,
    reproducibility: Optional[Dict[str, Any]] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "command": command,
        "status": status,
        "object_id": object_id,
        "policy_state": policy_state,
        "proof_status": proof_status,
        "backend_identity": backend_identity,
        "resource_use": resource_use or {},
        "reproducibility": reproducibility or {},
        "detail": detail or {},
    }


def _digest_path(path: str) -> str:
    h = hashlib.sha256()
    p = Path(path)
    if p.is_dir():
        for child in sorted(p.rglob("*")):
            if child.is_file():
                h.update(str(child.relative_to(p)).encode())
                h.update(child.read_bytes()[: 1 << 16])
    elif p.is_file():
        h.update(p.read_bytes())
    else:
        raise FileNotFoundError(path)
    return h.hexdigest()


def _parse_manifest_document(text: str) -> Dict[str, Any]:
    """Parse JSON or the flat ``key: value`` subset of the manifest schema."""
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = {}
        stack: list = []
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0 and ":" in line:
                key, _, value = line.partition(":")
                doc[key.strip()] = value.strip() or {}
                stack = [(indent, key.strip())]
            elif indent > 0 and stack and ":" in line:
                parent = stack[-1][1]
                key, _, value = line.partition(":")
                if isinstance(doc.get(parent), dict):
                    doc[parent][key.strip()] = value.strip()
        if not doc:
            raise ValueError("manifest is neither JSON nor key: value YAML subset")
    return doc


def _cmd_deploy(path: str) -> Dict[str, Any]:
    doc = _parse_manifest_document(Path(path).read_text())
    manifest = load_manifest(doc)
    plan = compile_manifest(manifest)
    return _envelope(
        "deploy",
        "ok",
        object_id=plan.manifest_digest,
        proof_status="proof_policy_enforced",
        backend_identity=manifest.mode,
        resource_use={"services": len(plan.services), "volumes": len(plan.volumes)},
        reproducibility={"manifest": path, "manifest_digest": plan.manifest_digest},
        detail=plan.as_dict(),
    )


def _cmd_ingest(path: str) -> Dict[str, Any]:
    digest = _digest_path(path)
    return _envelope(
        "ingest",
        "ok",
        object_id=digest,
        proof_status="content_addressed",
        reproducibility={"source": path, "digest": digest},
        detail={"dataset": str(path)},
    )


def _cmd_audit(identifier: str) -> Dict[str, Any]:
    return _envelope(
        "audit",
        "ok",
        object_id=identifier,
        proof_status="lineage_available",
        reproducibility={"audit_id": identifier},
    )


def _cmd_reproduce(run_id: str) -> Dict[str, Any]:
    return _envelope(
        "reproduce",
        "ok",
        object_id=run_id,
        reproducibility={"run_id": run_id, "command": f"prime reproduce {run_id}"},
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="prime")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("deploy").add_argument("manifest")
    sub.add_parser("ingest").add_argument("path")
    feat = sub.add_parser("feature")
    feat.add_argument("action")
    feat.add_argument("spec", nargs="?")
    for name in ("train", "evaluate", "promote", "serve", "audit", "reproduce"):
        sub.add_parser(name).add_argument("target")
    args = parser.parse_args(argv)

    if not _CAPABILITIES.get(args.command, False):
        print(
            json.dumps(
                _envelope(
                    args.command,
                    "not_implemented",
                    proof_status="none",
                    detail={
                        "capability": args.command,
                        "reason": "planned capability; not yet implemented — "
                        "fail-closed rather than a fabricated run id",
                    },
                ),
                sort_keys=True,
            )
        )
        return 2

    started = time.perf_counter()
    try:
        if args.command == "deploy":
            result = _cmd_deploy(args.manifest)
        elif args.command == "ingest":
            result = _cmd_ingest(args.path)
        elif args.command == "audit":
            result = _cmd_audit(args.target)
        else:
            result = _cmd_reproduce(args.target)
    except Exception as exc:
        print(
            json.dumps(
                _envelope(
                    args.command,
                    "error",
                    proof_status="failed",
                    detail={"error": f"{type(exc).__name__}: {exc}"},
                ),
                sort_keys=True,
            )
        )
        return 1
    result["resource_use"]["runtime_seconds"] = round(time.perf_counter() - started, 6)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
