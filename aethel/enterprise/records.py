"""Common operational-record contract for THESEUS durable custody.

Every producer subsystem (Chronus, Turing, OVID, Tensor, PYTHIA, Salamander,
AL HARAS, approved EUCLID/TOE workflows) writes one :class:`OperationalRecord`
shape into custody. THESEUS validates the *contract* — registered producer,
supported schema version, declared evidence state, dependency compatibility,
and a content digest that binds to the payload — but never adjudicates the
record's semantics. A ``FAIL`` or ``REFUTED`` record is stored verbatim:
custody preserves meaning; the producer owns meaning.

Evidence states are explicit and never substituted:
PASS / FAIL / MEASURED / GATED / UNAVAILABLE / MISSING / REFUTED.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from .authenticity import content_digest
from .errors import EnterpriseCustodyError, SchemaVersionError

# ---------------------------------------------------------------------------
# Evidence taxonomy (shared doctrine — states are never optimistic defaults)
# ---------------------------------------------------------------------------

EVIDENCE_STATES = frozenset(
    {"PASS", "FAIL", "MEASURED", "GATED", "UNAVAILABLE", "MISSING", "REFUTED"}
)

#: Canonical producer names. Registration is fail-closed: a producer absent
#: from the registry is not an approved workflow and its record is refused.
CANONICAL_PRODUCERS = (
    "chronus",
    "turing",
    "ovid",
    "tensor",
    "pythia",
    "salamander",
    "al_haras",
    "euclid",
    "toe",
)

#: Dependency namespaces THESEUS can verify itself. A record that declares a
#: requirement in one of these namespaces is checked against the supplied
#: dependency policy; a requirement in an unknown namespace is unverifiable
#: and therefore refused (fail closed — dependency mismatch is a fault class,
#: not a warning).
DEPENDENCY_THESEUS_FORMAT = "theseus_format"
DEPENDENCY_OVID_TRANSFORM = "ovid_transform"


class ProducerAdmissionError(EnterpriseCustodyError):
    """Record rejected: unregistered producer or unsupported schema version."""


class ContractValidationError(EnterpriseCustodyError):
    """Record rejected: malformed contract fields or digest binding failure."""


class DependencyMismatchError(SchemaVersionError):
    """Record rejected: declared dependency is unsupported or unverifiable."""


# ---------------------------------------------------------------------------
# Producer registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProducerContract:
    """Admission contract for one producer subsystem.

    ``schema_versions`` is the inclusive (min, max) contract-version window
    THIS custody deployment agrees to store for this producer. Producers own
    their semantics; the window exists so a stale/newer-than-supported record
    is refused at admission instead of discovered on recovery.
    """

    name: str
    min_schema_version: int = 1
    max_schema_version: Optional[int] = None

    def supports(self, schema_version: int) -> bool:
        if schema_version < self.min_schema_version:
            return False
        if self.max_schema_version is not None and (schema_version > self.max_schema_version):
            return False
        return True


class ProducerRegistry:
    """Fail-closed registry of approved producers."""

    def __init__(self, contracts: Iterable[ProducerContract] = ()) -> None:
        self._contracts: dict[str, ProducerContract] = {}
        for contract in contracts:
            self.register(contract)

    def register(self, contract: ProducerContract) -> None:
        if not contract.name or not contract.name.strip():
            raise ContractValidationError("producer name must be non-empty")
        if contract.min_schema_version < 1:
            raise ContractValidationError("min_schema_version must be >= 1")
        if (
            contract.max_schema_version is not None
            and contract.max_schema_version < contract.min_schema_version
        ):
            raise ContractValidationError("max_schema_version must be >= min_schema_version")
        self._contracts[contract.name] = contract

    def contract(self, name: str) -> Optional[ProducerContract]:
        return self._contracts.get(name)

    def admits(self, name: str, schema_version: int) -> bool:
        contract = self._contracts.get(name)
        return contract is not None and contract.supports(schema_version)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._contracts))


def default_producer_registry() -> ProducerRegistry:
    """Canonical producers, unbounded schema window (>= 1).

    Deployment may tighten per-producer windows; the default admits every
    canonical producer at any positive declared contract version.
    """
    return ProducerRegistry(ProducerContract(name=p) for p in CANONICAL_PRODUCERS)


def default_dependency_policy(
    *,
    theseus_format_version: int,
    ovid_transform_versions: Iterable[int],
) -> dict[str, tuple[int, ...]]:
    """Dependency namespaces THESEUS verifies by default."""
    return {
        DEPENDENCY_THESEUS_FORMAT: (int(theseus_format_version),),
        DEPENDENCY_OVID_TRANSFORM: tuple(int(v) for v in ovid_transform_versions),
    }


# ---------------------------------------------------------------------------
# Operational record
# ---------------------------------------------------------------------------


@dataclass
class OperationalRecord:
    """One producer-authored operational record bound for durable custody.

    The payload is opaque bytes; ``content_digest`` is the producer-declared
    SHA-256 of the payload and MUST equal the recomputed digest at admission —
    that binding is what makes later corruption detectable. Everything else is
    declared provenance stored verbatim.
    """

    record_id: str
    producer: str
    producer_version: str
    schema_version: int
    kind: str
    payload: bytes
    content_digest: str = ""
    evidence_state: str = "MISSING"
    timestamp: float = 0.0
    sequence: int = 0
    epoch: str = ""
    lineage: tuple[str, ...] = ()
    correlation_ids: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, int] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.producer = str(self.producer).strip().lower()
        self.kind = str(self.kind).strip()
        self.evidence_state = str(self.evidence_state).strip().upper()
        self.schema_version = int(self.schema_version)
        self.sequence = int(self.sequence)
        if not self.timestamp:
            self.timestamp = time.time()
        if not isinstance(self.payload, (bytes, bytearray)):
            raise ContractValidationError("payload must be bytes")
        self.payload = bytes(self.payload)
        if not self.content_digest:
            self.content_digest = content_digest(self.payload)
        self.lineage = tuple(str(x) for x in self.lineage)
        self.correlation_ids = {str(k): str(v) for k, v in dict(self.correlation_ids).items()}
        self.dependencies = {str(k): int(v) for k, v in dict(self.dependencies).items()}

    # -- contract shape ---------------------------------------------------

    def manifest(self) -> dict[str, Any]:
        """Provenance manifest (everything except the payload itself)."""
        return {
            "record_id": self.record_id,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "schema_version": self.schema_version,
            "kind": self.kind,
            "evidence_state": self.evidence_state,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "epoch": self.epoch,
            "lineage": list(self.lineage),
            "correlation_ids": dict(self.correlation_ids),
            "dependencies": dict(self.dependencies),
            "content_digest": self.content_digest,
            "meta": dict(self.meta),
        }

    def manifest_digest(self) -> str:
        """SHA-256 over canonical manifest — stable record identity hash."""
        import json

        text = json.dumps(self.manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        import base64

        out = self.manifest()
        out["payload_b64"] = base64.b64encode(self.payload).decode("ascii")
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OperationalRecord":
        import base64

        return cls(
            record_id=str(data["record_id"]),
            producer=str(data["producer"]),
            producer_version=str(data.get("producer_version", "")),
            schema_version=int(data.get("schema_version", 1)),
            kind=str(data.get("kind", "")),
            payload=base64.b64decode(str(data.get("payload_b64", ""))),
            content_digest=str(data.get("content_digest", "")),
            evidence_state=str(data.get("evidence_state", "MISSING")),
            timestamp=float(data.get("timestamp", 0.0)),
            sequence=int(data.get("sequence", 0)),
            epoch=str(data.get("epoch", "")),
            lineage=tuple(data.get("lineage") or ()),
            correlation_ids=dict(data.get("correlation_ids") or {}),
            dependencies=dict(data.get("dependencies") or {}),
            meta=dict(data.get("meta") or {}),
        )

    # -- admission ---------------------------------------------------------

    def validate(
        self,
        registry: ProducerRegistry,
        dependency_policy: Mapping[str, tuple[int, ...]],
    ) -> None:
        """Fail-closed contract admission.

        Checks, in order: producer registered → schema version inside the
        producer's admitted window → record id non-empty → evidence state a
        member of the explicit taxonomy → declared digest recomputes over the
        payload → every declared dependency is verifiable and satisfied.
        Raises a typed error on first failure; returns None on admit.
        """
        contract = registry.contract(self.producer)
        if contract is None:
            raise ProducerAdmissionError(f"unregistered producer: {self.producer!r}")
        if not contract.supports(self.schema_version):
            raise ProducerAdmissionError(
                f"producer={self.producer} schema_version={self.schema_version} "
                f"outside admitted window "
                f"[{contract.min_schema_version}, {contract.max_schema_version}]"
            )
        if not self.record_id:
            raise ContractValidationError("record_id must be non-empty")
        if not self.kind:
            raise ContractValidationError("kind must be non-empty")
        if self.evidence_state not in EVIDENCE_STATES:
            raise ContractValidationError(
                f"unknown evidence_state={self.evidence_state!r}; "
                f"must be one of {sorted(EVIDENCE_STATES)}"
            )
        actual = content_digest(self.payload)
        if actual != self.content_digest:
            raise ContractValidationError(
                f"declared content_digest does not match payload for " f"record_id={self.record_id}"
            )
        for dep_name, dep_version in sorted(self.dependencies.items()):
            supported = dependency_policy.get(dep_name)
            if supported is None:
                raise DependencyMismatchError(
                    f"dependency {dep_name!r} has no verification policy — "
                    f"unverifiable, refusing (fail closed)"
                )
            if dep_version not in supported:
                raise DependencyMismatchError(
                    f"dependency {dep_name}={dep_version} not in supported " f"versions {supported}"
                )


__all__ = [
    "EVIDENCE_STATES",
    "CANONICAL_PRODUCERS",
    "DEPENDENCY_THESEUS_FORMAT",
    "DEPENDENCY_OVID_TRANSFORM",
    "ProducerAdmissionError",
    "ContractValidationError",
    "DependencyMismatchError",
    "ProducerContract",
    "ProducerRegistry",
    "OperationalRecord",
    "default_producer_registry",
    "default_dependency_policy",
]
