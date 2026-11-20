"""Controlled receipts test the software contract; not customer or deployment evidence."""
from dataclasses import asdict
from hashlib import sha256

import pytest

from chronus.accounting.bookings import Rider, canonical, cash_movements, replay, settlement, unit_economics

pytestmark = pytest.mark.simulated  # The fixture supplies an in-memory receipt reader.


@pytest.fixture
def scenario():
    data = {}
    tenant = "test-tenant"
    tranche = "test-tranche"

    def put(purpose, **fields):
        raw = canonical({"tenant_id": tenant, "purpose": purpose, **fields})
        digest = sha256(raw).hexdigest()
        data[digest] = raw
        return digest

    def read(scope, digest, purpose):
        assert scope == tenant
        return data[digest]

    rider = Rider("2026-01-01", "USD", 550000, 100, 1, "test-index", "base")
    contract = put("contract", tranche_id=tranche, rider=asdict(rider), dispute_days=10)
    source = put("measurement_input", kind="controlled_test_only")
    measurement = put("measurement", tranche_id=tranche, contract_digest=contract,
                      ipmvp_option="C", index_source="test-index", index_vintage="v1",
                      measurement_boundary="test storage", baseline_start="2025-10-01",
                      baseline_end="2025-12-31", reporting_start="2026-01-01",
                      reporting_end="2026-01-31", adjustment_minor=0, gb_num=1,
                      gb_den=1, index_num=1, index_den=1, actual_minor=0,
                      incremental_minor=0, input_digests=[source])
    # Index ratio 100/100 is used below; replace the measurement above
    # by the corresponding canonical receipt, without altering its bytes.
    raw = __import__("json").loads(data[measurement])
    raw["index_num"] = 100
    raw.pop("purpose")
    raw.pop("tenant_id")
    measurement = put("measurement", **raw)
    acceptance = put("acceptance", tranche_id=tranche, measurement_digest=measurement,
                     dispute_resolved=True, index_vintage="v1", date="2026-02-01")

    def event(kind, amount, day, **extra):
        return put("accounting_event", tranche_id=tranche, measurement_digest=measurement,
                   kind=kind, amount_minor=amount, date=day, **extra)

    def book(*events):
        return replay(tenant, tranche, contract, measurement, events, read)

    return dict(data=data, put=put, read=read, rider=rider, contract=contract,
                measurement=measurement, acceptance=acceptance, event=event, book=book)


def test_rider_exact_and_no_savings(scenario):
    r = scenario["rider"]
    assert r.cost(gb_num=1, gb_den=3, index_num=150, index_den=1) == 275000
    m = __import__("json").loads(scenario["data"][scenario["measurement"]])
    assert settlement(r, m) == {"counterfactual_minor": 550000, "net_minor": 550000,
                                "fee_minor": 137500, "client_retained_minor": 412500,
                                "currency": "USD"}
    m["actual_minor"] = 600000
    assert settlement(r, m)["fee_minor"] == 0
    m["ipmvp_option"] = "D"
    with pytest.raises(ValueError):
        settlement(r, m)


def test_invoice_acceptance_and_collection(scenario):
    e, b, a = scenario["event"], scenario["book"], scenario["acceptance"]
    i = e("invoice", 137500, "2026-02-01")
    c = e("acceptance", 137500, "2026-02-11", acceptance_digest=a, index_vintage="v1")
    p = e("collection", 137500, "2026-02-12")
    ledger = b(i, c, p)
    assert [(x.debit, x.credit, x.amount_minor) for x in ledger] == [
        ("Receivable", "DeferredRevenue", 137500),
        ("DeferredRevenue", "Revenue", 137500),
        ("Cash", "Receivable", 137500)]
    assert ledger == b(i, c, p)
    assert cash_movements(ledger) == (ledger[-1],)


def test_prepaid_acceptance_before_invoice(scenario):
    e, b, a = scenario["event"], scenario["book"], scenario["acceptance"]
    d = e("advance", 50000, "2026-01-01")
    c = e("acceptance", 137500, "2026-02-11", acceptance_digest=a, index_vintage="v1")
    i = e("invoice", 137500, "2026-02-12")
    p = e("collection", 87500, "2026-02-13")
    ledger = b(d, c, i, p)
    assert [(x.debit, x.credit, x.amount_minor) for x in ledger] == [
        ("Cash", "CustomerAdvances", 50000),
        ("CustomerAdvances", "Revenue", 50000),
        ("ContractAsset", "Revenue", 87500),
        ("Receivable", "ContractAsset", 87500),
        ("Cash", "Receivable", 87500)]
    assert sum(x.amount_minor for x in ledger if x.credit == "Revenue") == 137500
    assert sum(x.amount_minor for x in cash_movements(ledger)) == 137500


@pytest.mark.parametrize("bad", ["early", "vintage", "duplicate", "amount", "overpay", "missing_grid"])
def test_fail_closed(scenario, bad):
    e, b, a = scenario["event"], scenario["book"], scenario["acceptance"]
    i = e("invoice", 137500, "2026-02-01")
    c = e("acceptance", 137500, "2026-02-11", acceptance_digest=a, index_vintage="v1")
    rows = {
        "early": (i, e("acceptance", 137500, "2026-02-10", acceptance_digest=a, index_vintage="v1")),
        "vintage": (i, e("acceptance", 137500, "2026-02-11", acceptance_digest=a, index_vintage="v2")),
        "duplicate": (i, i),
        "amount": (e("invoice", 137501, "2026-02-01"),),
        "overpay": (i, c, e("collection", 137501, "2026-02-12")),
        "missing_grid": (i, c, e("grid_credit", 100, "2026-02-12", provider_digest="f"*64)),
    }
    with pytest.raises((ValueError, KeyError)):
        b(*rows[bad])


def test_provider_credit_and_cash_identity(scenario):
    e, b, a, put = (scenario[k] for k in ("event", "book", "acceptance", "put"))
    proof = put("grid_provider", tranche_id="test-tranche", measurement_digest=scenario["measurement"],
                amount_minor=100, certified=True, interruptible=True, portable=True)
    i = e("invoice", 137500, "2026-02-01")
    c = e("acceptance", 137500, "2026-02-11", acceptance_digest=a, index_vintage="v1")
    g = e("grid_credit", 100, "2026-02-12", provider_digest=proof)
    p = e("collection", 137400, "2026-02-13")
    ledger = b(i, c, g, p)
    assert (ledger[-2].debit, ledger[-2].credit, ledger[-2].amount_minor) == ("ContraRevenue", "Receivable", 100)
    assert cash_movements(ledger) == (ledger[-1],)


def test_digest_tampering_rejected(scenario):
    digest = scenario["contract"]
    scenario["data"][digest] += b" "
    with pytest.raises(ValueError, match="digest"):
        scenario["book"]()


def test_economics():
    r = unit_economics(revenue_minor=100, infra_minor=20, support_minor=10, qc_minor=5)
    assert r == {"gross_margin_minor": 65, "margin_fraction": "13/20"}
    assert unit_economics(revenue_minor=0, infra_minor=1, support_minor=0, qc_minor=0)["margin_fraction"] is None
