"""Execute, restart and rebuild the owner-declared triad across both modes."""

import json
import pytest

from aethel.enterprise.ovid_state import UncertainStateError
from chronus.triad import ChronusTriad
from chronus.virtual_igpu.abi import Workload
from chronus.virtual_igpu.adapters import ChronusSoftwareFabricAdapter


def open_triad(root, tenant="a", mode="independent"):
    return ChronusTriad(root, tenant=tenant, mode=mode, adapters=[ChronusSoftwareFabricAdapter()])


@pytest.mark.parametrize("mode", ["independent", "host"])
def test_scaled_capacity_is_custodied_and_projection_is_disposable(tmp_path, mode):
    triad = open_triad(tmp_path, mode=mode)
    result = triad.execute(workload_id="scale", base_items=1, scale_index=10, chunk_items=50)
    assert result["executed_items"] == 123
    assert len(result["custody"]) == 3
    assert all(c["authority"] == "ovid" for c in result["custody"])
    records = triad.query(producer="chronus")
    assert len(records) == 3
    rows = [row for record in records for row in json.loads(record.payload)["output"]["rows"]]
    assert sorted(map(tuple, rows)) == sorted(map(tuple, result["rows"]))
    checkpoint = triad.checkpoint("capacity")
    assert triad.ovid.engine.verify_checkpoint(checkpoint["checkpoint_id"])["status"] == "PASS"
    triad.theseus.delete()
    restarted = open_triad(tmp_path, mode=mode)
    assert [r.to_dict() for r in restarted.query()] == [r.to_dict() for r in records]
    restarted.theseus.path.write_text('{"rows":["forged"]}')
    assert len(restarted.query()) == 3


def test_pythia_prepared_workload_and_tenant_isolation(tmp_path):
    triad = open_triad(tmp_path)
    result = triad.pythia(
        workload_id="pythia", header80=bytes(range(80)), target=b"\xff" * 32, nonces=[99, 3, 7]
    )
    assert result.output["hits"][0]["nonce"] == 99
    assert result.metrics["custody"]["authority"] == "ovid"
    assert json.loads(triad.query(workload_id="pythia")[0].payload)["output"] == result.output
    assert open_triad(tmp_path, tenant="b").query() == []
    with pytest.raises(PermissionError):
        triad.ovid.get_record("b", result.metrics["custody"]["record_id"])
    with pytest.raises(PermissionError):
        triad.submit(Workload(id="foreign", tenant="b", kind="probe", input={}))


def test_uncertain_commit_survives_restart_and_never_reports_success(tmp_path, monkeypatch):
    triad = open_triad(tmp_path)
    original = triad.ovid.engine.put_record

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("simulated lost completion")

    monkeypatch.setattr(triad.ovid.engine, "put_record", interrupted)
    from chronus.virtual_igpu.runtime import CustodyError

    with pytest.raises(CustodyError):
        triad.pythia(workload_id="interrupted", header80=bytes(80), target=bytes(32), nonces=[0])
    restarted = open_triad(tmp_path)
    assert restarted.ovid.health()["ready"] is False
    with pytest.raises(UncertainStateError):
        restarted.query()
    with pytest.raises(CustodyError):
        restarted.pythia(workload_id="retry", header80=bytes(80), target=bytes(32), nonces=[1])


def test_corrupt_both_copies_cannot_disappear_from_discovery(tmp_path):
    triad = open_triad(tmp_path)
    triad.pythia(workload_id="tamper", header80=bytes(80), target=bytes(32), nonces=[0])
    for directory in (triad.ovid.engine.primary_dir, triad.ovid.engine.replica_dir):
        for path in directory.glob("*.json"):
            value = json.loads(path.read_bytes())
            value["content_digest"] = "0" * 64
            path.write_text(json.dumps(value))
    with pytest.raises(Exception, match="(?i)(unrecoverable|valid|integrity|corrupt|custody)"):
        triad.query()
