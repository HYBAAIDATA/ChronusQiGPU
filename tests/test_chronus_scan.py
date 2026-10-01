from aethel.device import ChronusSku
from chronus.seam.workflow import share_meets_target, sha256d


def test_sku_scan_finds_easy_target():
    header76 = b"\x00" * 76
    digest0 = sha256d(header76 + (0).to_bytes(4, "little"))
    target = int.from_bytes(digest0[::-1], "big")
    sku = ChronusSku("standalone")
    nonce = sku.scan_nonce(header76, target, 8)
    assert nonce == 0
    assert share_meets_target(digest0, target)


def test_sku_scan_empty_window():
    sku = ChronusSku("standalone")
    assert sku.scan_nonce(b"\x00" * 76, 1, 0) is None
