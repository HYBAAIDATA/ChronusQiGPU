"""Fail-closed production gates for the local EUCLID runtime."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .contracts import Authority
from .runtime import EuclidRuntime


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str


def checkpoint_state(snapshot):
    """Restore validates the seal; a new process token must not be copied.

    Compare all durable semantics, while intentionally excluding the origin
    process token and its derived document seal. This is not evidence that
    producer-bound execution rights transferred to the restored process.
    """
    return {key: snapshot[key] for key in ("schema", "creator_id", "worlds", "rights", "evidence")}


def run_production_gates(factory: Callable[[Path], EuclidRuntime]) -> dict[str, Any]:
    results: list[GateResult] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runtime = factory(root)
        report = runtime.startup_report()
        results.append(
            GateResult(
                "network-disabled",
                not report["network_enabled"] and not report["federation_enabled"],
                "public networking and federation must remain disabled",
            )
        )
        unsafe = [
            organ
            for organ in runtime.registry.report()
            if organ["authority"]
            not in {
                Authority.READ_ONLY.value,
                Authority.PROPOSE.value,
                Authority.MINING_POLICY_ONLY.value,
            }
        ]
        results.append(
            GateResult(
                "bounded-organ-authority",
                not unsafe,
                "no registered organ may directly mutate world state",
            )
        )
        memory_status = report["memory_database"]
        results.append(
            GateResult(
                "durable-memory",
                bool(memory_status.get("valid")),
                "a verified scoped memory database is required",
            )
        )
        checkpoint = root / "euclid.json"
        runtime.save(checkpoint)
        restored = EuclidRuntime.restore(checkpoint, state_dir=root / "restored")
        results.append(
            GateResult(
                "sealed-roundtrip",
                checkpoint_state(restored.snapshot())
                == checkpoint_state(json.loads(checkpoint.read_text())),
                "sealed creator, worlds, rights and evidence round-trip; restored process identity is fresh",
            )
        )
        tampered = json.loads(checkpoint.read_text())
        tampered["creator_id"] = "attacker"
        checkpoint.write_text(json.dumps(tampered))
        rejected = False
        try:
            EuclidRuntime.restore(checkpoint, state_dir=root / "tampered")
        except ValueError:
            rejected = True
        results.append(
            GateResult(
                "tamper-rejection",
                rejected,
                "modified checkpoints must be rejected",
            )
        )
        # Close inside the temporary directory's lifetime: each runtime holds a
        # SQLite handle, and a handle outliving the directory makes it
        # undeletable.
        restored.close()
        runtime.close()
    passed = all(result.passed for result in results)
    return {
        "schema": "euclid.production-gates/1",
        "passed": passed,
        "results": [result.__dict__ for result in results],
        "claim_boundary": (
            "local governed runtime gates only; not evidence of public-network "
            "deployment, general intelligence or external superiority"
        ),
    }
