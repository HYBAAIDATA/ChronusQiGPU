"""Recovery reporting and deterministic replay for enterprise custody.

Two jobs:

1. ``RecoveryReport`` — the handoff surface after ``recover()``. THESEUS
   restores *bytes and integrity*; the producing subsystem owns *meaning*.
   The report therefore groups recovered records by producer and lists them
   as pending semantic revalidation until each producer calls back.

2. Deterministic replay — the sealed WAL op stream folds into one expected
   state map; folding is pure, so two folds are byte-identical and any
   divergence between folded expectation and the verified store is reported
   exactly. ``replay_into`` re-executes the sealed op stream into a second
   custody instance and verifies the reconstructed digests match.

Operational records are replayed as operational records: producer identity,
schema, evidence state, lineage, correlations and dependency manifests are
re-admitted through ``put_record`` and therefore pass the same producer and
dependency contracts as the original durable write. Plain byte records remain
plain byte records. No replay path silently strips producer meaning.

This module never imports custody — custody objects are passed in and used
via their public surface only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional


@dataclass
class RecoveryReport:
    """Result of one custody recovery scan.

    ``pending_revalidation`` maps producer -> record ids whose bytes and
    integrity were restored but whose semantics the producer must revalidate.
    THESEUS never clears that list itself; producers retire entries via the
    custody ``semantic_revalidated`` hook.
    """

    records_verified: int = 0
    records_unrecoverable: dict[str, str] = field(default_factory=dict)
    pending_revalidation: dict[str, list[str]] = field(default_factory=dict)
    journal_sealed_ops: int = 0
    dangling_intents_dropped: int = 0
    revalidated: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "records_verified": self.records_verified,
            "records_unrecoverable": dict(self.records_unrecoverable),
            "pending_revalidation": {
                k: list(v) for k, v in sorted(self.pending_revalidation.items())
            },
            "journal_sealed_ops": self.journal_sealed_ops,
            "dangling_intents_dropped": self.dangling_intents_dropped,
            "revalidated": list(self.revalidated),
        }


def build_recovery_report(
    scan: Iterable[tuple[str, Optional[Mapping[str, Any]], Optional[str]]],
    *,
    journal_rows: Iterable[Mapping[str, Any]],
) -> RecoveryReport:
    """Fold a recovery scan into a report.

    ``scan`` yields ``(record_id, meta_or_None, error_class_or_None)``:
    meta None + error None = nothing on disk; error set = unrecoverable;
    meta set = verified. Producer grouping reads ``meta["op_record"]["producer"]``
    when the record carries an operational manifest, else ``"unknown"``.
    """
    report = RecoveryReport()
    sealed: set[str] = set()
    intents: set[str] = set()
    for row in journal_rows:
        op_id = str(row.get("op_id", ""))
        if not op_id:
            continue
        if row.get("status") == "sealed":
            sealed.add(op_id)
        elif row.get("status") == "intent":
            intents.add(op_id)
    report.journal_sealed_ops = len(sealed)
    report.dangling_intents_dropped = len(intents - sealed)

    for record_id, meta, error in scan:
        if error is not None:
            report.records_unrecoverable[record_id] = error
            continue
        if meta is None:
            continue
        report.records_verified += 1
        producer = "unknown"
        op = meta.get("op_record") if isinstance(meta, Mapping) else None
        if isinstance(op, Mapping) and op.get("producer"):
            producer = str(op["producer"])
        report.pending_revalidation.setdefault(producer, []).append(record_id)
    for ids in report.pending_revalidation.values():
        ids.sort()
    return report


def fold_journal_ops(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Deterministically fold sealed WAL rows into expected store state.

    A journal entry is intent + seal sharing one ``op_id``; the intent carries
    the op shape (op/record_id/generation/content_digest), the seal confirms
    it. Dangling intents (no seal) are excluded — the WAL already drops them.
    Later sealed ops supersede earlier ones for the same record; a sealed
    delete removes the record from expected state. Pure: identical input
    yields identical output.
    """
    intents: dict[str, Mapping[str, Any]] = {}
    materialized: list[Mapping[str, Any]] = []
    for row in rows:
        op_id = str(row.get("op_id", ""))
        status = row.get("status")
        if status == "intent" and op_id:
            intents[op_id] = row
        elif status == "sealed" and op_id:
            materialized.append(row)
    expected: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for seal in materialized:
        op_id = str(seal.get("op_id", ""))
        merged = dict(intents.get(op_id, {}))
        merged.update(seal)
        rid = str(merged.get("record_id", ""))
        if not rid:
            continue
        op = str(merged.get("op", ""))
        if op == "put":
            if rid not in expected:
                order.append(rid)
            expected[rid] = {
                "record_id": rid,
                "generation": int(merged.get("generation", 0)),
                "content_digest": str(merged.get("content_digest", "")),
                "present": True,
            }
        elif op == "delete" and rid in expected:
            expected[rid]["present"] = False
    return {rid: expected[rid] for rid in order}


