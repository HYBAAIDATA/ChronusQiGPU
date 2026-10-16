"""Sealed checkpoint manifest for governed EUCLID training artefacts.

A manifest links one trained learner checkpoint to the exact dataset
partitions, task/action contract, deduplication state, source revision and
evidence that produced it.  Restore paths verify the manifest seal and the
recorded learner-state hash before the checkpoint is consumed; corruption or
schema mismatch fails closed and is never silently skipped.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import canonical_json, domain_hash
from .evidence import load_json
from .manifest_integrity import require_sha256, validate_manifest_envelope
from hyba_substrate.memory_preservation import verified_atomic_json_write

MANIFEST_SCHEMA = "euclid.checkpoint-manifest/1"
POLICY_VERSION = "euclid.experience-policy/1"
SECRET_FIELD_TOKENS = ("password", "secret", "token", "credential", "api_key")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_secret_fields(value: Any, *, trail: str = "") -> None:
    """Refuse manifest fields whose names suggest credentials."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in SECRET_FIELD_TOKENS):
                raise ValueError(f"manifest field {trail + str(key)!r} may carry secrets")
            _reject_secret_fields(item, trail=f"{trail}{key}.")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_fields(item, trail=f"{trail}{index}.")


def dataset_partition_fingerprint(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Hash a partition of canonical case descriptors.

    Each descriptor must expose case_id, state, lineage_id, session_id and
    seed keys (as produced by ``TrainingCase.as_identity``).
    """
    canonical_json(list(cases))  # reject non-serializable partitions early
    entries = sorted(
        (
            str(case["case_id"]),
            str(case.get("lineage_id") or ""),
            str(case.get("session_id") or ""),
            "" if case.get("seed") is None else str(case["seed"]),
            canonical_json(case["state"]).decode("utf-8"),
        )
        for case in cases
    )
    return {
        "cases": len(entries),
        "lineages": len({(row[1], row[2], row[3]) for row in entries}),
        "hash": domain_hash("euclid.dataset-partition.v1", entries),
    }


def build_manifest(
    *,
    source_revision: str,
    task: Mapping[str, Any],
    learner: Mapping[str, Any],
    dataset: Mapping[str, Any],
    dedup: Mapping[str, Any],
    evidence: Mapping[str, Any],
    boundaries: Mapping[str, Any] | None = None,
    created_at: float | None = None,
    policy_version: str = POLICY_VERSION,
) -> dict[str, Any]:
    """Assemble a sealed manifest body (``seal`` covers every field)."""
    if not str(source_revision or "").strip():
        raise ValueError("source_revision is required and must be injectable")
    body = {
        "schema": MANIFEST_SCHEMA,
        "created_at": float(time.time() if created_at is None else created_at),
        "source_revision": str(source_revision),
        "policy_version": str(policy_version),
        "task": dict(task),
        "learner": dict(learner),
        "dataset": dict(dataset),
        "dedup": dict(dedup),
        "evidence": dict(evidence),
        "boundaries": dict(
            boundaries
            or {
                "live_pool_readiness": "NOT_CLAIMED",
                "hardware_readiness": "NOT_CLAIMED",
                "profitability": "NOT_CLAIMED",
                "production_readiness": "NOT_CLAIMED",
            }
        ),
    }
    _reject_secret_fields(body)
    return {**body, "seal": domain_hash("euclid.checkpoint-manifest.seal.v1", body)}


def write_manifest(
    path: str | Path,
    *,
    source_revision: str,
    task: Mapping[str, Any],
    learner: Mapping[str, Any],
    dataset: Mapping[str, Any],
    dedup: Mapping[str, Any],
    evidence: Mapping[str, Any],
    boundaries: Mapping[str, Any] | None = None,
    created_at: float | None = None,
    policy_version: str = POLICY_VERSION,
) -> dict[str, Any]:
    manifest = build_manifest(
        source_revision=source_revision,
        task=task,
        learner=learner,
        dataset=dataset,
        dedup=dedup,
        evidence=evidence,
        boundaries=boundaries,
        created_at=created_at,
        policy_version=policy_version,
    )
    verified_atomic_json_write(Path(path).resolve(), manifest)
    return manifest


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a manifest and verify schema plus seal; fail closed otherwise."""
    return validate_manifest_envelope(load_json(Path(path)))


def verify_manifest(
    manifest: Mapping[str, Any],
    *,
    learner_checkpoint_path: str | Path | None = None,
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    """Verify the envelope and artifact commitments on every entry path.

    A valid seal is integrity evidence, not publisher authentication or
    promotion approval. This function does not grant deployment authority.
    """
    manifest = validate_manifest_envelope(manifest)
    learner = dict(manifest["learner"])
    checkpoint = learner_checkpoint_path or learner.get("checkpoint_path")
    if not checkpoint:
        raise ValueError("manifest records no learner checkpoint path")
    checkpoint_path = Path(str(checkpoint))
    recorded_hash = require_sha256(learner.get("state_hash"), field="learner state_hash")
    if not checkpoint_path.is_file():
        raise ValueError(f"learner checkpoint missing: {checkpoint_path}")
    actual_hash = sha256_file(checkpoint_path)
    if recorded_hash != actual_hash:
        raise ValueError("learner checkpoint hash differs from manifest")
    evidence = dict(manifest["evidence"])
    selected_evidence = evidence_path if evidence_path is not None else evidence.get("report_path")
    evidence_verified = False
    if selected_evidence is not None:
        recorded_evidence = require_sha256(
            evidence.get("report_sha256"), field="evidence report_sha256"
        )
        evidence_file = Path(selected_evidence)
        if not evidence_file.is_file():
            raise ValueError(f"training evidence missing: {evidence_file}")
        if recorded_evidence != sha256_file(evidence_file):
            raise ValueError("training evidence hash differs from manifest")
        evidence_verified = True
    elif evidence.get("report_sha256"):
        raise ValueError("manifest records an evidence hash without an evidence path")
    return {
        "schema": "euclid.checkpoint-manifest.verification/1",
        "valid": True,
        "checkpoint_path": str(checkpoint_path),
        "learner_state_hash": actual_hash,
        "source_revision": manifest.get("source_revision"),
        "policy_version": manifest.get("policy_version"),
        "task_id": (manifest.get("task") or {}).get("task_id"),
        "evidence_verified": evidence_verified,
    }


__all__ = [
    "MANIFEST_SCHEMA",
    "POLICY_VERSION",
    "build_manifest",
    "dataset_partition_fingerprint",
    "load_manifest",
    "sha256_file",
    "verify_manifest",
    "write_manifest",
]
