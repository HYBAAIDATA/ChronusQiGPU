from chronus.gates import Fixture
from chronus.qualify import qualify
from chronus.verdict import Status,GateResult
from chronus.crypto.signers import SignerUnavailable
import chronus.qualify as module

def empty_fixture():
    return Fixture(None,[],b"",b"",object())

def test_registry_never_green_without_evidence():
    result=qualify(empty_fixture())
    assert result.status is Status.UNQUALIFIED
    assert len(result.gates)==5

def test_crashing_gate_is_fail(monkeypatch):
    def crash(fx):
        raise RuntimeError("boom")
    monkeypatch.setattr(module,"GATES",(crash,))
    assert qualify(empty_fixture()).status is Status.FAIL

def test_missing_provider_is_unqualified(monkeypatch):
    def missing(fx):
        raise SignerUnavailable("no HSM")
    monkeypatch.setattr(module,"GATES",(missing,))
    assert qualify(empty_fixture()).status is Status.UNQUALIFIED

def test_budget_exhaustion(monkeypatch):
    monkeypatch.setattr(module,"GATES",(lambda fx:GateResult("x",Status.PASS),))
    assert qualify(empty_fixture(),budget_s=-1).status is Status.UNQUALIFIED
