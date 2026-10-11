"""Companion PWA + device-offer tests — census device block, packaged
assets, console routes, and JS/Python verifier parity via macOS JXA."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pythia_consumer import census  # noqa: E402

PKG = Path(__file__).resolve().parent.parent / "src" / "pythia_consumer"
COMPANION = PKG / "companion"


class TestDeviceOffer:
    def test_offer_tier_thresholds(self):
        assert census.offer_tier(16) == "pythia-node"
        assert census.offer_tier(36) == "pythia-node"
        assert census.offer_tier(95.9) == "pythia-node"
        assert census.offer_tier(96) == "pythia-node-large-memory"
        assert census.offer_tier(192) == "pythia-node-large-memory"
        assert census.offer_tier(None) is None

    def test_device_block_shape(self):
        d = census.device_block()
        for key in ("family", "offer_tier", "unified_memory"):
            assert key in d
        assert d["family"] in (
            "macbook", "imac", "mac-studio", "mac-mini", "mac-pro",
            "mac", "unknown", "non-apple")
        if d["unified_memory"] and d.get("memory_gib"):
            assert d["offer_tier"] in ("pythia-node", "pythia-node-large-memory")

    def test_device_in_node_status(self):
        s = census.node_status()
        assert "device" in s
        assert s["mining_performed"] is False


class TestCompanionAssets:
    @pytest.mark.parametrize("name", [
        "index.html", "verify.js", "sw.js", "manifest.webmanifest", "icon.png"])
    def test_asset_present(self, name):
        assert (COMPANION / name).is_file()

    def test_icon_is_png(self):
        assert (COMPANION / "icon.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_manifest_is_standalone(self):
        m = json.loads((COMPANION / "manifest.webmanifest").read_text())
        assert m["display"] == "standalone"
        assert m["icons"]


class TestConsoleRoutes:
    def _server(self):
        from pythia_consumer.console import make_handler
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(None))
        return srv

    def _get(self, path):
        import threading, urllib.error, urllib.request
        srv = self._server()
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{srv.server_address[1]}{path}"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return r.status, r.read(), r.headers.get("Content-Type")
            except urllib.error.HTTPError as e:
                return e.code, e.read(), e.headers.get("Content-Type")
        finally:
            srv.shutdown()
            srv.server_close()

    def test_companion_index(self):
        status, body, ctype = self._get("/companion")
        assert status == 200 and b"PYTHIA" in body and "text/html" in ctype

    def test_companion_assets(self):
        for name, frag in (("verify.js", b"PythiaVerify"),
                           ("sw.js", b"pythia-companion-v1"),
                           ("manifest.webmanifest", b"PYTHIA Companion"),
                           ("icon.png", b"\x89PNG")):
            status, body, _ = self._get(f"/companion/{name}")
            assert status == 200 and frag in body, name

    def test_companion_traversal_rejected(self):
        status, _, _ = self._get("/companion/../census.py")
        assert status == 404

    def test_status_has_device(self):
        status, body, _ = self._get("/api/status")
        s = json.loads(body)
        assert status == 200 and "device" in s


class TestMint:
    def test_minted_receipt_verifies(self):
        from pythia_consumer import mint, verify
        for kwargs in ({}, {"context_id": "ctx-1"}, {"data": b"payload-bytes"},
                       {"data": "unicode-∂-text".encode()}, {"context_id": "c", "data": b"d"}):
            r = mint.mint_receipt(**kwargs)
            v = verify.verify_receipt(r)
            assert v["verdict"] == "pass", (kwargs, v["checks"])
            assert v["levels"]["canonical_binding"] is True
            assert r["producer"]["provenance"].startswith("unsupported")

    def test_mint_masks_producible_and_deterministic(self):
        from pythia_consumer import mint, verify
        m1 = mint.data_coordinate_masks(b"hello")
        m2 = mint.data_coordinate_masks(b"hello")
        assert m1 == m2 and len(m1) == 11
        for m in m1:
            assert (m >> 25) == 0 and (m & 0b11) == 0 and (m & (m << 1)) == 0

    def test_minted_survives_wire_roundtrip(self):
        from pythia_consumer import mint, verify
        r = mint.mint_receipt(data=b"roundtrip", context_id="wire")
        assert verify.verify_receipt(json.loads(json.dumps(r)))["verdict"] == "pass"

    def test_mint_cli(self, capsys):
        from pythia_consumer import cli
        assert cli.main(["mint", "--context", "x", "--masks", ",".join(["4"] * 11)]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["token_hex"].startswith("ZECK-")


class TestOffers:
    def test_catalog_shape(self):
        from pythia_consumer import offers
        cat = offers.offer_catalog()
        assert cat["schema"] == "pythia.consumer.offers/1"
        names = {o["offer"] for o in cat["offers"]}
        assert {"pythia", "pythia-node", "pythia-node-large-memory",
                "pythia-companion", "pythia-studio"} == names
        states = {o["offer"]: o["state"] for o in cat["offers"]}
        assert states["pythia"] == "installed"
        assert states["pythia-companion"] == "served"
        assert states["pythia-studio"] == "not-productized"  # honest stub

    def test_offers_cli(self, capsys):
        from pythia_consumer import cli
        assert cli.main(["offers"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert len(out["offers"]) == 5


class TestMintRoute:
    def test_api_mint_and_offers(self):
        import threading, urllib.request
        from pythia_consumer.console import make_handler
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(None))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            req = urllib.request.Request(
                base + "/api/mint", method="POST",
                data=json.dumps({"context_id": "api", "data": "payload"}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                receipt = json.loads(r.read())
            from pythia_consumer import verify
            assert verify.verify_receipt(receipt)["verdict"] == "pass"
            with urllib.request.urlopen(base + "/api/offers", timeout=5) as r:
                assert json.loads(r.read())["schema"] == "pythia.consumer.offers/1"
        finally:
            srv.shutdown()
            srv.server_close()


class TestJsParity:
    """verify.js must produce verdicts identical to the Python contract.
    Runs the JS under macOS JXA (JavaScriptCore); skipped off-Darwin."""

    @pytest.fixture(autouse=True)
    def _need_jxa(self):
        if sys.platform != "darwin" or not shutil.which("osascript"):
            pytest.skip("JXA parity check requires macOS osascript")

    def _js_verdicts(self, cases):
        from pythia_consumer import verify as pyv
        verify_js = (COMPANION / "verify.js").read_text()
        case_texts = {n: json.dumps(r) for n, r in cases.items()}
        harness = verify_js + "\n" + f"""
