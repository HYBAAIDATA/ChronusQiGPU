"""Actual local canonical SharedTuring/THESEUS/OVID; not live enterprise wiring.

The ephemeral HMAC key authorizes only this isolated test directory. No real
Guardian, enterprise tenant, hardware or Salamander action is substituted.
"""

import secrets

from aethel.enterprise.lifecycle import CompositionRoot
from aethel.enterprise.system_relations import ProductionSystemRelations
from turing_universal_quantum_computer import Program
from turing_universal_quantum_computer.pipeline import VQCRequest


def test_canonical_shared_custody_replays_after_lifecycle_restart(tmp_path):
    key = secrets.token_bytes(32)
    root = tmp_path / "shared-owner"
    lifecycle = CompositionRoot(root, tenant="test-tenant", hmac_key=key)
    try:
        lifecycle.start()
        shared = ProductionSystemRelations(lifecycle).turing()
        report = shared.run(VQCRequest(program=Program(2).then("h", 0).then("cx", 0, 1)))
        assert report.verdict == "PASS"
        assert report.certificate and report.witness
        assert set(shared.last_bindings) == {
            "program",
            "result",
            "certificate",
            "witness",
            "report",
            "replay",
        }
        assert shared.replay()["passed"] is True
        for binding in shared.last_bindings.values():
            assert lifecycle.fabric.verify(binding.binding_id)["passed"] is True
    finally:
        lifecycle.stop()
    recovered = CompositionRoot(root, tenant="test-tenant", hmac_key=key)
    try:
        recovered.start()
        shared = ProductionSystemRelations(recovered).turing()
        replay = shared.replay()
        assert replay["passed"] is True
        assert replay["replay_source"] == "durable_graph"
        assert {"program", "result", "certificate", "witness"} <= set(replay["record_kinds"])
    finally:
        recovered.stop()
