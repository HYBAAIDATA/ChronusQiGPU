"""THESEUS custody consumption for the TURING VQC (WF05).

THESEUS owns durable custody, journalling, continuity, recovery and
provenance.  TURING consumes it for circuits, states, results, witnesses and
checkpoints; it does not keep a private store.  ``phi_machine.PhiCheckpoint``
remains an *in-memory* accelerator checkpoint only — durable custody of any
VQC artefact goes through this module.

Contract exercised:

* ``commit(kind, bytes, meta)`` — canonical-envelope serialise, Theseus.put;
* ``recover(uid)`` — Theseus.get (digest-verified heal path inside THESEUS)
  then envelope digest re-verified on the TURING side too;
* ``replay(uid)`` — recover + structural validation, producing a
  ``ReplayReport`` so a custody roundtrip is demonstrated, not assumed;
* ``verify(uid)`` — THESEUS-side heal/verify status surfaced as evidence.

When the aethel package is absent, custody is UNAVAILABLE and the pipeline
fails closed — no private substitute store is permitted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "CUSTODY_ENVELOPE_SCHEMA",
    "CustodyReceipt",
    "ReplayReport",
    "TuringCustody",
    "CustodyUnavailable",
    "CustodyError",
    "open_custody",
    "theseus_available",
    "canonical_envelope_bytes",
    "envelope_digest",
]

CUSTODY_ENVELOPE_SCHEMA = "turing.vqc.custody_envelope.v1"

#: Artefact kinds TURING may place into custody.
_ENVELOPE_KINDS = (
    "program",
    "state",
    "result",
    "witness",
    "certificate",
    "checkpoint",
)


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_envelope_bytes(
    kind: str,
    payload: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> bytes:
    """Canonical serialisation of one custody envelope (payload embedded)."""
    if kind not in _ENVELOPE_KINDS:
        raise ValueError(f"unknown custody kind {kind!r}; expected {_ENVELOPE_KINDS}")
    body = {"kind": kind, "payload": payload, "meta": meta or {}}
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    return _canonical({"schema": CUSTODY_ENVELOPE_SCHEMA, "digest": digest, **body})


def envelope_digest(envelope_bytes: bytes) -> str:
    """Recompute and return the digest a well-formed envelope must carry."""
    env = json.loads(envelope_bytes.decode("utf-8"))
    if env.get("schema") != CUSTODY_ENVELOPE_SCHEMA:
        raise CustodyError(f"unexpected envelope schema {env.get('schema')!r}")
    body = {"kind": env["kind"], "payload": env["payload"], "meta": env.get("meta", {})}
    recomputed = hashlib.sha256(_canonical(body)).hexdigest()
    if recomputed != env["digest"]:
        raise CustodyError("envelope digest mismatch — content altered after commit")
    return recomputed


def theseus_available() -> bool:
    try:
        from aethel import theseus as _theseus  # noqa: F401
    except Exception:
        return False
    return True


@dataclass(frozen=True)
class CustodyReceipt:
    """What THESEUS committed, in checkable form."""

    uid: str
    kind: str
    digest: str
    raw_len: int
    folded_units: int
    durable_index: int | None
    state: str  # PASS
    backend: str = "theseus"

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ReplayReport:
    """Evidence that a custody artefact replayed correctly."""

    uid: str
    kind: str
    digest_verified: bool
    theseus_verify: bool
    recovered: bool
    payload_summary: dict[str, Any]
    state: str  # PASS / FAIL
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "kind": self.kind,
            "digest_verified": self.digest_verified,
            "theseus_verify": self.theseus_verify,
            "recovered": self.recovered,
            "payload_summary": self.payload_summary,
            "state": self.state,
            "reason": self.reason,
        }


class CustodyError(RuntimeError):
    """Custody content failed verification — fail closed."""


class CustodyUnavailable(RuntimeError):
    """THESEUS cannot be exercised on this host."""


class TuringCustody:
    """Fail-closed adapter over ``aethel.theseus``.  No private store.

    ``durable=True`` alone gives in-process healing only.  ``durable_dir``
    binds custody to an on-disk THESEUS store so commits survive process
    exit; :meth:`reopen` then returns a fresh adapter re-attached to that
    store, which is what custody replay after restart exercises.
    """

    def __init__(
        self,
        theseus: Any = None,
        *,
        durable: bool = False,
        durable_dir: str | Path | None = None,
    ) -> None:
        if theseus is None:
            if not theseus_available():
                raise CustodyUnavailable(
                    "aethel.theseus is not importable; THESEUS custody is "
                    "UNAVAILABLE on this host (no private substitute permitted)"
                )
            from aethel.theseus import open_theseus

            theseus = open_theseus(durable=durable, durable_dir=durable_dir)
        self._theseus = theseus
        self._durable_dir = Path(durable_dir) if durable_dir is not None else None
        self._kinds: dict[str, str] = {}

    @property
    def durable_dir(self) -> Path | None:
        return self._durable_dir

    def reopen(self) -> "TuringCustody":
        """Return a fresh adapter re-attached to this custody's durable dir.

        The new instance holds no live records: the THESEUS index is
        re-parsed and every payload is re-admitted from the durable block
        store through the digest-verified heal path.  Only meaningful when
        this custody was opened with ``durable_dir``.
        """
        if self._durable_dir is None:
            raise CustodyError(
                "reopen requires a durable_dir-bound custody; this adapter "
                "is in-process only"
            )
        return TuringCustody(durable_dir=self._durable_dir)

    # -- commit -------------------------------------------------------------

    def commit(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        meta: dict[str, Any] | None = None,
        durable: bool | None = None,
    ) -> CustodyReceipt:
        """Serialise to a canonical envelope and place it in THESEUS.

        ``durable`` defaults to the adapter's bound mode: a ``durable_dir``
        custody commits durably (the receipt's ``durable_index`` is then
        non-None and the record survives restart).
        """
        env_bytes = canonical_envelope_bytes(kind, payload, meta)
        record = self._theseus.put(
            env_bytes,
            durable=self._durable_dir is not None if durable is None else durable,
        )
        self._kinds[record.uuid] = kind
        return CustodyReceipt(
            uid=record.uuid,
            kind=kind,
            digest=record.digest,
            raw_len=record.raw_len,
            folded_units=record.folded_units,
            durable_index=record.durable_index,
            state="PASS",
        )

    # -- recover / verify / replay -----------------------------------------

    def recover(self, uid: str) -> dict[str, Any]:
        """Retrieve and digest-verify an envelope; returns its payload dict."""
        data = self._theseus.get(uid)  # Theseus heals + digest-checks internally
        envelope_digest(data)  # TURING-side re-verification of the envelope
        env = json.loads(data.decode("utf-8"))
        return env

    def verify(self, uid: str) -> bool:
        """Integrity check: THESEUS store verify + per-uid recovery probe.

        ``Theseus.verify()`` is whole-store (it re-reads and digest-checks
        every record, healing via replica/durable where needed); the uid is
        additionally re-verified by a full envelope recovery so the check is
        specific, not just store-level.
        """
        try:
            store_ok = bool(self._theseus.verify())
        except Exception:
            store_ok = False
        try:
            self.recover(uid)
        except Exception:
            return False
        return store_ok

    def replay(self, uid: str) -> ReplayReport:
        """Demonstrate recovery + replay for a custody artefact.

        Replays the *custody record*: recover bytes, verify the envelope
        digest, and validate the payload's structural expectations for its
        kind (a program must re-parse; a witness must carry its schema).
        """
        try:
            env = self.recover(uid)
        except Exception as exc:
            return ReplayReport(
                uid=uid,
                kind="unknown",
                digest_verified=False,
                theseus_verify=self.verify(uid),
                recovered=False,
                payload_summary={},
                state="FAIL",
                reason=f"recovery failed: {exc}",
            )
        kind = env["kind"]
        payload = env["payload"]
        structural_ok, summary = _validate_payload(kind, payload)
        verified = self.verify(uid)
        ok = structural_ok and verified
        return ReplayReport(
            uid=uid,
            kind=kind,
            digest_verified=True,
            theseus_verify=verified,
            recovered=True,
            payload_summary=summary,
            state="PASS" if ok else "FAIL",
            reason="custody replay: envelope intact, payload revalidated"
            if ok
            else "custody replay: integrity ok but payload validation failed",
        )

    def corrupt_for_test(self, uid: str) -> None:
        """Deliberately corrupt primary storage (test hook; delegates to
        THESEUS's own corruption hook — heals via replica/durable on get)."""
        self._theseus.corrupt_for_test(uid)


def _validate_payload(kind: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Structural re-validation of a recovered payload — replay means the
    artefact is still *usable*, not merely that bytes matched."""
    try:
        if kind == "program":
            from .backends.base import Program

            program = Program.from_dict(payload)
            return True, {
                "n_qubits": program.n_qubits,
                "operations": len(program.operations),
                "digest": program.digest(),
            }
        if kind == "witness":
            from .certificates import RunWitness, verify_witness

            witness = RunWitness.from_dict(payload)
            verify_witness(witness)
            return True, {
                "schema": witness.schema,
                "backend": witness.backend,
                "program_digest": witness.program_digest,
            }
        if kind == "certificate":
            from .certificates import VQCComputationCertificate

            certificate = VQCComputationCertificate.from_dict(payload)
            certificate.verify_integrity()
            return True, {
                "schema": certificate.schema,
                "backend": certificate.backend,
                "certificate_digest": certificate.certificate_digest,
            }
        if kind == "checkpoint":
            ok = "program_digest" in payload
            return ok, {"program_digest": payload.get("program_digest")}
        return True, {"keys": sorted(payload)[:8]}
    except Exception as exc:  # pragma: no cover - defensive
        return False, {"error": str(exc)}


def open_custody(
    *,
    durable: bool = False,
    durable_dir: str | Path | None = None,
) -> TuringCustody:
    """Open the THESEUS consumption adapter; UNAVAILABLE -> fail closed.

    ``durable_dir`` selects the on-disk THESEUS store — the only mode in
    which a custody receipt outlives the committing process.
    """
    return TuringCustody(durable=durable, durable_dir=durable_dir)