const caseTexts = {json.dumps(case_texts)};
const out = {{}};
for (const [name, text] of Object.entries(caseTexts)) {{
  let r; try {{ r = PythiaVerify.parse_receipt(text); }} catch(e) {{ out[name] = {{parse_error: String(e)}}; continue; }}
  const v = PythiaVerify.verify_receipt(r);
  out[name] = {{checks: v.checks.map(c => [c.check, c.result]), verdict: v.verdict,
               verification_level: v.verification_level}};
}}
console.log(JSON.stringify(out));
"""
        with open("/tmp/pythia_jxa_parity.js", "w") as f:
            f.write(harness)
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", "/tmp/pythia_jxa_parity.js"],
            capture_output=True, text=True, timeout=120)
        raw = proc.stdout.strip() or proc.stderr.strip()
        assert proc.returncode == 0 and raw, proc.stderr[:400]
        return json.loads(raw.splitlines()[-1])

    def test_verdict_parity(self):
        from pythia_consumer import verify as pyv
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "zeckendorf_certificate.json").read_text())
        ctx = dict(fixture)
        ctx["context_id"] = "parity-ctx-∂"
        acc = pyv.canonical_accumulator(ctx["coordinate_masks"], ctx["context_id"])
        ctx["canonical_int"] = acc
        ctx["token_hex"] = f"ZECK-{acc:016X}"
        ctx.pop("token", None)
        cases = {
            "genuine": fixture,
            "utf8_context": ctx,
            "max_canonical": dict(fixture, canonical_int=18446744073709551615,
                                  token_hex="ZECK-FFFFFFFFFFFFFFFF"),
            "tampered": dict(fixture, token_hex="ZECK-0000000000000000"),
            "shape": {"non_adjacent_mask": 3},
            "big_zeck": dict(fixture, zeckendorf_indices=pyv.zeckendorf(7639424778862807),
                             zeckendorf_value=7639424778862807),
        }
        js = self._js_verdicts(cases)
        for name, r in cases.items():
            pv = pyv.verify_receipt(r)
            expected = {"checks": [[c["check"], c["result"]] for c in pv["checks"]],
                        "verdict": pv["verdict"],
                        "verification_level": pv["verification_level"]}
            assert js.get(name) == expected, f"JS/Python verdict drift on {name}"

    def test_mint_parity(self):
        """JS mint must produce fold-identical receipts to Python mint."""
        from pythia_consumer import mint as pym, verify as pyv
        verify_js = (COMPANION / "verify.js").read_text()
        cases = {"empty": {}, "ctx": {"context_id": "ctx-∂"},
                 "data": {"data": "hello-world", "context_id": "d"}}
        harness = verify_js + "\n" + f"""
const cases = {json.dumps(cases)};
const out = {{}};
for (const [name, kw] of Object.entries(cases)) {{
  const r = PythiaVerify.mint_receipt(kw);
  const text = PythiaVerify.receipt_json(r);
  const parsed = PythiaVerify.parse_receipt(text);   // JS-side roundtrip
  const v = PythiaVerify.verify_receipt(parsed);
  out[name] = {{text, verdict: v.verdict}};
}}
console.log(JSON.stringify(out));
"""
        with open("/tmp/pythia_jxa_mint.js", "w") as f:
            f.write(harness)
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", "/tmp/pythia_jxa_mint.js"],
            capture_output=True, text=True, timeout=120)
        raw = proc.stdout.strip() or proc.stderr.strip()
        assert proc.returncode == 0 and raw, proc.stderr[:400]
        js = json.loads(raw.splitlines()[-1])
        for name, kw in cases.items():
            args = dict(kw)
            if "data" in args:
                args["data"] = args["data"].encode()
            pyr = pym.mint_receipt(**args)
            jsr = json.loads(js[name]["text"])  # wire text parses as bare int
            assert jsr["canonical_int"] == pyr["canonical_int"], name
            assert jsr["token_hex"] == pyr["token_hex"], name
            assert jsr["coordinate_masks"] == pyr["coordinate_masks"], name
            assert jsr["non_adjacent_mask"] == pyr["non_adjacent_mask"], name
            assert js[name]["verdict"] == "pass", name
            assert pyv.verify_receipt(jsr)["verdict"] == "pass", name
