#!/usr/bin/env python3
"""Reproducible local demonstration using production control classes."""
from __future__ import annotations
import hashlib
import json
import tempfile
import time
from pathlib import Path

from chronus.mla1517.mining.closed_loop import ClosedLoopOptimizer
from chronus.mla1517.mining.recovery_authority import RecoveryGovernor


def measure(window: int, rounds: int = 200) -> tuple[int, float]:
    started = time.perf_counter()
    value = b"pythia"
    completed = 0
    for _ in range(rounds):
        for nonce in range(window):
            value = hashlib.sha256(value + nonce.to_bytes(4, "little")).digest()
            completed += 1
    return window, (time.perf_counter() - started) / rounds


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoint = root / "worker.json"
        checkpoint.write_text("{corrupt", encoding="utf-8")
        events = []
        governor = RecoveryGovernor(on_event=lambda kind, record: events.append((kind, record.state.value)))
        print("START\nsystem monitoring")
        try:
            json.loads(checkpoint.read_text())
            healthy = True
        except json.JSONDecodeError:
            healthy = False
        print("\nFAULT INJECTED\ninvalid state detected")
        recovery = governor.propose(["RESTORE_CHECKPOINT"], "checkpoint JSON rejected")
        assert recovery is not None
        def restore_checkpoint() -> str:
            checkpoint.write_text('{"healthy":true}', encoding="utf-8")
            return "RESTORE_CHECKPOINT"

        governor.dispatch(recovery, [("RESTORE_CHECKPOINT", restore_checkpoint)])
        recovered = json.loads(checkpoint.read_text()).get("healthy") is True
        governor.observe(recovered)
        print("\nHEALING ACTION\nverified checkpoint restored")
        print("\nRECOVERY\nsystem healthy again")

        state = root / "optimisation.json"
        opt = ClosedLoopOptimizer(min_samples=3, state_path=state)
        for window in (64, 64, 64):
            opt.select(route="cpu_reference", proposed_window=window)
            done, elapsed = measure(window)
            opt.observe(route="cpu_reference", planned_window=window,
                        completed_work=done, elapsed_seconds=elapsed,
                        completion_state="COMPLETE")
        print("\nBASELINE\nwindow=64 measured")
        assert opt.select(route="cpu_reference", proposed_window=256) == 256
        print("\nOPTIMISATION TRIAL\nwindow=256 bounded trial")
        for _ in range(3):
            done, elapsed = measure(256)
            opt.observe(route="cpu_reference", planned_window=256,
                        completed_work=done, elapsed_seconds=elapsed,
                        completion_state="COMPLETE")
        print("\nDECISION\n" + opt.history[-1].event + ": " + opt.history[-1].reason)
        restored = ClosedLoopOptimizer(state_path=state)
        print("\nFINAL STATE")
        print(json.dumps({"active": restored.active, "recovery": governor.snapshot(),
                          "optimisation": restored.snapshot(), "evidence_persisted": state.exists()},
                         sort_keys=True, default=str))


if __name__ == "__main__":
    main()