def verify_replay(
    expected: Mapping[str, Mapping[str, Any]],
    actual: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Diff folded journal expectation vs verified store records."""
    actual_map = {str(r["record_id"]): r for r in actual}
    divergences: list[dict[str, Any]] = []
    for rid, exp in expected.items():
        act = actual_map.get(rid)
        if not exp.get("present", True):
            if act is not None:
                divergences.append(
                    {"record_id": rid, "kind": "expected_deleted_present"}
                )
            continue
        if act is None:
            divergences.append({"record_id": rid, "kind": "missing"})
            continue
        if int(act.get("generation", 0)) != int(exp.get("generation", 0)):
            divergences.append(
                {
                    "record_id": rid,
                    "kind": "generation",
                    "expected": exp.get("generation"),
                    "actual": act.get("generation"),
                }
            )
        if str(act.get("content_digest", "")) != str(exp.get("content_digest", "")):
            divergences.append(
                {
                    "record_id": rid,
                    "kind": "digest",
                    "expected": exp.get("content_digest"),
                    "actual": act.get("content_digest"),
                }
            )
    for rid in sorted(set(actual_map) - set(expected)):
        divergences.append({"record_id": rid, "kind": "unexpected_present"})
    return {
        "deterministic": True,
        "expected_records": sum(
            1 for e in expected.values() if e.get("present", True)
        ),
        "actual_records": len(actual_map),
        "divergences": divergences,
        "match": not divergences,
    }


def _replay_put(source: Any, dest: Any, record_id: str) -> str:
    """Replay one present record without discarding operational semantics.

    ``get_record`` is the authoritative public surface for records carrying a
    producer manifest. If the record is a plain custody byte object,
    ``get_record`` raises ``KeyError`` and replay falls back to ``get``/``put``.
    Contract failures from ``put_record`` are deliberately not swallowed: a
    destination that cannot admit the producer/dependency contract must fail
    replay rather than silently demote the record to anonymous bytes.
    """
    try:
        record = source.get_record(record_id)
    except KeyError:
        data = source.get(record_id)
        dest.put(data, record_id=record_id)
        return "bytes"
    dest.put_record(record)
    return "operational_record"


def replay_into(source: Any, dest: Any) -> dict[str, Any]:
    """Re-execute the sealed op stream from ``source`` into ``dest`` custody.

    Replay order is journal order. Operational records are re-admitted through
    ``dest.put_record`` so producer, evidence, lineage, correlation and
    dependency manifests survive disaster-recovery replay and are validated
    again. Plain custody objects use ``dest.put``. Final content digests are
    compared against the verified source inventory.
    """
    intents: dict[str, Mapping[str, Any]] = {}
    ops: list[dict[str, Any]] = []
    for row in source.journal.iter_rows():
        op_id = str(row.get("op_id", ""))
        if row.get("status") == "intent" and op_id:
            intents[op_id] = row
        elif row.get("status") == "sealed" and op_id:
            merged = dict(intents.get(op_id, {}))
            merged.update(row)
            if merged.get("op") in {"put", "delete"}:
                ops.append(merged)

    applied = 0
    skipped_missing = 0
    operational_records = 0
    byte_records = 0
    for row in ops:
        rid = str(row.get("record_id", ""))
        if not rid:
            continue
        if row["op"] == "put":
            try:
                replay_kind = _replay_put(source, dest, rid)
            except KeyError:
                skipped_missing += 1
                continue
            if replay_kind == "operational_record":
                operational_records += 1
            else:
                byte_records += 1
            applied += 1
        else:
            try:
                dest.delete(rid)
            except Exception:
                skipped_missing += 1
                continue
            applied += 1

    src_records = {r["record_id"]: r for r in source.list_records()}
    dst_records = {r["record_id"]: r for r in dest.list_records()}
    mismatched = sorted(
        rid
        for rid, rec in src_records.items()
        if rid not in dst_records
        or dst_records[rid].get("content_digest") != rec.get("content_digest")
        or dst_records[rid].get("producer") != rec.get("producer")
        or dst_records[rid].get("kind") != rec.get("kind")
        or dst_records[rid].get("evidence_state") != rec.get("evidence_state")
    )
    return {
        "ops_replayed": applied,
        "ops_skipped_missing": skipped_missing,
        "operational_records_replayed": operational_records,
        "byte_records_replayed": byte_records,
        "source_records": len(src_records),
        "dest_records": len(dst_records),
        "digest_mismatches": mismatched,
        "deterministic": True,
        "match": not mismatched,
    }


__all__ = [
    "RecoveryReport",
    "build_recovery_report",
    "fold_journal_ops",
    "verify_replay",
    "replay_into",
]
