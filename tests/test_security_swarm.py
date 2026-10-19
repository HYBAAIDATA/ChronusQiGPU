"""Security Swarm & Telemetry Test Suite (17/17 tests).

Maps the full `test_security_swarm.test.ts` and `test_telemetry.test.ts` suite
from the Recursive Self-Learning Achievement specification into the canonical
Python single-backend repository.
"""

from __future__ import annotations

import numpy as np
import pytest

from Intelligence.recursive_self_learning import RecursiveSelfLearningSubstrate
from Intelligence.security_swarm import (
    SecuritySwarm,
    SecuritySwarmAgent,
    SwarmTelemetryEvent,
    lucas_bound,
)


def test_01_security_swarm_initializes_shards_a_and_b():
    swarm = SecuritySwarmAgent(shard_size=32, seed=1)
    shard_a = swarm.get_shard_a()
    shard_b = swarm.get_shard_b()
    assert shard_a.shape == (32,)
    assert shard_b.shape == (32,)
    assert shard_a.dtype == np.uint8
    assert not np.array_equal(shard_a, shard_b)


def test_02_camel_case_and_class_alias_compatibility():
    assert SecuritySwarm is SecuritySwarmAgent
    swarm = SecuritySwarm(shard_size=16, seed=2)
    assert np.array_equal(swarm.getShardA(), swarm.get_shard_a())
    assert np.array_equal(swarm.getShardB(), swarm.get_shard_b())


def test_03_baseline_irreducibility_is_modular_0052():
    swarm = SecuritySwarmAgent(shard_size=32, seed=3)
    assert swarm.measure_irreducibility() == 0.0520
    assert swarm.snapshot()["entangled"] is False


def test_04_xor_entanglement_with_mining_entropy_elevates_irreducibility():
    swarm = SecuritySwarmAgent(shard_size=32, seed=4)
    entropy = np.arange(1, 33, dtype=np.uint8) * 7
    res = swarm.entangle_with_mining(entropy, mask=0xAA)
    assert res["entangled"] is True
    assert res["irreducibility"] >= 0.5625


def test_05_complementary_bitmask_partition_reconstructs_exact_mining_entropy():
    swarm = SecuritySwarmAgent(shard_size=32, seed=5)
    entropy = np.random.default_rng(5).integers(1, 255, size=32, dtype=np.uint8)
    swarm.entangle_with_mining(entropy, mask=0xF0)
    recovered = swarm.reconstruct_mining_entropy()
    assert np.array_equal(recovered, entropy)
    assert swarm.verify_mining_integrity() is True


def test_06_corrupting_shard_a_breaks_mining_operation():
    swarm = SecuritySwarmAgent(shard_size=32, seed=6)
    entropy = np.ones(32, dtype=np.uint8) * 123
    swarm.entangle_with_mining(entropy, mask=0xAA)
    assert swarm.verify_mining_integrity() is True
    swarm.corrupt_shard("A", flip_mask=0xFF)
    assert swarm.verify_mining_integrity() is False


def test_07_corrupting_shard_b_breaks_mining_operation():
    swarm = SecuritySwarmAgent(shard_size=32, seed=7)
    entropy = np.ones(32, dtype=np.uint8) * 201
    swarm.entangle_with_mining(entropy, mask=0xAA)
    swarm.corrupt_shard("B", flip_mask=0x55)
    assert swarm.verify_mining_integrity() is False


def test_08_heal_shards_restores_entangled_mining_integrity():
    swarm = SecuritySwarmAgent(shard_size=32, seed=8)
    entropy = np.arange(10, 42, dtype=np.uint8)
    swarm.entangle_with_mining(entropy, mask=0xAA)
    swarm.corrupt_shard("A")
    assert swarm.verify_mining_integrity() is False
    swarm.heal_shards()
    assert swarm.verify_mining_integrity() is True


def test_09_heal_shards_when_unentangled_restores_baseline():
    swarm = SecuritySwarmAgent(shard_size=16, seed=9)
    orig_a = swarm.get_shard_a()
    swarm.corrupt_shard("A")
    assert not np.array_equal(swarm.get_shard_a(), orig_a)
    swarm.heal_shards()
    assert np.array_equal(swarm.get_shard_a(), orig_a)


def test_10_telemetry_records_init_entanglement_corruption_and_heal():
    swarm = SecuritySwarmAgent(shard_size=16, seed=10)
    swarm.entangle_with_mining(np.ones(16, dtype=np.uint8) * 42)
    swarm.corrupt_shard("A")
    swarm.verify_mining_integrity()
    swarm.heal_shards()
    kinds = [ev.kind for ev in swarm.telemetry_log]
    assert "SWARM_INIT" in kinds
    assert "COGNITIVE_ENTANGLEMENT" in kinds
    assert "SHARD_CORRUPTION_INJECTED" in kinds
    assert "MINING_INTEGRITY_FAILURE" in kinds
    assert "SHARD_HEALED" in kinds


def test_11_telemetry_event_dataclass_and_timestamps():
    swarm = SecuritySwarmAgent(shard_size=16, seed=11)
    ev = swarm.telemetry_log[0]
    assert isinstance(ev, SwarmTelemetryEvent)
    assert ev.event_id == 1
    assert ev.timestamp > 0


def test_12_snapshot_exports_complete_swarm_state():
    swarm = SecuritySwarmAgent(shard_size=16, seed=12)
    swarm.entangle_with_mining(np.ones(16, dtype=np.uint8) * 99)
    snap = swarm.snapshot()
    assert snap["schema"] == "intelligence.security_swarm/1"
    assert snap["entangled"] is True
    assert snap["mining_integrity_ok"] is True
    assert len(snap["shard_a"]) == 16
    assert len(snap["shard_b"]) == 16


def test_13_invalid_shard_size_raises_value_error():
    with pytest.raises(ValueError):
        SecuritySwarmAgent(shard_size=0)


def test_14_short_mining_entropy_auto_resizes_cleanly():
    swarm = SecuritySwarmAgent(shard_size=32, seed=14)
    res = swarm.entangle_with_mining([1, 2, 3, 4], mask=0xAA)
    assert res["entangled"] is True
    assert swarm.verify_mining_integrity() is True


def test_15_recursive_substrate_shard_corruption_breaks_mining():
    sub = RecursiveSelfLearningSubstrate(dimension=32, seed=15)
    sub.evolve(0.4)
    assert sub.verify_mining_with_shards() is True
    sub.corrupt_security_shard("A")
    assert sub.verify_mining_with_shards() is False


def test_16_recursive_substrate_convergence_acceleration_demonstration():
    sub = RecursiveSelfLearningSubstrate(dimension=32, seed=16)
    demo = sub.demonstrate_convergence_acceleration(cycles=50)
    assert demo["accelerated"] is True
    assert demo["recursion_depth"] == 100


def test_17_lucas_bound_wiring_on_security_swarm():
    res = lucas_bound(10)
    assert res["module"] == "Intelligence.security_swarm"
