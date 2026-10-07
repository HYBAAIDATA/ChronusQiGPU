"""TOE ↔ PYTHIA end-to-end mining voyage (CPU reference, regtest difficulty).

    measured window telemetry → MiningWindowAdapter → Problem
    → TOEIntelligenceRuntime.solve (tenant mode "mining")
    → PYTHIA authorize → real double-SHA256 execution (check_pow + recheck)
    → observed telemetry → runtime.learn → THESEUS snapshot
    → restart → recovered model reused

Honest scope: the job is a declared regtest-difficulty template (compact
bits 0x207fffff), not a live pool job — no pool credentials exist on this
host. Every hash, timing and validity decision is real. The decision TOE
influences is the work-window size under a latency budget; validity is
decided by ``check_pow`` alone. The "no TOE" baseline is PYTHIA's naive
default (largest declared window).

Usage: python scripts/toe_mining_voyage.py [--report PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # append: an installed toe wins over the checkout

from chronus.mla1517.mining.toe_problem import (  # noqa: E402
    WINDOW_LEVELS,
    MiningWindowAdapter,
    WorkTemplate,
    authorize,
    execute_window,
)

TEMPLATE = WorkTemplate(
    version=0x20000000,
    previous_hash=hashlib.sha256(b"toe-mining-voyage/prev").hexdigest(),
    merkle_root=hashlib.sha256(b"toe-mining-voyage/merkle").hexdigest(),
    timestamp=1_791_388_800,
    bits="207fffff",
    label="regtest-difficulty template (declared fixture)",
)


def run(custody_root: Optional[Path] = None, *, rounds: int = 2) -> Dict[str, Any]:
    import toe
    from toe.custody import open_theseus_custody, theseus_available
    from toe.runtime import TenantContext, TOEIntelligenceRuntime, TOEIntelligenceRuntimeConfig

    report: Dict[str, Any] = {
        "toe_version": toe.__version__,
        "toe_file": str(Path(toe.__file__).resolve()),
        "template": TEMPLATE.label,
    }
    nonce = 0
    history: List[Dict[str, float]] = []
    for _ in range(rounds):
        for w in WINDOW_LEVELS:
            run_ = execute_window(TEMPLATE, nonce, w)
            nonce += w
            history.append(run_.telemetry())
    largest = [h for h in history if h["window_size"] == WINDOW_LEVELS[-1]]
    budget = 0.6 * sum(h["latency_ms"] for h in largest) / len(largest)
    report["latency_budget_ms"] = budget
    report["bootstrap_rows"] = len(history)

    key = os.urandom(32)
    factory = None
    if custody_root is not None and theseus_available():

        def factory(tenant_id: str):  # noqa: E306
            return open_theseus_custody(custody_root / tenant_id, hmac_key=key)

    def runtime():
        cfg = TOEIntelligenceRuntimeConfig(
            enable_feedback=False, enable_asi=False, enable_platform=False
        )
        return TOEIntelligenceRuntime(config=cfg, custody_factory=factory)

    tenant = TenantContext("pythia-cpu-reference", mode="mining")
    adapter = MiningWindowAdapter(budget)
    rt = runtime()
    resp = rt.solve(adapter.to_problem(history), tenant)
    if not resp.ok:
        report["toe"] = {"ok": False, "error": resp.error.as_dict()}
        return report
    ep = resp.result
    report["toe"] = {
        "ok": True,
        "status": ep["status"],
        "recommended_window": (ep["recommendation"].get("interventions") or {}).get("window_size"),
        "futures_rung": ep["decision"]["futures_rung"],
        "estimated_weights": ep["identity"].get("estimated_from_samples"),
        "excluded": [
            f["action"] + ": " + str(f["excluded_because"])
            for f in ep["decision"]["policy"]["futures"]
            if not f["admissible"]
        ],
        "advisory_contains_consensus_fields": False,  # runtime refused otherwise
    }
    auth = authorize(ep, allowed=WINDOW_LEVELS, governor_max=WINDOW_LEVELS[-1])
    report["pythia_authority"] = auth
    executed = execute_window(TEMPLATE, nonce, int(auth["window_size"] or WINDOW_LEVELS[0]))
    nonce += executed.window_size
    report["execution"] = {
        "window_size": executed.window_size,
        "hashes": executed.hashes,
        "hashes_per_s": executed.hashes_per_s,
        "latency_ms": executed.latency_ms,
        "within_budget": executed.latency_ms <= budget,
        "candidates_found_by_check_pow": executed.candidates_found,
        "candidates_rechecked_valid": executed.candidates_rechecked_valid,
        "validity_authority": "chronus.mla1517.mining.pow.check_pow (+ independent SHA256d recheck)",
    }
    baseline = execute_window(TEMPLATE, nonce, WINDOW_LEVELS[-1])
    nonce += baseline.window_size
    report["baseline_no_toe"] = {
        "policy": "largest declared window",
        "window_size": baseline.window_size,
        "hashes_per_s": baseline.hashes_per_s,
        "latency_ms": baseline.latency_ms,
        "within_budget": baseline.latency_ms <= budget,
    }
    report["decision_effect"] = {
        "toe_changed_window": executed.window_size != baseline.window_size,
        "toe_within_budget": executed.latency_ms <= budget,
        "baseline_within_budget": baseline.latency_ms <= budget,
        "throughput_ratio_toe_over_baseline": (
            executed.hashes_per_s / baseline.hashes_per_s if baseline.hashes_per_s else None
        ),
    }
    learn = rt.learn(resp.decision_id, [executed.telemetry()], tenant)
    report["learning"] = {
        "ok": learn.ok,
        "assessment": (learn.result or {}).get("assessment", {}).get("status"),
        "revised": (learn.result or {}).get("revision") is not None,
        "persisted": (learn.result or {}).get("persisted"),
    }
    if factory is None:
        report["restart"] = {"available": False, "reason": "THESEUS custody unavailable"}
        return report
    history.append(executed.telemetry())
    rt2 = runtime()
    again = rt2.solve(adapter.to_problem(history), tenant)
    machine = rt2.machine_for(tenant)
    report["restart"] = {
        "available": True,
        "recovered_from": machine.recovered_from,
        "episodes_known_after_restart": len(machine.episodes),
        "bindings_after_restart": len(machine.bindings),
        "recommended_window_after_restart": (
            (again.result["recommendation"].get("interventions") or {}).get("window_size")
            if again.ok
            else None
        ),
        "replay_first_episode": machine.replay(resp.decision_id),
    }
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="toe-mining-voyage-") as tmp:
        report = run(Path(tmp))
    text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    ok = (
        report.get("toe", {}).get("ok")
        and report["execution"]["candidates_found_by_check_pow"]
        == report["execution"]["candidates_rechecked_valid"]
        and report.get("learning", {}).get("ok")
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
