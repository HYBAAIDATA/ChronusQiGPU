import json
import pytest

from chronus.product import TIERS, PackagedGPU, CapacityExceeded
from chronus.fleet.pythia import PythiaFleet
from chronus.virtual_igpu.adapters import ChronusSoftwareFabricAdapter
from chronus.virtual_igpu.abi import Workload


def adapters():
    return [ChronusSoftwareFabricAdapter()]


def test_installed_fleet_bootstrap_does_not_expose_private_turing_modules(tmp_path, monkeypatch):
    import sys
    from chronus.fleet import workload_contracts

    package = tmp_path / "turing_universal_quantum_computer"
    package.mkdir()
    (package / "__init__.py").write_text("")
    monkeypatch.setattr(
        workload_contracts, "__file__", str(tmp_path / "chronus/fleet/workload_contracts.py")
    )
    before = list(sys.path)
    result = workload_contracts.ensure_canonical_import_roots()
    assert result["bootstrapped_paths"] == []
    assert sys.path == before


def test_tiers_use_existing_exact_algebra_and_enforce_bounds(tmp_path):
    from aethel.fibonacci import fibonacci, cassini_holds
    from chronus.igpu.scaled_plan import ScaledPlan

    for tier in TIERS.values():
        manifest = tier.manifest()
        assert tier.max_items_per_request == ScaledPlan(32, tier.scale_index).effective_items
        assert tier.max_custody_bytes == fibonacci(tier.storage_index) * 1024**2
        assert cassini_holds(manifest["storage"]["cassini_witness"])
        assert manifest["storage"]["binet_value"] == fibonacci(tier.storage_index)
        assert manifest["guaranteed_hashrate"] is None
    gpu = PackagedGPU(tmp_path, tenant="a", adapters=adapters())
    request = Workload(
        id="over",
        tenant="a",
        kind="sha256d_scan",
        input={
            "header80_hex": bytes(80).hex(),
            "target_hex": bytes(32).hex(),
            "nonces": [0] * (TIERS["starter"].max_items_per_request + 1),
        },
    )
    with pytest.raises(CapacityExceeded):
        gpu.submit(request)
    from dataclasses import replace

    ranged = replace(
        request,
        content_hash=None,
        input={
            "header80_hex": bytes(80).hex(),
            "target_hex": bytes(32).hex(),
            "count": TIERS["starter"].max_items_per_request + 1,
        },
    )
    with pytest.raises(CapacityExceeded):
        gpu.submit(ranged)
    assert gpu.triad.query() == []
    with pytest.raises(CapacityExceeded):
        PythiaFleet(tmp_path / "over", tenant="a", tier="starter", workers=2)


@pytest.mark.parametrize("mode", ["independent", "host"])
def test_fleet_executes_partitions_with_custody_and_measured_counts(tmp_path, mode):
    fleet = PythiaFleet(
        tmp_path, tenant="pythia", tier="pro", workers=3, mode=mode, adapter_factory=adapters
    )
    nonces = [91, 37, 0, 22, 8, 4, 7, 12]
    winner, digest, done = fleet.grind_target_batch(bytes(range(80)), bytes(32), nonces)
    assert winner is digest is None
    assert done == len(nonces)
    evidence = fleet.last_batch_evidence
    assert [tuple(s["partition"]) for s in evidence["shards"]] == [(0, 3), (3, 6), (6, 8)]
    assert evidence["sha256d_evaluations"] == len(nonces)
    assert evidence["measured_hashes_per_second"] > 0
    assert all(s["custody"]["authority"] == "ovid" for s in evidence["shards"])
    assert (
        sum(n.tier.max_custody_bytes for n in fleet.nodes.values())
        <= TIERS["pro"].max_custody_bytes
    )
    first = next(iter(fleet.nodes.values())).triad
    stored = first.ovid.get_record("pythia", evidence["custody_record"])
    assert json.loads(stored.payload)["sha256d_evaluations"] == 8
    assert fleet.physical_device_executed is False
    winner, digest, done = fleet.grind_target_batch(bytes(range(80)), b"\xff" * 32, nonces)
    assert winner == nonces[0]  # submitted order, not worker completion order
    assert done == 3  # one actual evaluation in each software shard
    assert len(digest) == 32


def test_fleet_lost_worker_fails_closed_without_success_receipt(tmp_path, monkeypatch):
    fleet = PythiaFleet(tmp_path, tenant="p", tier="pro", workers=2, adapter_factory=adapters)
    broken = list(fleet.nodes.values())[1]
    monkeypatch.setattr(broken, "submit", lambda _w: (_ for _ in ()).throw(OSError("lost worker")))
    with pytest.raises(OSError, match="lost worker"):
        fleet.grind_target_batch(bytes(80), bytes(32), [0, 1, 2, 3])
    assert fleet.last_batch_evidence["completion_state"] == "DEVICE_ERROR"
    first = next(iter(fleet.nodes.values())).triad
    assert all(r.kind != "pythia_fleet_complete" for r in first.query(producer="pythia"))


def test_package_keeps_original_binet_zeckendorf_storage_contract(tmp_path):
    from aethel.encoding import fold, unfold
    from aethel.storage import AddressSpace

    raw = b"\x00" * 64 + bytes(range(256))
    form = fold(raw)
    assert unfold(form) == raw
    space = AddressSpace()
    address = space.write(raw)
    space.snapshot(tmp_path)
    assert AddressSpace.attach(tmp_path).read(address) == raw
    assert space.ledger.verify_ledger()
