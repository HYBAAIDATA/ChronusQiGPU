"""Archived marketing claims must remain blocked."""
import json
from pathlib import Path

from scripts.claim_gate import check


def test_archived_claims_still_block(tmp_path):
    root = Path(__file__).resolve().parents[1]
    register = root / "claims/register.json"
    archive = json.loads((root / "claims/archive_uncited/register.json").read_text())
    for claim in archive["claims"]:
        (tmp_path / "index.html").write_text(claim["text"])
        assert any(claim["code"] in problem for problem in check(tmp_path, register))


def test_archive_missing_fails_closed(tmp_path):
    from pytest import raises
    claims = tmp_path / "claims"
    claims.mkdir()
    register = claims / "register.json"
    register.write_text(json.dumps({"claims": [], "archive": "claims/archive_uncited/missing.json"}))
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("placeholder")
    with raises(OSError):
        check(site, register)


def test_held_claims_have_specific_reasons():
    root = Path(__file__).resolve().parents[1]
    claims = json.loads((root / "claims/archive_uncited/register.json").read_text())["claims"]
    assert len(claims) == 6
    assert all(c["state"] == "held" and c["why_held"].strip() for c in claims)
    assert len({c["why_held"] for c in claims}) == len(claims)
