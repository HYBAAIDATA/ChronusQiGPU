"""Theseus — self-healing prime-manifold storage owner.

Theseus is the ship that remains itself under replacement of parts:
digest-pinned custody, Galois prime keys, Cassini/pv-lattice anchors,
sunflower phyllotaxis packing, and one-shot heal from a redundant replica.

Retrieval is **not** Theseus's job — geodesic search is handed off via
``GeodesicHandoff``. Theseus stores and heals; the engine navigates.

Production database surface for the Chronus · Theseus · Ovid triad.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid as uuid_lib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .cassini import CassiniVerifier
from .errors import AethelError
from .fibonacci import fibonacci
from .geodesic import GeodesicHandoff, ManifoldPoint
from .manifold import ManifoldCurvature, ManifoldSector
from .ovid import FoldedWorkingForm, Ovid, open_ovid
from .phyllotaxis import (
    PhyllotaxisSite,
    pack_from_anchor,
    sector_lane,
    verify_golden_angle_constant,
)
from .primes import GaloisPrimeSubstrate
from .storage import AddressSpace, FibonacciAddress, JOURNAL_NAME


OWNER_ID = "theseus"
CLAIM_BOUNDARY = (
    "Theseus is HYBA's self-healing prime-manifold storage owner. "
    "It commits folded working forms under Galois prime keys and Cassini "
    "anchors with sunflower phyllotaxis packing. It does not provide "
    "infinite capacity, zero-footprint media elimination, hash preimages, "
    "or geodesic search (search is GeodesicHandoff → engine only)."
)

_ANCHOR_MODULUS = 90


class TheseusError(AethelError):
    """Theseus-tier failure — custody, heal, or commit refused."""


@dataclass(frozen=True)
class TheseusRecord:
    """One committed custody record."""

    uuid: str
    prime_key: int
    anchor: int
    digest: str
    phyllotaxis: PhyllotaxisSite
    lane: int
    raw_len: int
    folded_units: int
    curvature: str
    durable_index: Optional[int] = None


@dataclass
class Theseus:
    """Production self-healing storage owner.

    ``durable`` alone is an in-memory :class:`AddressSpace` — it heals
    corruption inside one process but survives no restart.  ``durable_dir``
    is the cross-process contract: the durable space and the record index are
    published under that directory on every durable commit, and
    :meth:`attach` rebuilds the owner from it in a fresh process.
    """

    ovid: Ovid = field(default_factory=open_ovid)
    primes: GaloisPrimeSubstrate = field(default_factory=GaloisPrimeSubstrate)
    durable: Optional[AddressSpace] = None
    durable_dir: Optional[Path] = None
    handoff: Optional[GeodesicHandoff] = None
    require_phyllotaxis: bool = True
    owner_id: str = OWNER_ID
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _records: Dict[str, TheseusRecord] = field(default_factory=dict)
    _by_digest: Dict[str, str] = field(default_factory=dict)
    _payloads: Dict[str, bytes] = field(default_factory=dict)
    _replicas: Dict[str, bytes] = field(default_factory=dict)
    _forms: Dict[str, FoldedWorkingForm] = field(default_factory=dict)
    _metrics: Dict[str, int] = field(
        default_factory=lambda: {
            "put_ok": 0,
            "put_reject": 0,
            "get_ok": 0,
            "get_miss": 0,
            "heal_ok": 0,
            "heal_fail": 0,
        }
    )

    def __post_init__(self) -> None:
        if self.require_phyllotaxis and not verify_golden_angle_constant():
            raise TheseusError(
                "golden-angle constant failed first-principles check"
            )

    @property
    def claim_boundary(self) -> str:
        return CLAIM_BOUNDARY

    def put(
        self,
        payload: Union[bytes, bytearray, FoldedWorkingForm],
        *,
        curvature: ManifoldCurvature = ManifoldCurvature.GOLDEN_DENSE,
        sector: ManifoldSector = ManifoldSector.P_VS_NP,
        durable: bool = False,
    ) -> TheseusRecord:
        """Commit: Ovid fold → prime key → phyllotaxis → Theseus custody.

        ``sector`` is accepted for API symmetry with the manifold; lane routing
        uses sunflower phyllotaxis, not the manifold sector enum.
        """
        del sector  # lane comes from phyllotaxis packing
        with self._lock:
            try:
                if isinstance(payload, FoldedWorkingForm):
                    form = payload
                    if not form.verify():
                        raise TheseusError("FoldedWorkingForm failed verify")
                    data = self.ovid.materialise(form)
                elif isinstance(payload, (bytes, bytearray)):
                    data = bytes(payload)
                    form = self.ovid.metamorphose(data)
                else:
                    raise TypeError(
                        "Theseus.put requires bytes or FoldedWorkingForm"
                    )
            except TheseusError:
                self._metrics["put_reject"] += 1
                raise
            except Exception as exc:
                self._metrics["put_reject"] += 1
                raise TheseusError(f"fold refused: {exc}") from exc

            # Deterministic anchor in the 90-slot manifold domain from content
            digest_int = int(form.digest[:16], 16)
            anchor = digest_int % _ANCHOR_MODULUS
            if not CassiniVerifier.verify(anchor):
                # Identity must hold for every n; failure is a math bug
                self._metrics["put_reject"] += 1
                raise TheseusError(f"Cassini identity failed at n={anchor}")

            uid = str(uuid_lib.uuid4())
            try:
                prime_key = int(self.primes.commit(anchor, uid, data))
            except Exception as exc:
                self._metrics["put_reject"] += 1
                raise TheseusError(f"prime commit refused: {exc}") from exc

            site = pack_from_anchor(anchor)
            lane = sector_lane(site)

            durable_index: Optional[int] = None
            if durable or self.durable is not None:
                space = self.durable
                if space is None:
                    space = AddressSpace()
                    self.durable = space
                try:
                    addr = space.write(data)
                    durable_index = addr.index
                    if not space.verify():
                        self._metrics["put_reject"] += 1
                        raise TheseusError(
                            "durable AddressSpace failed Cassini verify"
                        )
                except TheseusError:
                    raise
                except Exception as exc:
                    self._metrics["put_reject"] += 1
                    raise TheseusError(f"durable write refused: {exc}") from exc
                if self.handoff is None:
                    self.handoff = GeodesicHandoff(space)

            # Primary + replica parts of the ship
            self._payloads[uid] = data
            self._replicas[uid] = bytes(data)
            self._forms[uid] = form

            curv_name = (
                curvature.value if hasattr(curvature, "value") else str(curvature)
            )
            record = TheseusRecord(
                uuid=uid,
                prime_key=prime_key,
                anchor=anchor,
                digest=form.digest,
                phyllotaxis=site,
                lane=lane,
                raw_len=form.raw_len,
                folded_units=form.folded_units,
                curvature=curv_name,
                durable_index=durable_index,
            )
            self._records[uid] = record
            self._by_digest[form.digest] = uid
            if self.durable_dir is not None and durable_index is not None:
                # A durable commit is only durable if it survives this
                # process: publish the block store and record index before
                # the receipt is issued.
                self._persist_locked()
            self._metrics["put_ok"] += 1
            return record

    def get(self, uid: str) -> bytes:
        """Read payload; heal once on digest failure; fail-closed thereafter."""
        with self._lock:
            record = self._records.get(uid)
            if record is None:
                self._metrics["get_miss"] += 1
                raise TheseusError(f"unknown uuid: {uid}")

            data = self._payloads.get(uid)
            if data is not None and hashlib.sha256(data).hexdigest() == record.digest:
                self._metrics["get_ok"] += 1
                return bytes(data)

            healed = self._heal(uid, record)
            if healed is None:
                self._metrics["get_miss"] += 1
                raise TheseusError(
                    f"digest mismatch or missing payload; heal failed for {uid}"
                )
            self._metrics["get_ok"] += 1
            return healed

    def _heal(self, uid: str, record: TheseusRecord) -> Optional[bytes]:
        # 1) Replica part of the ship
        replica = self._replicas.get(uid)
        if (
            replica is not None
            and hashlib.sha256(replica).hexdigest() == record.digest
        ):
            self._payloads[uid] = replica
            self._metrics["heal_ok"] += 1
            return bytes(replica)

        # 2) Durable AddressSpace
        if record.durable_index is not None and self.durable is not None:
            try:
                addr = FibonacciAddress(
                    record.durable_index, fibonacci(record.durable_index)
                )
                data = self.durable.read(addr)
                if hashlib.sha256(data).hexdigest() == record.digest:
                    self._payloads[uid] = data
                    self._replicas[uid] = bytes(data)
                    self._metrics["heal_ok"] += 1
                    return bytes(data)
            except Exception:
                pass

        # 3) Prime substrate reconstruct (best-effort)
        try:
            fetched = None
            if hasattr(self.primes, "retrieve"):
                fetched = self.primes.retrieve(uid)
            elif hasattr(self.primes, "fetch"):
                fetched = self.primes.fetch(uid)
            if (
                isinstance(fetched, (bytes, bytearray))
                and hashlib.sha256(fetched).hexdigest() == record.digest
            ):
                self._payloads[uid] = bytes(fetched)
                self._replicas[uid] = bytes(fetched)
                self._metrics["heal_ok"] += 1
                return bytes(fetched)
        except Exception:
            pass

        self._metrics["heal_fail"] += 1
        return None

    def corrupt_for_test(self, uid: str, junk: bytes = b"\x00CORRUPT") -> None:
        """Test-only: damage primary copy to exercise heal."""
        with self._lock:
            if uid not in self._records:
                raise TheseusError(f"unknown uuid: {uid}")
            self._payloads[uid] = junk

    def get_working_form(self, uid: str) -> FoldedWorkingForm:
        with self._lock:
            form = self._forms.get(uid)
            if form is not None and form.verify():
                return form
        return self.ovid.metamorphose(self.get(uid))

    def lookup_digest(self, digest: str) -> Optional[TheseusRecord]:
        uid = self._by_digest.get(digest)
        return self._records.get(uid) if uid else None

    def record(self, uid: str) -> TheseusRecord:
        with self._lock:
            if uid not in self._records:
                raise TheseusError(f"unknown uuid: {uid}")
            return self._records[uid]

    def verify(self) -> bool:
        with self._lock:
            if self.durable is not None and not self.durable.verify():
                return False
            for uid, rec in list(self._records.items()):
                try:
                    data = self.get(uid)
                except TheseusError:
                    return False
                if hashlib.sha256(data).hexdigest() != rec.digest:
                    return False
            return True

    def geodesic(self) -> GeodesicHandoff:
        if self.handoff is not None:
            return self.handoff
        if self.durable is None:
            self.durable = AddressSpace()
        self.handoff = GeodesicHandoff(self.durable)
        return self.handoff

    def to_manifold_point(self, uid: str) -> ManifoldPoint:
        rec = self.record(uid)
        handoff = self.geodesic()
        if rec.durable_index is None:
            data = self.get(uid)
            assert self.durable is not None
            addr = self.durable.write(data)
            self._records[uid] = TheseusRecord(
                uuid=rec.uuid,
                prime_key=rec.prime_key,
                anchor=rec.anchor,
                digest=rec.digest,
                phyllotaxis=rec.phyllotaxis,
                lane=rec.lane,
                raw_len=rec.raw_len,
                folded_units=rec.folded_units,
                curvature=rec.curvature,
                durable_index=addr.index,
            )
            rec = self._records[uid]
        addr = FibonacciAddress(rec.durable_index, fibonacci(rec.durable_index))
        return handoff.to_manifold(addr)

    def metrics(self) -> Dict[str, Any]:
        return {
            "owner": self.owner_id,
            "records": len(self._records),
            "counters": dict(self._metrics),
            "ovid": self.ovid.metrics(),
            "primes": self.primes.stats(),
        }

    def health(self) -> Dict[str, Any]:
        phy_ok = verify_golden_angle_constant()
        return {
            "owner": self.owner_id,
            "status": "ok" if phy_ok else "degraded",
            "records": len(self._records),
            "phyllotaxis_constant_ok": phy_ok,
            "durable": self.durable is not None,
            "metrics": self.metrics(),
            "claim_boundary": CLAIM_BOUNDARY,
            "production_surface": True,
        }

    def _record_index(self) -> Dict[str, Any]:
        return {
            "owner": self.owner_id,
            "records": {
                u: {
                    "uuid": r.uuid,
                    "prime_key": r.prime_key,
                    "anchor": r.anchor,
                    "digest": r.digest,
                    "lane": r.lane,
                    "raw_len": r.raw_len,
                    "folded_units": r.folded_units,
                    "curvature": r.curvature,
                    "durable_index": r.durable_index,
                    "phyllotaxis": {
                        "index": r.phyllotaxis.index,
                        "radius": r.phyllotaxis.radius,
                        "theta": r.phyllotaxis.theta,
                        "x": r.phyllotaxis.x,
                        "y": r.phyllotaxis.y,
                        "ring": r.phyllotaxis.ring,
                        "sector": r.phyllotaxis.sector,
                    },
                }
                for u, r in self._records.items()
            },
        }

    def _write_index(self, directory: Path) -> None:
        path = directory / "theseus_index.json"
        tmp = directory / "theseus_index.json.tmp"
        tmp.write_text(
            json.dumps(self._record_index(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def _persist_locked(self) -> None:
        """Publish durable blocks + record index under ``durable_dir``.

        Caller must hold ``self._lock`` (re-entrant); called automatically
        after every durable commit on a directory-bound owner.
        """
        assert self.durable_dir is not None
        directory = Path(self.durable_dir)
        directory.mkdir(parents=True, exist_ok=True)
        if self.durable is not None:
            self.durable.snapshot(directory / "durable")
        self._write_index(directory)

    def snapshot(self, directory: str | Path) -> Dict[str, Any]:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self.durable is not None:
                self.durable.snapshot(directory / "durable")
            self._write_index(directory)
            return {"path": str(directory), "records": len(self._records)}

    @classmethod
    def attach(cls, directory: str | Path, **kwargs: Any) -> "Theseus":
        """Rebuild a Theseus owner from a ``durable_dir``/``snapshot`` tree.

        The durable :class:`AddressSpace` journal and every block are
        re-verified by :meth:`AddressSpace.attach`; the record index is
        re-parsed; then every record is re-admitted through the normal
        digest-verified heal path so a torn or forged store fails closed at
        attach rather than on first read.
        """
        directory = Path(directory)
        index_path = directory / "theseus_index.json"
        if not index_path.is_file():
            raise TheseusError(f"no THESEUS record index at {index_path}")
        durable = AddressSpace.attach(directory / "durable")
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TheseusError(f"unreadable THESEUS record index: {exc}") from exc
        if index.get("owner") != OWNER_ID:
            raise TheseusError(
                f"unexpected THESEUS index owner {index.get('owner')!r}"
            )
        raw_records = index.get("records")
        if not isinstance(raw_records, dict):
            raise TheseusError("THESEUS index has no record table")

        theseus = cls(durable=durable, durable_dir=directory, **kwargs)
        theseus.handoff = GeodesicHandoff(durable)
        for uid, entry in raw_records.items():
            try:
                site = entry["phyllotaxis"]
                record = TheseusRecord(
                    uuid=str(entry["uuid"]),
                    prime_key=int(entry["prime_key"]),
                    anchor=int(entry["anchor"]),
                    digest=str(entry["digest"]),
                    phyllotaxis=PhyllotaxisSite(
                        index=int(site["index"]),
                        radius=float(site["radius"]),
                        theta=float(site["theta"]),
                        x=float(site["x"]),
                        y=float(site["y"]),
                        ring=int(site["ring"]),
                        sector=int(site["sector"]),
                    ),
                    lane=int(entry["lane"]),
                    raw_len=int(entry["raw_len"]),
                    folded_units=int(entry["folded_units"]),
                    curvature=str(entry["curvature"]),
                    durable_index=entry["durable_index"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise TheseusError(
                    f"corrupt THESEUS index entry {uid!r}: {exc}"
                ) from exc
            if record.uuid != uid or not isinstance(record.durable_index, int):
                raise TheseusError(
                    f"THESEUS index entry {uid!r} is inconsistent or "
                    "not durable"
                )
            theseus._records[uid] = record
            theseus._by_digest[record.digest] = uid

        # Prove re-admission for every restored record now: an index row
        # whose block is missing or digests wrong is a corrupt store, not a
        # store that happens to look empty.
        for uid in list(theseus._records):
            try:
                theseus.get(uid)
            except TheseusError as exc:
                raise TheseusError(
                    f"attached THESEUS store cannot re-admit record {uid}: {exc}"
                ) from exc
        return theseus


def open_theseus(
    *,
    durable: bool = False,
    durable_dir: str | Path | None = None,
    ovid: Optional[Ovid] = None,
) -> Theseus:
    """Factory — production Theseus owner.

    ``durable`` alone is in-process healing only.  ``durable_dir`` binds a
    real on-disk store: an existing tree (``theseus_index.json`` or a
    durable journal) is attached, a fresh one is created on first durable
    commit, and every durable commit is published before its receipt is
    issued — custody survives process exit.
    """
    kwargs: Dict[str, Any] = {}
    if ovid is not None:
        kwargs["ovid"] = ovid
    if durable_dir is not None:
        directory = Path(durable_dir)
        if (directory / "theseus_index.json").is_file():
            return Theseus.attach(directory, **kwargs)
        journal = directory / "durable" / JOURNAL_NAME
        if journal.is_file():
            # Orphaned block store without a record index: keep the verified
            # sequence (writer cursors, ledger) rather than overwriting it.
            theseus = Theseus(
                durable=AddressSpace.attach(directory / "durable"),
                durable_dir=directory,
                **kwargs,
            )
            theseus.handoff = GeodesicHandoff(theseus.durable)
            return theseus
        return Theseus(
            durable=AddressSpace(), durable_dir=directory, **kwargs
        )
    if durable:
        kwargs["durable"] = AddressSpace()
    return Theseus(**kwargs)


__all__ = [
    "OWNER_ID",
    "CLAIM_BOUNDARY",
    "TheseusError",
    "TheseusRecord",
    "Theseus",
    "open_theseus",
]
