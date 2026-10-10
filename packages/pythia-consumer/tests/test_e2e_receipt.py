"""End-to-end receipt validation — genuine producer → consumer verifier.

Producer (genuine, not a fixture built for the test):
    toe/poincare_golden_11d.py :: compute_zeckendorf_certificate(x, context_id)
    invoked as: compute_zeckendorf_certificate(np.linspace(-0.5, 0.5, 11),
                                               context_id="pythia-consumer-e2e-v1")
    serialized via ZeckendorfCertificate.to_dict() — bytes committed verbatim.

Fixture: tests/fixtures/zeckendorf_certificate.json
    sha256 = 150ec7d58ef7c740757db58f1310f7ac0db39e59027817cda91b05a3d231716c

Verifier surface exercised: the public `pythia verify` CLI
(pythia_consumer.cli -> verify_receipt), not an internal helper.

What this test establishes:
  - token form ("ZECK-" + 16 hex) is checked ................ PASS/FAIL cases
  - non-adjacency invariant (mask & (mask << 1)) == 0 ....... PASS/FAIL cases
  - malformed input is rejected safely, no crash ............ CLI exit codes

Documented limitations (pinned by assertions below, NOT hidden):
  - fields outside the contract (canonical_int, coordinate_masks,
    slot_address, context_id) are ignored — mutating them passes
  - receipt fields are all optional; a receipt containing only a valid
    mask yields "pass" with a reduced check count
  - no producer authentication exists: a hand-crafted dict with a legal
    token + legal mask passes. Verification is structural, not provenance.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pythia_consumer import cli  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "zeckendorf_certificate.json"
EXPECTED_SHA256 = "150ec7d58ef7c740757db58f1310f7ac0db39e59027817cda91b05a3d231716c"


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


def _verify(tmp_path: Path, receipt) -> dict:
    import io, contextlib
    p = tmp_path / "receipt.json"
    p.write_text(json.dumps(receipt))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli.main(["verify", str(p)]) in (0, 1)
    return json.loads(buf.getvalue())


class TestGenuineReceipt:
    def test_fixture_is_verbatim_producer_bytes(self):
        import hashlib
        assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == EXPECTED_SHA256
        r = _load()
        assert r["token_hex"].startswith("ZECK-") and isinstance(r["non_adjacent_mask"], int)

    def test_positive_e2e_via_public_cli(self, tmp_path, capsys):
        assert cli.main(["verify", str(FIXTURE)]) == 0
        verdict = json.loads(capsys.readouterr().out)
        assert verdict["verdict"] == "pass"
        assert verdict["verification_level"] == "structural"
        assert verdict["custody_proof"] is False
        names = {c["check"] for c in verdict["checks"]}
        assert {"token_format", "non_adjacent_mask"} <= names
        assert all(c["passed"] for c in verdict["checks"])


class TestTamperedReceipt:
    def test_corrupted_token_rejected(self, tmp_path):
        r = _load()
        r["token_hex"] = "ZECK-000000000000000G"
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"

    def test_adjacent_mask_rejected(self, tmp_path):
        r = _load()
        r["non_adjacent_mask"] |= 0b10          # 1365|2 = 1367 sets bits 0+1 (adjacent)
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"

    def test_wrong_type_rejected(self, tmp_path):
        r = _load()
        r["non_adjacent_mask"] = "1365"
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"

    def test_unvalidated_field_mutation_passes(self, tmp_path):
        """canonical_int is outside the verifier contract — mutating it is
        undetectable structurally. This documents, not certifies, the gap."""
        r = _load()
        r["canonical_int"] = 0
        v = _verify(tmp_path, r)
        assert v["verdict"] == "pass"

    def test_missing_optional_field_reduces_coverage(self, tmp_path):
        """All fields are optional by contract: removing token_hex still
        yields 'pass' — on fewer checks. Coverage shrink is observable."""
        r = _load()
        del r["token_hex"], r["token"]
        v = _verify(tmp_path, r)
        assert v["verdict"] == "pass"
        assert len(v["checks"]) == 1


class TestMalformedInput:
    def test_invalid_json_rejected_safely(self, tmp_path, capsys):
        p = tmp_path / "bad.json"
        p.write_bytes(b"{not json")
        assert cli.main(["verify", str(p)]) == 2
        capsys.readouterr()

    def test_missing_file_rejected_safely(self, tmp_path, capsys):
        assert cli.main(["verify", str(tmp_path / "nope.json")]) == 2
        capsys.readouterr()

    def test_non_object_rejected(self, tmp_path):
        p = tmp_path / "arr.json"
        p.write_text("[1, 2, 3]")
        assert cli.main(["verify", str(p)]) == 1
