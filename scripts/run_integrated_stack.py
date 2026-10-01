"""Live run of the wired quantum stack through the real mining path.

NOT a simulation: this instantiates the real ``IntelligenceOrchestrator``,
wires the intelligence bridge into ``turing_core.PythiaMiningEngine``'s
``scan_range`` (the same monkey-patch production tests use), then scans
real headers at an easy target so winners land inside the window. Every
hash is a real double-SHA256 evaluated against the real consensus
predicate — the stack's signals can only reorder and annotate, never
bypass it.

Per window the run reports: the guidance source, the quantum-stack
telemetry (YM regime / consciousness state / emergence / QNP) that
``guide_mining`` now emits, whether the scan found a winner, and the
integrated-intelligence cycle result driven by that real outcome.

Usage: python -m scripts.run_integrated_stack [--windows 6] [--rate 0.05]
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "chronus/mla1517_platform" / "python")
)

import turing_core  # noqa: E402
from Intelligence.mining_bridge import (  # noqa: E402
    _MEASURED_RATE,
    is_wired,
    wire_intelligence_into_mining,
)
from Intelligence.orchestrator import IntelligenceOrchestrator  # noqa: E402
from Intelligence.intelligence_integration import (  # noqa: E402
    IntegratedIntelligence,
)


def _header(tag: int) -> tuple[bytes, bytes]:
    """Build a real 76-byte header prefix partitioned for scan_range."""
    seed = hashlib.sha256(f"wired-stack-{tag}".encode()).digest()
    body = struct.pack("<I", 0x20000000) + seed + hashlib.sha256(
        seed + bytes([tag & 0xFF])
    ).digest() + struct.pack("<II", 0x69000000 + tag, 0x207FFFFF)
    assert len(body) == 76
    return body[:64], body[64:76]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", type=int, default=6)
    ap.add_argument("--rate", type=float, default=0.05,
                    help="per-nonce win probability (easy target)")
    ap.add_argument("--nonce-count", type=int, default=50_000)
    args = ap.parse_args()

    target = int(2**256 * args.rate)

    print("Building real IntelligenceOrchestrator (registry instantiate_all)...")
    t0 = time.monotonic()
    orch = IntelligenceOrchestrator()
    print(f"  orchestrator up in {time.monotonic()-t0:.1f}s; "
          f"quantum_stack wired: {orch.quantum_stack is not None}")

    assert wire_intelligence_into_mining(orch) and is_wired()
    engine = turing_core.PythiaMiningEngine()
    integ = IntegratedIntelligence(orch)
    # The consecutive-block cooldown is real and would otherwise hold for
    # its full duration; shrink the wall-clock wait only (the FSM still
    # runs WAITING_EXTERNAL -> COOLDOWN -> IDLE through the real tick).
    orch.safety.state.cooldown_seconds = 0.01
    from mining.bitcoin_hasher import BitcoinHasher

    hasher = BitcoinHasher(backend="auto")  # opencl when silicon exists, else cpu oracle
    print(f"  golden-stride backend: {hasher.backend} "
          f"({hasher.fallback_reason or 'device bound'})")
    print(f"  silicon status: {hasher.silicon_status()}")
    from hyba.operating_model.lemma import ordering_lemmas_signed
    print(f"  ordering lemmas signed: {ordering_lemmas_signed()}")

    wins = 0
    total_t = 0.0
    for w in range(args.windows):
        chunk1, chunk2 = _header(w)
        t = time.monotonic()
        hit = engine.scan_range(chunk1, chunk2, target,
                                nonce_start=0, nonce_count=args.nonce_count)
        dt = time.monotonic() - t
        total_t += dt
        success = hit is not None
        wins += success

        # Pull the real guidance diagnostics (same call scan_range made).
        full_header = chunk1 + chunk2 + b"\x00" * 4
        g = orch.guide_mining(full_header, target.to_bytes(32, "big"),
                              nonce_window=args.nonce_count)
        qs = g.diagnostics.get("quantum_stack", {})

        # ASIC-mode pass: the golden-stride op probes the same header/target
        # through the hasher backend (device-derived nonce sequence, hit
        # FIFO; CPU oracle when no OpenCL silicon is attached).
        gold_win, gold_digest, gold_hashes, gold_hits = hasher.grind_target_gold(
            full_header, target.to_bytes(32, "big"), args.nonce_count
        )

        res = integ.run_cycle(
            header=full_header,
            target=target.to_bytes(32, "big"),
            block_context={"block_height": w, "header_bytes": full_header[:32]},
            mining_success=success,
        )
        # Advance the chain so the consecutive-block safety guard releases
        # the next window (a real chain sees external blocks between wins).
        if success:
            orch.on_block_submitted()
            orch.on_block_accepted(w, hashlib.sha256(full_header).hexdigest())
        orch.on_external_block(w + 1)
        time.sleep(0.02)  # let the (shortened) cooldown tick elapse

        print(f"\nwindow {w}: {'WIN' if success else 'miss'} "
              f"(nonce={hit[0] if hit else '-'}) in {dt*1e3:.0f}ms")
        print(f"  source={g.source} conf={g.confidence:.3f}")
        print(f"  quantum_stack: ym={qs.get('ym_regime')} "
              f"iit={qs.get('iit_composite_state')} "
              f"emergence={qs.get('emergence_probability')} "
              f"qnp={qs.get('qnp_generated')} "
              f"ordering={qs.get('ordering', '-')} "
              f"resonant={qs.get('resonant_fraction', '-')}")
        print(f"  integrated: global_conf={res.global_calibrated_confidence:.3f} "
              f"q_emergence={res.quantum_emergence:.3f} qnp={res.quantum_qnp}")
        print(f"  gold_stride: {'WIN' if gold_win is not None else 'miss'} "
              f"nonce={gold_win} hits={len(gold_hits)} "
              f"hashes={gold_hashes} backend={hasher.backend}")
        print("  brier: " + " ".join(
            f"{k}={v:.3f}" for k, v in sorted(res.brier_scores.items())))

    print("\n== run summary ==")
    print(f"windows: {wins}/{args.windows} wins "
          f"(expected ~{min(1.0, args.rate*args.nonce_count):.0%} at this "
          f"target size)")
    hps = (_MEASURED_RATE["hashes"] / _MEASURED_RATE["seconds"]
           if _MEASURED_RATE["seconds"] else 0.0)
    print(f"measured digest rate: {hps:,.0f} hashes/s over "
          f"{_MEASURED_RATE['hashes']:,} real sha256d evaluations")
    print(f"stack live context: {orch.quantum_stack.live_context() if orch.quantum_stack else 'unwired'}")
    print("note: every signal above reorders/annotates; sha256d<=target "
          "was the sole accept authority in every scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
