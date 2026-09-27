"""The claim register matches the disposition report and covers every id once."""

from pathlib import Path

from toe.unified.claims import CLAIMS, STATUSES, render_disposition


ROOT = Path(__file__).resolve().parents[1]
DISPOSITION = ROOT / "reports" / "toe_unified_disposition.md"


def test_claim_table_covers_every_id():
    ids = [claim.id for claim in CLAIMS]
    assert ids == sorted(ids, key=lambda item: (item[0], int(item[1:])))
    assert len(ids) == len(set(ids))
    assert set(claim.status for claim in CLAIMS) <= set(STATUSES)
    for claim in CLAIMS:
        if claim.status == "UNSUPPORTED":
            assert claim.test == ""
        else:
            assert claim.test.startswith("tests/")


def test_disposition_matches_claim_table():
    assert DISPOSITION.read_text(encoding="utf-8") == render_disposition()
