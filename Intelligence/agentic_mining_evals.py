"""Deterministic Crawl/Walk/Run evaluations for the agentic mining research workflow.

These evaluations grade local workflow evidence. They do not represent pool
acceptance, hardware production, or an online share-submission path.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from Intelligence._born import born_evidence
from Intelligence.agentic_mining import AgenticMiningWorkflow

GENESIS_HEADER = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49ffff001d1dac2b7c"
)
GENESIS_NONCE = 2083236893
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_HASH_INT = int(GENESIS_HASH, 16)


@dataclass(frozen=True)
class CrawlCase:
    case_id: str
    header_template: bytes
    nonce: int
    target: int
    expected_local_valid: bool
    tags: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "header_template_hex": self.header_template.hex(),
            "nonce": self.nonce,
            "target_hex": f"{self.target:064x}",
            "expected_local_valid": self.expected_local_valid,
            "tags": list(self.tags),
        }


CRAWL_CASES = (
    CrawlCase(
        "genesis-equality-accept",
        GENESIS_HEADER[:76],
        GENESIS_NONCE,
        GENESIS_HASH_INT,
        True,
        ("sha256d", "boundary", "positive", "grounded-header"),
    ),
    CrawlCase(
        "genesis-one-below-reject",
        GENESIS_HEADER[:76],
        GENESIS_NONCE,
        GENESIS_HASH_INT - 1,
        False,
        ("sha256d", "boundary", "negative", "grounded-header"),
    ),
    CrawlCase(
        "zero-target-reject",
        GENESIS_HEADER[:76],
        GENESIS_NONCE,
        0,
        False,
        ("sha256d", "negative", "minimum-target"),
    ),
    CrawlCase(
        "maximum-target-accept",
        GENESIS_HEADER[:76],
        GENESIS_NONCE,
        (1 << 256) - 1,
        True,
        ("sha256d", "positive", "maximum-target"),
    ),
)

WALK_CASES = (
    {
        "case_id": "warm-host-fixture",
        "telemetry": {"thermal_c": 54.0, "power_w": 140.0, "peer_count": 3},
        "tags": ("telemetry", "fixture", "single-cycle"),
    },
    {
        "case_id": "near-throttle-fixture",
        "telemetry": {"thermal_c": 82.0, "power_w": 295.0, "peer_count": 0},
        "tags": ("telemetry", "fixture", "near-throttle"),
    },
)


def _sha256d(header_template: bytes, nonce: int) -> bytes:
    header = header_template + nonce.to_bytes(4, "little")
    if len(header) != 80:
        raise ValueError("Bitcoin header fixture must encode to exactly 80 bytes")
    return hashlib.sha256(hashlib.sha256(header).digest()).digest()


def run_crawl_case(case: CrawlCase) -> dict[str, Any]:
    """Replay one fixed header/nonce/target and grade the exact local proof."""
    workflow = AgenticMiningWorkflow()
    workflow.phase1_cold_start()
    candidate = workflow.manifold_bridge.store_candidate(
        nonce=case.nonce,
        header_template=case.header_template,
        # Flat sector prior: the eval replays a cold workflow with no
        # measured sector outcomes yet (was invented 0.95).
        born_prob=born_evidence(0, 0),
        n_anchor=7,
    )
    workflow.current_target = case.target
    started = time.perf_counter()
    result = workflow.phase4_submit(target_nonce=case.nonce)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    digest = _sha256d(case.header_template, case.nonce)
    local_valid = int.from_bytes(digest, "little") <= case.target
    checks = {
        "header_grounding": candidate.header_template == case.header_template,
        "nonce_grounding": candidate.nonce == case.nonce,
        "digest_matches_sha256d": result.hash_hex == digest.hex(),
        "target_decision_matches_digest": result.accepted == local_valid,
        "target_decision_matches_case": result.accepted == case.expected_local_valid,
        "zeckendorf_certificate_valid": (
            candidate.zeckendorf_mask & (candidate.zeckendorf_mask << 1)
        )
        == 0,
        "provenance_chain_valid": workflow.toe.verify_provenance(),
    }
    return {
        "level": "crawl",
        "case": case.as_dict(),
        "observed": {
            "local_valid": result.accepted,
            "hash_hex": result.hash_hex,
            "provenance_hash": result.provenance_hash,
            "probe_count": result.probes_taken,
            "lookup_time_ms": result.lookup_time_ms,
            "wall_time_ms": elapsed_ms,
            "pool_accepted": None,
            "execution_scope": "local_sha256d_only",
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_crawl_suite(cases: Iterable[CrawlCase] = CRAWL_CASES) -> dict[str, Any]:
    results = [run_crawl_case(case) for case in cases]
    passed = sum(bool(result["passed"]) for result in results)
    return {
        "schema": "pythia.agentic-mining-eval/1",
        "level": "crawl",
        "cases": results,
        "passed": passed,
        "total": len(results),
        "pass_rate": passed / len(results) if results else 1.0,
    }


def run_walk_case(case: dict[str, Any]) -> dict[str, Any]:
    """Replay one synthetic telemetry episode and grade source/truth labels."""
    workflow = AgenticMiningWorkflow()
    workflow.phase1_cold_start()
    candidates = workflow.phase2_precompute(count=4, header_template=GENESIS_HEADER[:76])
    held = workflow.phase3_hold()
    workflow.current_target = 0
    local_result = workflow.phase4_submit()
    fixture = dict(case["telemetry"])
    ticks = workflow.phase5_steady_state(
        cycles=1,
        telemetry_provider=lambda _cycle: fixture,
        telemetry_source="fixture",
    )
    tick = ticks[0]
    checks = {
        "all_candidates_bound_to_fixture_header": all(
            candidate.header_template == GENESIS_HEADER[:76] for candidate in candidates
        ),
        "candidate_nonces_unique": len({candidate.nonce for candidate in candidates})
        == len(candidates),
        "hold_coverage_complete": held["total_held_candidates"] == len(candidates),
        "phase4_is_local_rejection": local_result.accepted is False,
        "fixture_not_claimed_as_measured": tick["truth_class"] == "simulated",
        "fixture_source_explicit": tick["telemetry_source"] == "fixture",
        "fixture_values_preserved": all(tick.get(key) == value for key, value in fixture.items()),
        "unprovided_thermal_not_fabricated": (
            "thermal_c" in fixture or tick.get("thermal_c") is None
        ),
    }
    return {
        "level": "walk",
        "case_id": case["case_id"],
        "tags": list(case["tags"]),
        "fixture": fixture,
        "observed": tick,
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_walk_suite(cases: Iterable[dict[str, Any]] = WALK_CASES) -> dict[str, Any]:
    results = [run_walk_case(case) for case in cases]
    passed = sum(bool(result["passed"]) for result in results)
    return {
        "schema": "pythia.agentic-mining-eval/1",
        "level": "walk",
        "cases": results,
        "passed": passed,
        "total": len(results),
        "pass_rate": passed / len(results) if results else 1.0,
    }


def run_full_cycle_eval() -> dict[str, Any]:
    """Run a bounded six-phase episode with replayed fixture telemetry."""
    workflow = AgenticMiningWorkflow()
    manifest = workflow.phase1_cold_start()
    candidates = workflow.phase2_precompute(count=8, header_template=GENESIS_HEADER[:76])
    hold = workflow.phase3_hold()
    workflow.current_target = 0
    local_result = workflow.phase4_submit()
    ticks = workflow.phase5_steady_state(
        cycles=2,
        telemetry_provider=lambda cycle: {
            "peer_count": cycle,
            "thermal_c": 55.0 + cycle,
            "power_w": 145.0 + cycle,
        },
        telemetry_source="fixture",
    )
    cooldown = workflow.phase6_cool_down()

    checks = {
        "valid_hardware_manifest": manifest.is_valid,
        "precompute_nonempty": bool(candidates),
        "hold_coverage_complete": hold["total_held_candidates"] == len(candidates),
        "every_probe_is_recorded": len(workflow.probe_log) == local_result.probes_taken,
        "local_reject_logged_honestly": not local_result.accepted and local_result.pool_name != "",
        "fixture_ticks_simulated": all(tick["truth_class"] == "simulated" for tick in ticks),
        "provenance_chain_valid": workflow.toe.verify_provenance(),
        "cooldown_safe": cooldown["state_safe"] and workflow.is_cooled_down,
        "no_pool_ack_claimed": all(
            share.to_dict().get("pool_accepted") is None for share in workflow.submitted_shares
        ),
    }
    return {
        "schema": "pythia.agentic-mining-eval/1",
        "level": "run",
        "case_id": "bounded-six-phase-replay",
        "checks": checks,
        "passed": all(checks.values()),
        "episode": {
            "candidate_count": len(candidates),
            "probes": workflow.probe_log,
            "telemetry": ticks,
            "cooldown": cooldown,
            "execution_scope": "research_simulation_local_checks_only",
        },
    }


def evaluate_workflow(*, trace_path: Path | None = None) -> dict[str, Any]:
    """Run Crawl/Walk/Run and optionally append one reproducible trace record."""
    started_at = time.time()
    report = {
        "schema": "pythia.agentic-mining-eval/1",
        "started_at": started_at,
        "levels": [run_crawl_suite(), run_walk_suite(), run_full_cycle_eval()],
    }
    report["finished_at"] = time.time()
    report["passed"] = all(level["passed"] for level in report["levels"])
    if trace_path is not None:
        append_trace(report, trace_path)
    return report


def append_trace(report: dict[str, Any], trace_path: Path) -> None:
    """Append a result to the rolling discovery trace without touching source."""
    trace_path = Path(trace_path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(report, sort_keys=True, default=str) + "\n")


def promote_failed_crawl_case(case: CrawlCase, dataset_path: Path) -> dict[str, Any]:
    """Promote a reviewed failure/near-miss into a versioned regression JSONL set."""
    if len(case.header_template) != 76:
        raise ValueError("regression case header_template must be exactly 76 bytes")
    if not 0 <= case.nonce < (1 << 32):
        raise ValueError("regression case nonce must be uint32")
    if not 0 <= case.target < (1 << 256):
        raise ValueError("regression case target must be uint256")
    record = {"schema": "pythia.agentic-mining-regression/1", **case.as_dict()}
    dataset_path = Path(dataset_path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    with dataset_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    return record


__all__ = [
    "CRAWL_CASES",
    "GENESIS_HASH",
    "GENESIS_HEADER",
    "GENESIS_NONCE",
    "WALK_CASES",
    "CrawlCase",
    "append_trace",
    "evaluate_workflow",
    "promote_failed_crawl_case",
    "run_crawl_case",
    "run_crawl_suite",
    "run_full_cycle_eval",
    "run_walk_case",
    "run_walk_suite",
]
