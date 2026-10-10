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

Contract v2 additionally pins (assertions below):
  - required fields: token_hex, non_adjacent_mask, canonical_int,
    coordinate_masks (×11), context_id — missing/mistyped → fail
  - token_canonical_binding: token == ZECK-%016X of canonical_int
  - canonical_derivation: independent re-fold of coordinate_masks +
    context_id must equal canonical_int (verified against genuine
    producer vectors, not circularly)
  - skipped checks are reported, never counted as evidence

Remaining documented limitations:
  - fields outside the contract (slot_address, truth_class, is_valid,
    active_dimensions) are ignored — mutating them passes
  - canonical binding proves internal consistency under the published
    algorithm; anyone can compute the same fold — still no provenance
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pythia_consumer import cli  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "zeckendorf_certificate.json"
EXPECTED_SHA256 = "150ec7d58ef7c740757db58f1310f7ac0db39e59027817cda91b05a3d231716c"


def _c(verdict: dict, name: str) -> dict:
    return next(c for c in verdict["checks"] if c["check"] == name)


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
        assert verdict["verification_level"] == "canonical_binding"
        assert verdict["levels"]["provenance_authentication"] == "unsupported"
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

    def test_token_mutation_canonical_unchanged(self, tmp_path):
        r = _load()
        r["token_hex"] = "ZECK-" + "0" * 15 + "0"
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, "token_canonical_binding")["result"] == "fail"

    def test_canonical_mutation_token_unchanged(self, tmp_path):
        r = _load()
        r["canonical_int"] += 1
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, "canonical_derivation")["result"] == "fail"

    def test_coordinate_mask_mutation(self, tmp_path):
        r = _load()
        r["coordinate_masks"][0] ^= 0b100           # flips a legal-index bit → fold changes
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, "canonical_derivation")["result"] == "fail"

    def test_context_substitution(self, tmp_path):
        r = _load()
        r["context_id"] = "attacker-context"
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, "canonical_derivation")["result"] == "fail"

    def test_unvalidated_field_mutation_passes(self, tmp_path):
        """Fields outside contract v2 (slot_address, truth_class, is_valid)
        are ignored — mutating them is structurally undetectable. Documented
        gap, not certification."""
        r = _load()
        r["slot_address"] = 0; r["truth_class"] = "forged"
        v = _verify(tmp_path, r)
        assert v["verdict"] == "pass"


class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "token_hex", "non_adjacent_mask", "canonical_int",
        "coordinate_masks", "context_id",
    ])
    def test_missing_required_field_fails(self, tmp_path, field):
        r = _load()
        r.pop(field, None); r.pop("token", None) if field == "token_hex" else None
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, f"required:{field}")["result"] == "fail"

    def test_missing_required_skips_dependents(self, tmp_path):
        """A missing field must never pass by reducing the check set:
        dependents are reported skipped, and 'pass' is impossible."""
        r = _load(); del r["canonical_int"]
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, "canonical_derivation")["result"] == "skipped"

    @pytest.mark.parametrize("field,bad", [
        ("token_hex", 12345), ("non_adjacent_mask", "1365"),
        ("non_adjacent_mask", True), ("canonical_int", "1693898459760322"),
        ("canonical_int", False), ("coordinate_masks", [0] * 10),
        ("coordinate_masks", "00"), ("context_id", 42),
    ])
    def test_wrong_types_rejected(self, tmp_path, field, bad):
        r = _load(); r[field] = bad
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"
        assert _c(v, f"required:{field}")["result"] == "fail"

    @pytest.mark.parametrize("mask", [0b11, 0b111, 1 << 11, -1])
    def test_mask_bounds_and_adjacency(self, tmp_path, mask):
        r = _load(); r["non_adjacent_mask"] = mask
        assert _verify(tmp_path, r)["verdict"] == "fail"

    def test_unproducible_coordinate_mask(self, tmp_path):
        """Bits <2 or ≥25 are unreachable by the genuine encoder."""
        for i, bad in enumerate([0b1, 1 << 25]):
            r = _load(); r["coordinate_masks"][i] = bad
            v = _verify(tmp_path, r)
            assert v["verdict"] == "fail"

    def test_adjacent_coordinate_mask(self, tmp_path):
        r = _load(); r["coordinate_masks"][0] = 0b1100   # bits 2,3 adjacent
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"

    def test_token_alias_contradiction(self, tmp_path):
        r = _load(); r["token"] = "ZECK-0000000000000000"
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"

    def test_lowercase_token_fails_binding(self, tmp_path):
        r = _load(); r["token_hex"] = r["token_hex"].lower(); r["token"] = r["token_hex"]
        v = _verify(tmp_path, r)
        assert v["verdict"] == "fail"          # form OK, canonical binding fails

    def test_unknown_fields_ignored(self, tmp_path):
        r = _load(); r["future_field"] = {"anything": 1}
        assert _verify(tmp_path, r)["verdict"] == "pass"


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
