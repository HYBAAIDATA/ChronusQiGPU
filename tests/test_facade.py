from chronus.core import facade
from chronus.security.canonical import canonical_bytes
import pytest
def test_empty_gates_fail():
    assert facade.Manifest("now").posture == "not_qualified"
def test_failing_gate_fails(monkeypatch):
    monkeypatch.setattr(facade, "GATES", (("GX", "fail", lambda: (False, "no")),))
    assert facade.run().posture == "not_qualified"
def test_crashing_gate_fails(monkeypatch):
    def crash():
        raise RuntimeError("failure")
    monkeypatch.setattr(facade, "GATES", (("GX", "crash", crash),))
    assert not facade.run().gates[0].passed
def test_restricted_json():
    assert canonical_bytes({"b": 2, "a": 1}) == canonical_bytes({"a": 1, "b": 2})
    with pytest.raises(TypeError):
        canonical_bytes({"a": 1.5})
def test_mldsa_blocks():
    assert facade._gate_signers()[0] is False
