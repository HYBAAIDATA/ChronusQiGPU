"""Paradigm triad runner — lemma + systems + measurement (+ honesty).

Green spine = all legs pass. External physical/pool gates stay PENDING and
are listed explicitly (never silent).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from chronus.paradigm.bakeoff import bakeoff_self_check
from chronus.paradigm.conformance import run_conformance
from chronus.paradigm.honesty import run_honesty_chaos
from chronus.paradigm.thesis import THESIS, THESIS_ID, assert_thesis_bounds, thesis_text


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LegResult:
    name: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TriadReport:
    ok: bool
    thesis_id: str
    thesis: str
    legs: tuple[LegResult, ...]
    pending_external: tuple[str, ...]
    recorded_at: str
    claim_ids: tuple[str, ...]
    artifact_digest: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["legs"] = [x.as_dict() if hasattr(x, "as_dict") else x for x in self.legs]
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), indent=indent, sort_keys=True, default=str)


def _leg_lemma() -> LegResult:
    from hyba.operating_model.lemma import (
        LEMMA_GOLDEN_STRIDE,
        verify_golden_stride,
        use_ordering_lemma,
    )
    from chronus.paradigm.schedules import assert_golden_stride_constant, golden_stride_walk

    assert_golden_stride_constant()
    verdicts = verify_golden_stride()
    ok = all(v.get("verdict") == "HOLDS" for v in verdicts)
    # Scope guard: ordering use only
    meta = use_ordering_lemma("order_host_probe_walk")
    assert meta.get("theorem_proven") is False
    # Small uniqueness sweep (full 2^32 is infeasible; 50k is a cross-check)
    seq = list(golden_stride_walk(0xA5A5A5A5, 50_000))
    unique = len(seq) == len(set(seq))
    ok = ok and unique and LEMMA_GOLDEN_STRIDE.get("theorem_proven") is False
    return LegResult(
        name="lemma_golden_stride",
        ok=ok,
        detail={
            "verdicts": verdicts,
            "unique_50k": unique,
            "theorem_proven": False,
            "not_a_proof_of": list(LEMMA_GOLDEN_STRIDE.get("not_a_proof_of", ())),
            "claim_id": "c-paradigm-golden-stride",
        },
    )


def _leg_systems() -> LegResult:
    report = run_conformance()
    return LegResult(
        name="systems_vigpu_conformance",
        ok=report.ok,
        detail=report.as_dict(),
    )


def _leg_measurement() -> LegResult:
    out = bakeoff_self_check()
    return LegResult(
        name="measurement_schedule_bakeoff",
        ok=bool(out.get("ok")),
        detail=out,
    )


def _leg_honesty() -> LegResult:
    report = run_honesty_chaos()
    return LegResult(
        name="honesty_chaos",
        ok=report.ok,
        detail=report.as_dict(),
    )


def _leg_thesis() -> LegResult:
    rep = assert_thesis_bounds()
    return LegResult(name="thesis_bounds", ok=bool(rep.get("ok")), detail=rep)


def run_triad(*, include_honesty: bool = True) -> TriadReport:
    """Run the full paradigm spine. Returns a structured report."""
    legs = [
        _leg_thesis(),
        _leg_lemma(),
        _leg_systems(),
        _leg_measurement(),
    ]
    if include_honesty:
        legs.append(_leg_honesty())

    pending = (
        "live_opencl_device_measurement",
        "hardware_rooted_attestation_keys",
        "real_pool_ack_truth_class",
        "third_party_conformance_repro",
        "osdi_style_external_bakeoff",
    )
    ok = all(leg.ok for leg in legs)
    claim_ids = (
        THESIS_ID,
        "c-paradigm-golden-stride",
        "c-paradigm-vigpu-conformance",
        "c-paradigm-bakeoff",
        "c-paradigm-honesty-chaos",
    )
    report = TriadReport(
        ok=ok,
        thesis_id=THESIS_ID,
        thesis=thesis_text(),
        legs=tuple(legs),
        pending_external=pending,
        recorded_at=_utc_now(),
        claim_ids=claim_ids,
    )
    # Content digest of the report body (without digest field)
    body = report.as_dict()
    body.pop("artifact_digest", None)
    import hashlib

    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return TriadReport(
        ok=report.ok,
        thesis_id=report.thesis_id,
        thesis=report.thesis,
        legs=report.legs,
        pending_external=report.pending_external,
        recorded_at=report.recorded_at,
        claim_ids=report.claim_ids,
        artifact_digest=digest,
    )


def write_report(path: str | Path, report: TriadReport | None = None) -> Path:
    """Persist triad JSON under docs/evidence or a caller path."""
    rep = report or run_triad()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rep.to_json(), encoding="utf-8", newline="\n")
    return out


# Re-export thesis constants for CLI convenience
__all__ = ["TriadReport", "LegResult", "run_triad", "write_report", "THESIS", "THESIS_ID"]
