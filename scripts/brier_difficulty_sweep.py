"""Brier calibration across a difficulty sweep — not just easy targets.

A calibration claim at easy difficulty is a claim about easy difficulty.
This drives the wired stack (real orchestrator, real scan_range, real
sha256d) across a difficulty ladder and reports the quantum_stack Brier
score honestly at each rung — it moves, and that movement IS the
calibration evidence.

Writes reports/brier_difficulty_sweep.json.
"""

import argparse
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "mla1517_platform_v3.4" / "python"))

from Intelligence.intelligence_integration import IntegratedIntelligence
from Intelligence.mining_bridge import is_wired, wire_intelligence_into_mining
from Intelligence.orchestrator import IntelligenceOrchestrator
import turing_core


def _header(tag: int):
    body = struct.pack("<q", tag) + hashlib.sha256(
        b"sweep|" + bytes([tag & 0xFF]) * 4).digest() * 2
    return body[:64], body[64:76]


def run_sweep(rates, windows, nonce_count):
    rows = []
    for rate in rates:
        # A fresh intelligence pipeline per difficulty rung: Brier memory
        # carries across rungs otherwise, and the report claims per-
        # difficulty calibration.
        orch = IntelligenceOrchestrator()
        assert wire_intelligence_into_mining(orch) and is_wired()
        engine = turing_core.PythiaMiningEngine()
        integ = IntegratedIntelligence(orch)
        orch.safety.state.cooldown_seconds = 0.01
        target = int(2**256 * rate)
        wins = 0
        res = None
        for w in range(windows):
            c1, c2 = _header(w)
            hit = engine.scan_range(c1, c2, target,
                                    nonce_start=0, nonce_count=nonce_count)
            success = hit is not None
            wins += success
            res = integ.run_cycle(
                header=c1 + c2 + b"\x00" * 4,
                target=target.to_bytes(32, "big"),
                block_context={"block_height": w},
                mining_success=success,
            )
            if success:
                orch.on_block_submitted()
                orch.on_block_accepted(
                    w, hashlib.sha256(c1 + c2).hexdigest())
            orch.on_external_block(w + 1)
            time.sleep(0.02)
        briers = res.brier_scores if res is not None else {}
        rows.append({
            "difficulty_rate": rate,
            "nonce_window": nonce_count,
            "expected_hits": rate * nonce_count,
            "windows": windows,
            "wins": wins,
            "brier_quantum_stack": round(
                briers.get("quantum_stack", 0.25), 4),
            "brier_scores": {k: round(v, 4)
                             for k, v in sorted(briers.items())},
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rates", type=float, nargs="+",
                    default=[0.5, 0.05, 0.005, 0.0005])
    ap.add_argument("--windows", type=int, default=4)
    ap.add_argument("--nonce-count", type=int, default=20_000)
    ap.add_argument("--out", default="reports/brier_difficulty_sweep.json")
    args = ap.parse_args()

    rows = run_sweep(args.rates, args.windows, args.nonce_count)
    record = {
        "sweep": rows,
        "note": "brier_quantum_stack is the self-model's calibration of "
                "the stack's emergence signal against real sha256d "
                "outcomes; it is expected to move with difficulty and is "
                "reported as measured, per-difficulty.",
        "theorem_proven": False,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    for r in rows:
        print(f"rate={r['difficulty_rate']:<7} wins={r['wins']}/{r['windows']} "
              f"brier_qs={r['brier_quantum_stack']} all={r['brier_scores']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
