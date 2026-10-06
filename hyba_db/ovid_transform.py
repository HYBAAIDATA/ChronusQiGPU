"""OVID transform plane for the file registry (M3 §7).

Registers OVID-folded transform artifacts as child versions of an already
registered file version, records the declared transform contract and
exactness on the ``file_versions`` row, and verifies equivalence by actually
unfolding — a transform is only ever *promoted* (recorded with an
``EXACT`` contract) when the unfold reproduces the source bytes exactly.

Fail-closed rules:

* an undeclared transform version is refused (``SchemaVersionError`` from
  the enterprise ``OvidRegistry.contract`` — no implicit classification);
* ``require_exact=True`` (the default) rejects any contract whose exactness
  is not ``Exactness.EXACT``;
* an unfolded payload that differs from the source raises
  ``IntegrityFailure`` — the artifact is never registered;
* the child version exists only when source bytes, folded bytes and the
  equivalence verdict all agree.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .file_registry import FileRegistry, _id, _json, _sha
from .models import AccessDenied, IntegrityFailure, InvalidRecord


def _version_row(files: FileRegistry, tenant_id: str, version_id: str) -> Any:
    row = files.store._db.execute(
        "SELECT fv.*, fo.logical_name FROM file_versions fv "
        "JOIN file_objects fo ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
        "WHERE fv.tenant_id=? AND fv.file_version_id=?",
        (tenant_id, version_id),
    ).fetchone()
    if not row:
        raise AccessDenied(f"file version not found in tenant: {version_id}")
    return row


def _read_version_bytes(row: Any) -> bytes:
    uri = str(row["storage_uri"])
    if not uri.startswith("file://"):
        raise InvalidRecord(f"transform source is not a local blob: {uri!r}")
    path = Path(uri[7:])
    if not path.is_file():
        raise IntegrityFailure(f"transform source blob missing: {path}")
    data = path.read_bytes()
    if _sha(data) != row["content_sha256"]:
        raise IntegrityFailure(
            f"transform source blob digest diverged from registry: {row['file_version_id']}"
        )
    return data


class OvidTransformPlane:
    """Records OVID transform lineage on the hyba_db file plane."""

    def __init__(self, files: FileRegistry, *, registry: Any | None = None) -> None:
        self.files = files
        if registry is None:
            from aethel.enterprise.ovid_registry import DEFAULT_OVID_REGISTRY

            registry = DEFAULT_OVID_REGISTRY
        self.registry = registry

    def fold_into(
        self,
        tenant_id: str,
        root: str | Path,
        source_version_id: str,
        *,
        transform_version: int = 1,
        require_exact: bool = True,
        producer: str = "ovid",
        custody_record_id: str | None = None,
    ) -> dict[str, Any]:
        """Fold one registered version and register the transform artifact.

        Returns the recorded transform lineage (OVID-compatible form):
        transform id/version, contract version, exactness, producer,
        input/output digests and the measured equivalence verdict.
        """
        self.files._tenant(tenant_id)
        row = _version_row(self.files, tenant_id, source_version_id)
        source = _read_version_bytes(row)
        # The contract must exist and be declared — OvidRegistry.contract
        # fails closed on undeclared versions.
        contract = self.registry.contract(transform_version)
        exactness = getattr(getattr(contract, "exactness", None), "value", None)
        if require_exact and exactness != "EXACT":
            raise InvalidRecord(
                f"transform v{transform_version} exactness={exactness!r}; "
                "EXACT required for promotion"
            )
        folded = self.registry.fold(source, transform_version)
        verdict = self._verify_equivalence(source, folded, transform_version)
        if not verdict["equivalent"]:
            raise IntegrityFailure("OVID transform failed equivalence: " + verdict["detail"])
        lineage_id = _id(
            "ovt",
            _json(
                {
                    "source": row["content_sha256"],
                    "transform": transform_version,
                    "out": verdict["output_sha256"],
                }
            ).encode(),
        )
        contract_doc = {
            "transform_id": contract.transform_id,
            "transform_version": int(transform_version),
            "contract_version": contract.version,
            "exactness": exactness,
            "reversible": bool(contract.reversible),
            "producer": producer,
            "input_sha256": verdict["input_sha256"],
            "output_sha256": verdict["output_sha256"],
            "input_bytes": len(source),
            "equivalence": verdict,
        }
        object_id = self.files.create_object(
            tenant_id,
            logical_name=f"{row['logical_name']}.ovid-v{transform_version}",
            file_class="transform",
            semantic_owner="ovid",
            domain=f"transform:{contract.transform_id}",
        )
        digest = hashlib.sha256(folded).hexdigest()
        base = Path(root) / tenant_id / "transform" / digest[:2]
        base.mkdir(parents=True, exist_ok=True)
        final = base / digest
        temp = base / f".{digest}.tmp"
        temp.write_bytes(folded)
        temp.replace(final)
        version_id = self.files.register_version(
            tenant_id,
            object_id,
            folded,
            storage_uri=f"file://{final}",
            logical_path=str(final),
            producer=producer,
            producer_version="ovid-registry/1",
            schema_version=int(transform_version),
            evidence_state="PASS",
            custody_record_id=custody_record_id,
            ovid_lineage_id=lineage_id,
            transform_contract=_json(contract_doc),
            transform_version=int(transform_version),
            exactness=exactness,
        )
        self.files.link(
            tenant_id,
            version_id,
            "file_version",
            source_version_id,
            relationship="transformed_from",
        )
        self.files.append_event(
            tenant_id,
            source_version_id,
            "TRANSFORMED",
            actor=producer,
            detail={
                "transform_version": transform_version,
                "lineage_id": lineage_id,
                "output_version_id": version_id,
            },
        )
        self.files.append_event(
            tenant_id,
            version_id,
            "TRANSFORMED",
            actor=producer,
            detail={"lineage_id": lineage_id, "source_version_id": source_version_id},
        )
        return {
            "lineage_id": lineage_id,
            "source_version_id": source_version_id,
            "transform_version_id": version_id,
            "transform_object_id": object_id,
            "transform_contract": contract_doc,
            "equivalence": verdict,
        }

    def _verify_equivalence(
        self, source: bytes, folded: bytes, transform_version: int
    ) -> dict[str, Any]:
        input_sha = hashlib.sha256(source).hexdigest()
        try:
            unfolded = self.registry.unfold(folded, transform_version)
        except Exception as exc:
            return {
                "transform_version": transform_version,
                "state": "FAIL",
                "equivalent": False,
                "input_sha256": input_sha,
                "output_sha256": hashlib.sha256(folded).hexdigest(),
                "detail": f"unfold refused the working form: {exc}",
            }
        equivalent = unfolded == source
        return {
            "transform_version": transform_version,
            "state": "PASS" if equivalent else "FAIL",
            "equivalent": equivalent,
            "input_sha256": input_sha,
            "output_sha256": hashlib.sha256(folded).hexdigest(),
            "detail": "" if equivalent else "materialised bytes differ from source",
        }


__all__ = ["OvidTransformPlane"]
