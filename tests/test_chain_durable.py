import json
import pytest
from chronus.canon import canonical_bytes,NonCanonical
from chronus.chain import ChainBroken,GENESIS,verify_chain
from chronus.journal import Journal,encode,JournalCorrupt
from chronus.durable import DurableChain
from chronus.verdict import Verdict,Status
from chronus.claims import Claim,Publish,gate_claims

def test_canonical():
    assert canonical_bytes({"b":1,"a":[2,"x"]})==b'{"a":[2,"x"],"b":1}'
    with pytest.raises(NonCanonical):
        canonical_bytes({"share":27.0})
    with pytest.raises(NonCanonical):
        canonical_bytes({"x":2**60})

def test_empty_verdict():
    assert Verdict(()).status is Status.UNQUALIFIED

def test_claim_demoted():
    c=Claim("RS-1","benchmark",("bench",),Publish.PUBLISHABLE)
    assert gate_claims([c],{})[0].state is Publish.HELD

def test_torn_tail_recovery(tmp_path):
    path=tmp_path/"journal"
    with Journal(path) as journal:
        journal.append(b"first")
    with path.open("ab") as f:
        f.write(encode(b"torn")[:5])
    with Journal(path) as journal:
        assert journal.recovery.records==1
        assert journal.recovery.truncated_bytes==5

def test_complete_corruption_fatal(tmp_path):
    path=tmp_path/"journal"
    path.write_bytes(encode(b"first")[:-1]+b"X")
    with pytest.raises(JournalCorrupt):
        Journal(path).open()

def test_journal_roundtrip(tmp_path):
    with Journal(tmp_path/"journal") as j:
        j.append(b"one")
        j.append(b"two")
    with Journal(tmp_path/"journal") as j:
        assert j.records==[b"one",b"two"]

def test_empty_gate_list_is_held_even_when_publishable():
    claim=Claim("CO-EMPTY","unbacked claim",(),Publish.PUBLISHABLE)
    assert gate_claims([claim],{})[0].state is Publish.HELD
    assert gate_claims([claim],{"other":Status.PASS})[0].state is Publish.HELD
