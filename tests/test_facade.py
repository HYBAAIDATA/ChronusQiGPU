from chronus.core import facade
from chronus.security.canonical import canonical_bytes
import pytest

pytestmark = pytest.mark.simulated

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


def test_purity_scanner_checks_installed_sources_outside_repository(tmp_path, monkeypatch):
    from chronus.core.purity_scanner import scan_installed_package

    monkeypatch.chdir(tmp_path)
    scanned, violations = scan_installed_package()
    assert scanned > 0
    assert violations == []


def test_purity_scanner_fails_if_required_package_is_missing(monkeypatch):
    from chronus.core import purity_scanner

    monkeypatch.setattr(purity_scanner, "EXACT_SUBPACKAGES", ("absent-package",))
    _, violations = purity_scanner.scan_installed_package()
    assert any("required purity package missing" in item for item in violations)


def test_read_only_manifest_remains_unqualified(monkeypatch):
    from pathlib import Path

    original = Path.write_text

    def denied_manifest(self, *args, **kwargs):
        if self.name == "qualification_manifest_v36.json":
            raise PermissionError("read-only installation")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", denied_manifest)
    record = facade.ChronusVerificationOrchestrator.run_complete_verification_suite()
    assert record["qualification_status"] == "NOT_QUALIFIED"
    assert any("manifest unavailable" in reason for reason in record["blockers"])
