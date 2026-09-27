from aethel.hyperscaler import HyperscalerSku


def test_folded_form_is_working_form():
    sku = HyperscalerSku()
    raw = b"hyperscaler-fold-working-form-payload"
    rec = sku.put(raw, job_id="hs-1")
    assert rec.units >= 1
    assert rec.work_items > 0
    assert rec.merkle
    vec = sku.working(rec.address)
    assert vec.verify()
    assert all((m & (m << 1)) == 0 for m in sku.masks(rec.address))
    assert sku.egress(rec.address) == raw
    rec2 = sku.put(b"second")
    assert rec2.merkle != rec.merkle
