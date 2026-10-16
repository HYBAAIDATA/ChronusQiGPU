import pytest
from chronus.agent._contracts import ContractError
from conftest import H
import hashlib
from chronus.agent.audit import AuditLedger, ReplayRecord, replay_decision


def test_chain_restore_tamper_and_anchor(ledger):
    e = ledger.append("agent_boot", {"state": "boot"}, now=1)
    data = ledger.export()
    other = AuditLedger(ledger.identity, ledger.signer)
    other.restore(data, expected_head=e.digest)
    assert other.replay() == ledger.replay()
    with pytest.raises(ContractError):
        other.restore(data.replace(b"boot", b"fake"))
    with pytest.raises(ContractError):
        other.restore(b"", expected_head=e.digest)


def test_durable_restart(ledger, tmp_path):
    path = tmp_path / "ledger.jsonl"
    disk = AuditLedger(ledger.identity, ledger.signer, path=path)
    disk.append("agent_boot", {}, now=1)
    assert AuditLedger(ledger.identity, ledger.signer, path=path).verify()


def test_stochastic_provenance_replay(ledger):
    ledger.append("agent_boot", {}, now=1)
    payload = b"unit prompt/tool/environment bytes"
    ref = hashlib.sha256(payload).hexdigest()
    record = ReplayRecord(
        H,
        "unit-model",
        (("temperature", "1"),),
        None,
        (ref,),
        (ref,),
        ref,
        ref,
        "unit-policy",
        (ref,),
        "selected tool on evidence",
    )
    from chronus.agent.audit import record_replay

    record_replay(ledger, record, now=2)
    result = replay_decision(ledger, (record,), load_evidence=lambda r: payload)
    assert result["decision_path_reconstructed"] and not result["byte_identical"]
    with pytest.raises(ContractError):
        replay_decision(ledger, (record,), load_evidence=lambda r: b"wrong")


def test_deterministic_component_compares_actual_bytes():
    from chronus.agent.audit import replay_deterministic_component

    expected = hashlib.sha256(b"ABC").hexdigest()
    assert replay_deterministic_component(b"abc", transform=bytes.upper, expected_sha256=expected)[
        "byte_identical"
    ]
    assert not replay_deterministic_component(
        b"wrong", transform=bytes.upper, expected_sha256=expected
    )["byte_identical"]
