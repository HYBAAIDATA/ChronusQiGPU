"""Consumer package tests — verify math, census shape, CLI smoke."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pythia_consumer import census, cli, verify  # noqa: E402


class TestMath:
    def test_fibonacci_known(self):
        assert [verify.fibonacci(n) for n in range(10)] == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        assert verify.fibonacci(20) == 6765

    def test_lucas_ladder_values(self):
        assert verify.lucas(0) == 2 and verify.lucas(10) == 123
        assert verify.lucas(15) == 1364 and verify.lucas(20) == 15127

    def test_cassini_identity(self):
        for n in (1, 2, 7, 15, 20, 76):
            assert verify.cassini_holds(n)

    def test_zeckendorf_roundtrip(self):
        for n in (1, 4, 100, 1364, 28143753123):
            idx = verify.zeckendorf(n)
            assert verify.zeckendorf_legal(idx)
            assert sum(verify.fibonacci(i) for i in idx) == n

    def test_zeckendorf_legality(self):
        assert not verify.zeckendorf_legal([3, 4])      # adjacent
        assert verify.zeckendorf_legal([3, 5, 8])       # non-adjacent
        assert not verify.zeckendorf_legal([5, 5])      # duplicate


class TestReceipt:
    def _good(self):
        """Contract-v2 compliant receipt — core values are a genuine
        compute_zeckendorf_certificate(np.zeros(11), "") output."""
        i = 7
        return {
            "token_hex": "ZECK-0006049777FAC6C2",
            "non_adjacent_mask": 1365,
            "canonical_int": 1693898459760322,
            "coordinate_masks": [0] * 11,
            "context_id": "",
            "zeckendorf_indices": verify.zeckendorf(100),
            "zeckendorf_value": 100,
            "cassini_ledger": [[i, verify.fibonacci(i - 1), verify.fibonacci(i),
                                verify.fibonacci(i + 1), (-1) ** i]],
            "lucas_ladder": {"15": 1364},
        }

    def test_pass(self):
        v = verify.verify_receipt(self._good())
        assert v["verdict"] == "pass" and v["custody_proof"] is False
        assert v["levels"]["canonical_binding"] is True
        assert v["levels"]["provenance_authentication"] == "unsupported"

    def test_fail_mask(self):
        r = self._good(); r["non_adjacent_mask"] = 0b11
        assert verify.verify_receipt(r)["verdict"] == "fail"

    def test_fail_cassini(self):
        r = self._good(); r["cassini_ledger"][0][3] += 1
        assert verify.verify_receipt(r)["verdict"] == "fail"

    def test_empty_fails_required(self):
        v = verify.verify_receipt({})
        assert v["verdict"] == "fail"
        assert all(c["result"] in ("fail", "skipped") for c in v["checks"])

    def test_fail_not_dict(self):
        assert verify.verify_receipt("x")["verdict"] == "fail"


class TestCensus:
    def test_node_status_shape(self):
        s = census.node_status()
        for key in ("platform", "backends", "products", "compute_routes"):
            assert key in s
        assert s["backends"]["cpu"] is True
        assert s["mining_performed"] is False

    def test_products_include_named_three(self):
        names = {p["distribution"] for p in census.available_products()}
        assert {"hyba-chronos-one-igpu", "hyba-ovid-data-organisation",
                "hyba-theseus-storage"} <= names
        for p in census.available_products():
            assert p["state"] in ("available", "partial", "absent")
            assert p["origin"] in ("bundled", "installed", "absent")


class TestCli:
    def test_version(self, capsys):
        assert cli.main(["version"]) == 0
        assert "hyba-pythia-consumer" in capsys.readouterr().out

    def test_verify_exit_codes(self, tmp_path, capsys):
        good = tmp_path / "r.json"
        good.write_text(json.dumps({
            "token_hex": "ZECK-0006049777FAC6C2", "non_adjacent_mask": 1365,
            "canonical_int": 1693898459760322, "coordinate_masks": [0] * 11,
            "context_id": ""}))
        assert cli.main(["verify", str(good)]) == 0
        bad = tmp_path / "bad.json"; bad.write_text(json.dumps({"non_adjacent_mask": 3}))
        assert cli.main(["verify", str(bad)]) == 1
        capsys.readouterr()

    def test_products_cmd(self, capsys):
        assert cli.main(["products"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert isinstance(out, list) and len(out) >= 10
