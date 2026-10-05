"""Ovid — metamorphosis owner: folded data is the working form.

Ovid owns encode/decode transformations for the Chronus·Theseus·Ovid triad:

* ``metamorphose`` / ``fold_working`` — bytes → folded working form (Zeckendorf)
* ``materialise`` / ``unfold_egress`` — folded form → bytes (edge only)

Compute and Theseus custody operate on the **folded** representation.
Unfold is egress/materialisation, not the ambient store format.

Every transform OVID offers is governed by a declared
:class:`TransformContract` carrying a mandatory exactness classification
(:class:`Exactness`): EXACT, BOUNDED_LOSS, APPROXIMATE or UNSUPPORTED.
``metamorphose`` emits a :class:`TransformLineage` — serializable
transformation provenance suitable for THESEUS durable custody — and
:meth:`Ovid.verify_equivalence` performs declared semantic-equivalence
validation returning an explicit evidence state, never an inferred one.

Not a claim of physical shape-shifting or universe history reversal.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .encoding import MAX_FOLD_LEN, fold, unfold
from .errors import FoldDomainOverflow, ZeckendorfInvariantError
from .zeckendorf import SparseTopology, apply_zeckendorf_compression


OWNER_ID = "ovid"
CLAIM_BOUNDARY = (
    "Ovid is the metamorphosis owner for HYBA storage: fold produces the "
    "working form; unfold materialises at the edge. Ovid does not reverse "
    "physical history, forge hash preimages, or abolish energy accounting."
)

#: Version of the declared-contract schema itself (not a transform version).
CONTRACT_VERSION = "ovid-contract/v1"

#: Transform id for the Zeckendorf bytes codec served by metamorphose/materialise.
ZECKENDORF_TRANSFORM_ID = "ovid.zeckendorf.fold"


class EvidenceState(str, Enum):
    """Explicit evidence states — never conflated, never inferred."""

    PASS = "PASS"
    FAIL = "FAIL"
    MEASURED = "MEASURED"
    GATED = "GATED"
    UNAVAILABLE = "UNAVAILABLE"
    MISSING = "MISSING"
    REFUTED = "REFUTED"


class Exactness(str, Enum):
    """Mandatory classification for every declared OVID transform.

    EXACT          — reversible, zero declared error; round-trip must prove
                     semantic equivalence bit/element-exactly.
    BOUNDED_LOSS   — lossy within a declared error bound recorded on the
                     contract; residual/support contract must be declared.
    APPROXIMATE    — heuristic; error is measured per execution, not bounded
                     a priori.
    UNSUPPORTED    — declared but not offered; any use fails closed.
    """

    EXACT = "EXACT"
    BOUNDED_LOSS = "BOUNDED_LOSS"
    APPROXIMATE = "APPROXIMATE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class TransformContract:
    """A declared transformation contract for one OVID transform.

    The contract is the normative description a transform is executed
    against: what domain it admits, which invariants must hold, how
    residuals are handled, and its exactness classification. ``owner``
    records which subsystem is attributable for the transform — an
    ``execution="external"`` entry is a classification reference to another
    subsystem's transform (e.g. PULVINI), never an OVID execution claim.
    """

    transform_id: str
    owner: str = OWNER_ID
    version: int = 1
    contract_version: str = CONTRACT_VERSION
    exactness: Exactness = Exactness.EXACT
    reversible: bool = True
    domain: Tuple[Tuple[str, Any], ...] = ()
    invariants: Tuple[str, ...] = ()
    residuals: str = ""
    error_bound: Optional[float] = None
    bound_source: str = ""
    support: str = ""
    execution: str = "local"  # "local" | "external"

    def validate(self) -> None:
        """Fail closed on an internally inconsistent declaration."""
        if not self.transform_id:
            raise ValueError("transform contract requires a transform_id")
        if self.version < 1:
            raise ValueError("transform contract version must be >= 1")
        if not isinstance(self.exactness, Exactness):
            raise ValueError(f"exactness must be an Exactness, got {self.exactness!r}")
        if self.exactness is Exactness.EXACT:
            if not self.reversible:
                raise ValueError("an EXACT transform must be declared reversible")
            if self.error_bound not in (None, 0.0):
                raise ValueError("an EXACT transform must declare zero error bound")
        if self.exactness is Exactness.BOUNDED_LOSS:
            declared = self.error_bound is not None and self.error_bound >= 0
            measured = bool(self.bound_source)
            if not (declared or measured):
                raise ValueError(
                    "a BOUNDED_LOSS transform must declare a non-negative "
                    "error_bound or a bound_source where the bound is measured"
                )
        if self.exactness is Exactness.UNSUPPORTED:
            # UNSUPPORTED means "declared, never executed": a contract that
            # claims executability would silently contradict the class.
            if self.execution == "local" and self.reversible:
                raise ValueError(
                    "an UNSUPPORTED transform cannot declare a local reversible path"
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transform_id": self.transform_id,
            "owner": self.owner,
            "version": int(self.version),
            "contract_version": self.contract_version,
            "exactness": self.exactness.value,
            "reversible": bool(self.reversible),
            "domain": dict(self.domain),
            "invariants": list(self.invariants),
            "residuals": self.residuals,
            "error_bound": self.error_bound,
            "bound_source": self.bound_source,
            "support": self.support,
            "execution": self.execution,
        }


@dataclass(frozen=True)
class TransformLineage:
    """Serializable transformation provenance — THESEUS-custody ready.

    One record per transform execution. Fields mirror the shared
    provenance contract: producer identity/version, contract version,
    input/output hashes, exactness, timestamp and parent lineage.
    """

    lineage_id: str
    transform_id: str
    transform_version: int
    contract_version: str
    exactness: str
    producer: str
    producer_version: str
    input_sha256: str
    output_digest: str
    input_bytes: int
    folded_units: int
    transform_ns: int
    parent_ids: Tuple[str, ...] = ()
    evidence_state: str = EvidenceState.PASS.value
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "transform_id": self.transform_id,
            "transform_version": int(self.transform_version),
            "contract_version": self.contract_version,
            "exactness": self.exactness,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "input_sha256": self.input_sha256,
            "output_digest": self.output_digest,
            "input_bytes": int(self.input_bytes),
            "folded_units": int(self.folded_units),
            "transform_ns": int(self.transform_ns),
            "parent_ids": list(self.parent_ids),
            "evidence_state": self.evidence_state,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransformLineage":
        return cls(
            lineage_id=str(data["lineage_id"]),
            transform_id=str(data["transform_id"]),
            transform_version=int(data["transform_version"]),
            contract_version=str(data["contract_version"]),
            exactness=str(data["exactness"]),
            producer=str(data["producer"]),
            producer_version=str(data["producer_version"]),
            input_sha256=str(data["input_sha256"]),
            output_digest=str(data["output_digest"]),
            input_bytes=int(data["input_bytes"]),
            folded_units=int(data["folded_units"]),
            transform_ns=int(data["transform_ns"]),
            parent_ids=tuple(str(p) for p in data.get("parent_ids", ())),
            evidence_state=str(data.get("evidence_state", EvidenceState.PASS.value)),
            detail=str(data.get("detail", "")),
        )


@dataclass(frozen=True)
class EquivalenceVerdict:
    """Machine-checkable semantic-equivalence result for one transform."""

    transform_id: str
    state: str  # EvidenceState value
    equivalent: bool
    input_sha256: str
    output_sha256: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transform_id": self.transform_id,
            "state": self.state,
            "equivalent": bool(self.equivalent),
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "detail": self.detail,
        }


def _producer_version() -> str:
    try:
        import aethel

        return str(getattr(aethel, "__version__", "unknown"))
    except Exception:
        return "unknown"


def _canonical_working_doc(vector: Any) -> bytes:
    """Canonical UTF-8 JSON form of a ZeckendorfVector (registry-stable)."""
    return json.dumps(
        {
            "kind": "zeckendorf_vector_v1",
            "blocks": [[int(o), int(m)] for o, m in vector.blocks],
            "total_bytes": int(vector.total_bytes),
            "folded_units": int(vector.folded_units),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def working_form_digest(vector: Any) -> str:
    """SHA-256 over the canonical transformed representation."""
    return hashlib.sha256(_canonical_working_doc(vector)).hexdigest()


#: Process-wide execution counter. `time.time_ns()` is not guaranteed to
#: advance between two folds on every platform (Windows timer granularity can
#: span two calls in one tick), so the nanosecond stamp alone cannot
#: distinguish executions; this sequence does.
_EXECUTION_SEQ = itertools.count()


def _lineage_id(
    transform_id: str,
    input_sha256: str,
    output_digest: str,
    transform_ns: int,
    execution_seq: int,
    parents: Tuple[str, ...],
) -> str:
    material = "|".join(
        (
            transform_id,
            input_sha256,
            output_digest,
            str(transform_ns),
            str(execution_seq),
            *parents,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class FoldedWorkingForm:
    """Canonical working representation after Ovid metamorphosis.

    ``lineage`` is the transformation-provenance record emitted at fold
    time; it travels with the form so any custodian (THESEUS) can persist
    it without re-deriving provenance.
    """

    vector: Any  # ZeckendorfVector
    sparse: SparseTopology
    digest: str
    raw_len: int
    folded_units: int
    owner: str = OWNER_ID
    lineage: Optional[TransformLineage] = None

    def verify(self) -> bool:
        try:
            if not bool(self.vector.verify()):
                return False
            # folded_units tracks the Zeckendorf vector; sparse is parallel witness
            if self.folded_units != int(self.vector.folded_units):
                return False
            if self.raw_len < 0:
                return False
            return True
        except Exception:
            return False


def _declared_contracts() -> Tuple[TransformContract, ...]:
    """The OVID transform inventory, each with a declared exactness class.

    Only OVID-owned transforms declare ``execution="local"``. The PULVINI
    entry is a classification reference — PULVINI is separately attributable
    and its execution stays in its own subsystem.
    """
    return (
        TransformContract(
            transform_id=ZECKENDORF_TRANSFORM_ID,
            version=1,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(
                ("payload_bytes_max", MAX_FOLD_LEN),
                ("chunk_bytes", 8),
                ("element", "bytes"),
            ),
            invariants=(
                "every mask satisfies non-adjacency: mask & (mask << 1) == 0",
                "every block offset is a non-negative multiple of 8",
                "total_bytes equals the source payload length",
                "source sha256 digest is bound to the working form",
            ),
            residuals=(
                "none — every 8-byte payload chunk retains a Zeckendorf mask; "
                "no information is discarded"
            ),
            error_bound=0.0,
            support=(
                "len(payload) <= declared max_fold_len (1 MiB default); larger "
                "payloads must be sharded upstream — folding never truncates"
            ),
        ),
        TransformContract(
            transform_id="ovid.phi_fold.numeric",
            version=1,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(
                ("dtypes", "numpy kinds i,u,f,c (int/uint/float/complex)"),
                ("min_segment_elements", 2),
                ("depth_min", 0),
                ("element", "ndarray"),
            ),
            invariants=(
                "fold is a contiguous partition of the flat C-order array",
                "all segments share the custodied dtype",
                "content_hash is sha256 over dtype, shape and all segment bytes",
            ),
            residuals=(
                "every complement segment is retained verbatim — reconstruction "
                "is concat(retained, reversed(complements))"
            ),
            error_bound=0.0,
            support="non-empty numeric ndarray; each fold level needs >= 2 retained elements",
        ),
        TransformContract(
            transform_id="ovid.phi_fold.splice",
            version=1,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(
                ("element", "NumericFoldState + KernelBoundary"),
                ("write_dtype", "must equal custodied dtype"),
            ),
            invariants=(
                "only segments intersecting the write region are copied",
                "untouched segments are shared verbatim with the parent state",
                "result is bit-identical to unfold -> write -> re-fold",
            ),
            residuals="none — regional write touches declared coordinates only",
            error_bound=0.0,
            support="boundary within original_size; values length == boundary length",
        ),
        TransformContract(
            transform_id="ovid.phi_fold.unfold_partial",
            version=1,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(
                ("element", "NumericFoldState + KernelBoundary or shaped region"),
                ("slice_step", "unit step only for shaped regions"),
            ),
            invariants=(
                "reconstructed span equals the same span of a full unfold",
                "only resident segments intersecting the boundary are read",
            ),
            residuals="none — addressed read, not an approximation",
            error_bound=0.0,
            support="boundary inside unfolded bounds; contiguous intervals per region axis",
        ),
        TransformContract(
            transform_id="ovid.phi_memory.refold",
            version=1,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(
                ("element", "TierResident / NumericFoldState"),
                ("tiers", "REGISTER(0) SRAM(1) L2(2) HBM(3+)"),
            ),
            invariants=(
                "tier change is unfold + re-fold — the full complement set is kept",
                "content_hash is recomputed and tracked on every transition",
            ),
            residuals="none — demotion deepens the fold, it never drops data",
            error_bound=0.0,
            support="promotion/demotion only changes fold depth of the same payload",
        ),
        TransformContract(
            transform_id="ovid.fold_store.checkpoint",
            version=1,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(
                ("element", "PersistentFoldStore -> .npz artifact"),
                ("format", "aethel-fold-store/v1"),
            ),
            invariants=(
                "every version's content_hash is re-verified on restore",
                "commit-id membership is rebuilt — exactly-once survives replay",
                "a tampered or foreign artifact fails closed at load",
            ),
            residuals="none — full version graph, lineage and commit records persisted",
            error_bound=0.0,
            support="allow_pickle=False npz; format tag enforced",
        ),
        TransformContract(
            transform_id="pulvini.svd_fold",
            owner="pulvini",
            version=1,
            exactness=Exactness.BOUNDED_LOSS,
            reversible=True,
            execution="external",
            domain=(
                ("element", "Hermitian/general matrix subspace projection"),
                ("basis", "energy-sorted SVD"),
            ),
            invariants=(
                "audit envelope records reconstruction_error_bound per fold",
                "spectral_gap_delta and topology_preserved are reported, not assumed",
            ),
            residuals=(
                "discarded singular directions are bounded by the audit envelope's "
                "reconstruction_error_bound and svd_truncation_mass"
            ),
            error_bound=None,
            bound_source=(
                "PulviniAuditEnvelope.reconstruction_error_bound — measured "
                "and emitted per fold by the owning subsystem"
            ),
            support=(
                "external owner — OVID classifies but does not execute; see "
                "quantum_compute_substrate/pulvini"
            ),
        ),
    )


#: The declared contract catalog for every transform in OVID's inventory.
OVID_TRANSFORM_CONTRACTS: Tuple[TransformContract, ...] = _declared_contracts()
for _contract in OVID_TRANSFORM_CONTRACTS:
    _contract.validate()


def transform_contract(transform_id: str) -> TransformContract:
    """Look up a declared contract; fail closed on unknown transforms."""
    for contract in OVID_TRANSFORM_CONTRACTS:
        if contract.transform_id == transform_id:
            return contract
    raise KeyError(f"no declared transform contract for {transform_id!r}")


@dataclass
class Ovid:
    """Production metamorphosis owner — fail-closed fold/unfold."""

    max_fold_len: int = MAX_FOLD_LEN
    owner_id: str = OWNER_ID
    _metrics: Dict[str, int] = field(
        default_factory=lambda: {
            "fold_ok": 0,
            "fold_reject": 0,
            "unfold_ok": 0,
            "unfold_reject": 0,
            "equivalence_pass": 0,
            "equivalence_fail": 0,
        }
    )

    @property
    def claim_boundary(self) -> str:
        return CLAIM_BOUNDARY

    def metamorphose(
        self, payload: bytes, *, parents: Tuple[str, ...] = ()
    ) -> FoldedWorkingForm:
        """Fold payload into the working form (primary ingress).

        ``parents`` carries upstream lineage ids (e.g. a THESEUS custody id
        or a producer run id) into the emitted :class:`TransformLineage`.
        """
        if not isinstance(payload, (bytes, bytearray)):
            self._metrics["fold_reject"] += 1
            raise TypeError("Ovid.metamorphose requires bytes")
        data = bytes(payload)
        try:
            vector = fold(data, max_fold_len=self.max_fold_len)
            sparse = apply_zeckendorf_compression(data)
        except FoldDomainOverflow:
            self._metrics["fold_reject"] += 1
            raise
        except Exception:
            self._metrics["fold_reject"] += 1
            raise
        if not vector.verify():
            self._metrics["fold_reject"] += 1
            raise ZeckendorfInvariantError(
                "folded working form failed verify()"
            )
        digest = hashlib.sha256(data).hexdigest()
        transform_ns = time.time_ns()
        lineage = TransformLineage(
            lineage_id=_lineage_id(
                ZECKENDORF_TRANSFORM_ID,
                digest,
                working_form_digest(vector),
                transform_ns,
                next(_EXECUTION_SEQ),
                tuple(str(p) for p in parents),
            ),
            transform_id=ZECKENDORF_TRANSFORM_ID,
            transform_version=1,
            contract_version=CONTRACT_VERSION,
            exactness=Exactness.EXACT.value,
            producer=self.owner_id,
            producer_version=_producer_version(),
            input_sha256=digest,
            output_digest=working_form_digest(vector),
            input_bytes=len(data),
            folded_units=int(vector.folded_units),
            transform_ns=transform_ns,
            parent_ids=tuple(str(p) for p in parents),
            evidence_state=EvidenceState.PASS.value,
        )
        form = FoldedWorkingForm(
            vector=vector,
            sparse=sparse,
            digest=digest,
            raw_len=len(data),
            folded_units=int(vector.folded_units),
            lineage=lineage,
        )
        if not form.verify():
            self._metrics["fold_reject"] += 1
            raise ZeckendorfInvariantError(
                "FoldedWorkingForm assembly failed verify()"
            )
        self._metrics["fold_ok"] += 1
        return form

    fold_working = metamorphose

    def materialise(self, form: FoldedWorkingForm) -> bytes:
        """Unfold working form to bytes (egress only)."""
        if not isinstance(form, FoldedWorkingForm):
            self._metrics["unfold_reject"] += 1
            raise TypeError("Ovid.materialise requires FoldedWorkingForm")
        if not form.verify():
            self._metrics["unfold_reject"] += 1
            raise ZeckendorfInvariantError(
                "working form failed verify before unfold"
            )
        try:
            out = unfold(form.vector)
        except Exception:
            self._metrics["unfold_reject"] += 1
            raise
        if len(out) != form.raw_len or hashlib.sha256(out).hexdigest() != form.digest:
            self._metrics["unfold_reject"] += 1
            raise ZeckendorfInvariantError(
                "materialise digest/length mismatch — refusing corrupt working form"
            )
        self._metrics["unfold_ok"] += 1
        return out

    unfold_egress = materialise

    def verify_equivalence(
        self, source: bytes, form: FoldedWorkingForm
    ) -> EquivalenceVerdict:
        """Declared semantic-equivalence validation for one transform.

        Materialises ``form`` and compares against ``source`` byte-exactly —
        the EXACT contract's equivalence relation. The verdict carries an
        explicit evidence state; a refused materialise or a mismatched
        payload is FAIL, never an exception smuggled as a pass.
        """
        transform_id = (
            form.lineage.transform_id
            if isinstance(form, FoldedWorkingForm) and form.lineage is not None
            else ZECKENDORF_TRANSFORM_ID
        )
        if not isinstance(source, (bytes, bytearray)):
            self._metrics["equivalence_fail"] += 1
            return EquivalenceVerdict(
                transform_id=transform_id,
                state=EvidenceState.FAIL.value,
                equivalent=False,
                input_sha256="",
                output_sha256="",
                detail="source is not bytes — equivalence requires byte evidence",
            )
        input_sha256 = hashlib.sha256(bytes(source)).hexdigest()
        try:
            out = self.materialise(form)
        except Exception as exc:
            self._metrics["equivalence_fail"] += 1
            return EquivalenceVerdict(
                transform_id=transform_id,
                state=EvidenceState.FAIL.value,
                equivalent=False,
                input_sha256=input_sha256,
                output_sha256="",
                detail=f"materialise refused the working form: {exc}",
            )
        output_sha256 = hashlib.sha256(out).hexdigest()
        equivalent = out == bytes(source)
        if not equivalent:
            self._metrics["equivalence_fail"] += 1
        else:
            self._metrics["equivalence_pass"] += 1
        return EquivalenceVerdict(
            transform_id=transform_id,
            state=EvidenceState.PASS.value if equivalent else EvidenceState.FAIL.value,
            equivalent=equivalent,
            input_sha256=input_sha256,
            output_sha256=output_sha256,
            detail="" if equivalent else "materialised bytes differ from source",
        )

    def round_trip(self, payload: bytes) -> Tuple[FoldedWorkingForm, bytes]:
        form = self.metamorphose(payload)
        return form, self.materialise(form)

    def working_digest(self, form: FoldedWorkingForm) -> str:
        return form.digest

    def transform_contracts(self) -> Tuple[TransformContract, ...]:
        """The declared contract catalog this Ovid executes under."""
        return OVID_TRANSFORM_CONTRACTS

    def contract_report(self) -> Dict[str, Any]:
        """Machine-readable contract inventory for provenance surfaces."""
        return {
            "contract_version": CONTRACT_VERSION,
            "transforms": [c.to_dict() for c in OVID_TRANSFORM_CONTRACTS],
        }

    def metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    def health(self) -> Dict[str, Any]:
        return {
            "owner": self.owner_id,
            "status": "ok",
            "max_fold_len": self.max_fold_len,
            "metrics": self.metrics(),
            "claim_boundary": CLAIM_BOUNDARY,
            "contract_version": CONTRACT_VERSION,
            "transforms": {
                "declared": len(OVID_TRANSFORM_CONTRACTS),
                "local": sum(
                    1 for c in OVID_TRANSFORM_CONTRACTS if c.execution == "local"
                ),
            },
            "production_surface": True,
        }


def open_ovid(*, max_fold_len: int = MAX_FOLD_LEN) -> Ovid:
    return Ovid(max_fold_len=max_fold_len)


__all__ = [
    "CONTRACT_VERSION",
    "CLAIM_BOUNDARY",
    "EvidenceState",
    "Exactness",
    "EquivalenceVerdict",
    "FoldedWorkingForm",
    "OWNER_ID",
    "OVID_TRANSFORM_CONTRACTS",
    "Ovid",
    "TransformContract",
    "TransformLineage",
    "ZECKENDORF_TRANSFORM_ID",
    "open_ovid",
    "transform_contract",
    "working_form_digest",
]
