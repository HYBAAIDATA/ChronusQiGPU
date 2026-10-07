"""§9 module adapters: uniform evidence registration for named modules.

Every producer module that emits durable artifacts (PYTHIA, TURING, CHRONUS,
TENSOR, EUCLID, SALAMANDER, KELLOGG, AL HARAS, STRATUM, POOL, SHA256D, TOE)
registers through one adapter shape — producer name is validated against the
same registry THESEUS custody admission uses, so an adapter can never mint
artifacts under a producer name custody would refuse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .file_registry import FileRegistry
from .models import InvalidRecord
from .theseus_custody import FILE_PLANE_PRODUCERS


def _admissible_producers() -> frozenset[str]:
    from aethel.enterprise.records import CANONICAL_PRODUCERS

    return frozenset(set(CANONICAL_PRODUCERS) | set(FILE_PLANE_PRODUCERS))


class ModuleEvidenceAdapter:
    """One adapter per module; emits custodied, linked, content-addressed files."""

    def __init__(self, files: FileRegistry, module: str) -> None:
        module = str(module).strip().lower()
        if module not in _admissible_producers():
            raise InvalidRecord(f"module {module!r} is not a custody-admissible producer")
        self.files = files
        self.module = module

    def emit(
        self,
        tenant_id: str,
        root: str | Path,
        *,
        logical_name: str,
        content: bytes,
        file_class: str = "durable_evidence",
        domain: str | None = None,
        evidence_state: str = "MEASURED",
        custody_record_id: str | None = None,
        producer_version: str = "",
        schema_version: int = 1,
        provenance: Mapping[str, Any] | None = None,
        links: Sequence[tuple[str, str, str]] = (),
        detail: Mapping[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Register one durable artifact under this module's producer name."""
        object_id, version_id = self.files.put_file(
            tenant_id,
            root,
            logical_name=logical_name,
            file_class=file_class,
            semantic_owner=self.module,
            domain=domain or f"{self.module}:evidence",
            content=bytes(content),
            producer=self.module,
            producer_version=producer_version,
            schema_version=schema_version,
            evidence_state=evidence_state,
            custody_record_id=custody_record_id,
            provenance=provenance,
            links=links,
        )
        if detail:
            self.files.append_event(
                tenant_id,
                version_id,
                "REGISTERED",
                actor=self.module,
                detail=dict(detail),
            )
        return object_id, version_id

    def project_knowledge(
        self,
        tenant_id: str,
        *,
        subject: str,
        predicate: str,
        domain: str,
        object_value: Any,
        knowledge_kind: str,
        evidence_state: str,
        semantic_owner: str | None = None,
        knowledge_form: str = "unspecified",
        evidence_class: str | None = None,
        maturity_stage: str = "UNAVAILABLE",
        producer_version: str = "",
        schema_version: int = 1,
        source_ids: Sequence[str] = (),
        parent_ids: Sequence[str] = (),
        correlation_ids: Mapping[str, str] | None = None,
        provenance: Mapping[str, Any] | None = None,
        supersedes_id: str | None = None,
    ) -> Any:
        """Project producer-owned knowledge without transferring semantic authority."""
        return self.files.store.knowledge.project(
            tenant_id,
            subject=subject,
            predicate=predicate,
            domain=domain,
            object_value=object_value,
            knowledge_kind=knowledge_kind,
            knowledge_form=knowledge_form,
            semantic_owner=semantic_owner or self.module,
            producer=self.module,
            evidence_state=evidence_state,
            evidence_class=evidence_class,
            maturity_stage=maturity_stage,
            producer_version=producer_version,
            schema_version=schema_version,
            source_ids=source_ids,
            parent_ids=parent_ids,
            correlation_ids=correlation_ids,
            provenance=provenance,
            supersedes_id=supersedes_id,
        )


def adapters_for(files: FileRegistry, modules: Sequence[str]) -> dict[str, ModuleEvidenceAdapter]:
    """Build the declared adapter set, e.g. ``adapters_for(store.files, MODULES)``."""
    return {m: ModuleEvidenceAdapter(files, m) for m in modules}


MODULES = tuple(sorted(_admissible_producers()))

__all__ = ["ModuleEvidenceAdapter", "MODULES", "adapters_for"]
