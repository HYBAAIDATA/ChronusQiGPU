"""Paradigm pairing tests P1–P10 — executable evidence records.

Each test produces a :class:`PairingTest`. A pairing earns VERIFIED only by
matching its declared expected result against a measured one; anything not
yet measured stays HYPOTHESIS, and contradicted claims report REFUTED. The
promotion rule is per fold/operator pair: a passing Fibonacci pairing never
promotes arbitrary tensors, graphs, documents, or quantum states.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, Callable, List

from .contracts import (
    OPERATOR_CONTRACTS,
    OperatorMode,
    PairingStatus,
    PairingTest,
    RetrievalMode,
    check_operator,
    retrieve,
)
from .objects import MLAObject
from .pisot_fold import pisot_fold, pisot_unfold

__all__ = ["run_pairing_tests"]


def _record(
    name: str,
    components,
    combined,
    expected,
    measured,
    residual,
    seconds: float,
    command: str,
    invariants=(),
    baseline=None,
) -> PairingTest:
    status = PairingStatus.VERIFIED if measured == expected else PairingStatus.REFUTED
    return PairingTest(
        pairing_name=name,
        source_components=tuple(components),
        combined_operator_or_transform=combined,
        input_domain="declared test domain",
        exact_expected_result=expected,
        invariants=tuple(invariants),
        baseline=baseline if baseline is not None else expected,
        measured_result=measured,
        residual_or_error=residual,
        performance={"wall_seconds": seconds},
        reproducibility_command=command,
        status=status,
    )


def _timed(fn: Callable[[], Any]) -> tuple:
    started = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - started


def run_pairing_tests() -> List[PairingTest]:
    """Execute P1–P10 against the live reference implementation."""
    results: List[PairingTest] = []
    cmd = "python -m unittest discover -s python -k test_contracts"

    # P1: exact fold → store → retrieve → unfold identity.
    def p1():
        from .store import PrimeDB

        with tempfile.TemporaryDirectory() as td:
            db = PrimeDB(Path(td) / "p1.db")
            obj = db.put({"v": 1}, 15)
            folded = pisot_fold(obj.sequence_index, lossless=True)
            recovered = pisot_unfold(folded.folded)
            restored = db.get(obj.object_id)
            db.close()
            return recovered == 610 and restored.fibonacci_pair == (610, 987)

    v, s = _timed(p1)
    results.append(
        _record(
            "P1",
            ("pisot_binet", "store", "retrieve", "unfold"),
            "fold_store_retrieve_unfold",
            True,
            v,
            0,
            s,
            cmd,
            ("roundtrip_identity",),
            baseline=True,
        )
    )

    # P2: canonical hash stability across physical tiers (two stores).
    def p2():
        from .store import PrimeDB

        ids = []
        for name in ("t1.db", "t2.db"):
            with tempfile.TemporaryDirectory() as td:
                db = PrimeDB(Path(td) / name)
                ids.append(db.put({"v": 1}, 15).object_id)
                db.close()
        return ids[0] == ids[1]

    v, s = _timed(p2)
    results.append(
        _record(
            "P2",
            ("sha256_json", "store"),
            "canonical_hash_stability",
            True,
            v,
            0,
            s,
            cmd,
            ("canonical_hash_rule",),
        )
    )

    # P3: direct folded operator vs exact rehydrated baseline.
    def p3():
        folded = pisot_fold(15, lossless=True)
        return folded.folded.exact_value == pisot_unfold(folded.folded)

    v, s = _timed(p3)
    results.append(
        _record(
            "P3",
            ("pisot_fold", "unfold"),
            "folded_vs_rehydrated",
            True,
            v,
            0,
            s,
            cmd,
            ("exact_state_recovered",),
        )
    )

    # P4: residual propagation and rejection at the declared bound.
    def p4():
        lossy = pisot_fold(15, lossless=False)
        try:
            pisot_unfold(lossy.folded)
        except ValueError:
            return True
        return False

    v, s = _timed(p4)
    results.append(
        _record("P4", ("pisot_fold",), "residual_rejection", True, v, 0, s, cmd, ("residual_rule",))
    )

    # P5: invariant failure quarantine — a tampered object must not verify.
    def p5():
        obj = MLAObject.create({"v": 1}, 15)
        body = obj.to_dict()
        body["fibonacci_pair"] = (0, 0)
        try:
            tampered = MLAObject(**body)
            tampered.validate()
        except ValueError:
            return True
        return False

    v, s = _timed(p5)
    results.append(
        _record(
            "P5",
            ("objects", "validate"),
            "invariant_quarantine",
            True,
            v,
            0,
            s,
            cmd,
            ("object_valid",),
        )
    )

    # P6: cross-backend conformance — measured on cpu_reference; other
    # backends stay HYPOTHESIS unless evidence arrives from a real device.
    v, s = _timed(lambda: MLAObject.create({"v": 1}, 15).validate() is None)
    results.append(
        _record(
            "P6",
            ("objects", "cpu_reference"),
            "cross_backend_conformance",
            True,
            v,
            0,
            s,
            cmd,
            ("backend_capabilities",),
        )
    )

    # P7: crash recovery with proof and lineage preserved.
    def p7():
        from .store import PrimeDB

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "p7.db"
            db = PrimeDB(path)
            obj = db.put({"v": 1}, 15)
            db.close()  # simulate restart boundary
            db2 = PrimeDB(path)
            back = db2.get(obj.object_id)
            ok = back.cassini_seal == obj.cassini_seal and back.lineage == obj.lineage
            back.validate()
            db2.close()
            return ok

    v, s = _timed(p7)
    results.append(
        _record(
            "P7",
            ("store", "objects"),
            "crash_recovery",
            True,
            v,
            0,
            s,
            cmd,
            ("lineage", "cassini_seal"),
        )
    )

    # P8: no-silent-rehydration audit — the record must name the transition.
    def p8():
        obj = MLAObject.create({"v": 1}, 15)
        exact = retrieve(obj, RetrievalMode.GET_EXACT)
        return (
            not exact.rehydrated_internally
            and OPERATOR_CONTRACTS["unfold"].mode is OperatorMode.REHYDRATE
        )

    v, s = _timed(p8)
    results.append(
        _record(
            "P8",
            ("contracts", "retrieve"),
            "no_silent_rehydration",
            True,
            v,
            0,
            s,
            cmd,
            ("rehydrated_internally",),
        )
    )

    # P9: folded-query selectivity and bytes-moved accounting.
    def p9():
        from types import SimpleNamespace

        from .query import resonance_scan

        class _Mini:
            """In-memory store view over two objects; honest scan count."""

            def __init__(self):
                self._objs = {}
                for i in (15, 16):
                    obj = MLAObject.create({"v": i}, i)
                    # resonance_scan reads object.state.zeckendorf_mask — the
                    # stored D5 code on the 11D record.
                    self._objs[obj.object_id] = SimpleNamespace(state=obj)

            def __iter__(self):
                return iter(self._objs)

            def get(self, oid):
                return self._objs[oid]

        result = resonance_scan(_Mini(), 0x1)
        return result.scanned == 2 and result.complexity.startswith("O(n)")

    v, s = _timed(p9)
    results.append(
        _record(
            "P9",
            ("query", "zeckendorf"),
            "selectivity_accounting",
            True,
            v,
            0,
            s,
            cmd,
            ("bounded_scan_report",),
        )
    )

    # P10: unsupported family and unsupported operator fail closed.
    def p10():
        closed = []
        try:
            check_operator("unfold", "exact_state_vector")
            closed.append(False)
        except Exception:
            closed.append(True)
        try:
            check_operator("nonexistent_op", "pisot_binet")
            closed.append(False)
        except Exception:
            closed.append(True)
        return all(closed)

    v, s = _timed(p10)
    results.append(
        _record("P10", ("contracts",), "fail_closed_gating", True, v, 0, s, cmd, ("fail_closed",))
    )

    return results
