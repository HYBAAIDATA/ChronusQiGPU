"""Exact CIaaS settlement recomputation and receipt-derived accounting.

No issuance, custody, signature or qualification authority is granted here.
The application must supply its AL HARAS/THESEUS admission-and-read boundary.
The existing CIaaS preview remains non-authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from hashlib import sha256
import json
import re
from typing import Callable

DigestReader = Callable[[str, str, str], bytes]
_DIGEST = re.compile(r"[0-9a-f]{64}")


def integer(value: int) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer minor units required")
    return value


def positive(value: int) -> int:
    if integer(value) == 0:
        raise ValueError("positive integer required")
    return value


def text(value: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("nonempty identifier required")
    return value


def iso(value: str) -> date:
    parsed = date.fromisoformat(text(value))
    if parsed.isoformat() != value:
        raise ValueError("canonical ISO date required")
    return parsed


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read_admitted(reader: DigestReader, tenant: str, digest: str, purpose: str) -> dict:
    """Reader must independently authenticate and admit bytes for tenant/purpose.

    A digest match proves byte integrity, not signer authority.
    """
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValueError("full SHA-256 required")
    raw = reader(text(tenant), digest, text(purpose))
    if not isinstance(raw, bytes) or sha256(raw).hexdigest() != digest:
        raise ValueError("receipt bytes do not match digest")
    result = json.loads(raw)
    if type(result) is not dict or canonical(result) != raw:
        raise ValueError("canonical admitted receipt required")
    if result.get("tenant_id") != tenant or result.get("purpose") != purpose:
        raise ValueError("receipt scope mismatch")
    return result


@dataclass(frozen=True)
class Rider:
    contract_epoch: str
    currency: str
    base_minor_per_gb: int
    base_index_num: int
    base_index_den: int
    index_source: str
    base_vintage: str

    def __post_init__(self):
        iso(self.contract_epoch)
        if not re.fullmatch(r"[A-Z]{3}", text(self.currency)):
            raise ValueError("ISO currency code required")
        integer(self.base_minor_per_gb)
        positive(self.base_index_num)
        positive(self.base_index_den)
        text(self.index_source)
        text(self.base_vintage)

    def cost(self, *, gb_num: int, gb_den: int, index_num: int, index_den: int) -> int:
        value = (Fraction(self.base_minor_per_gb) * Fraction(integer(gb_num), positive(gb_den))
                 * Fraction(positive(index_num), positive(index_den))
                 / Fraction(self.base_index_num, self.base_index_den))
        return round(value)  # exact, half-even at the minor-unit boundary


def settlement(contract: Rider, measurement: dict) -> dict:
    """Option C calculation; Option D requires a separate calibrated contract."""
    if measurement["ipmvp_option"] != "C":
        raise ValueError("only admitted Option C measurement is supported")
    if measurement["index_source"] != contract.index_source:
        raise ValueError("index source differs from frozen contract")
    text(measurement["index_vintage"])
    text(measurement["measurement_boundary"])
    start, end = iso(measurement["reporting_start"]), iso(measurement["reporting_end"])
    baseline_start, baseline_end = iso(measurement["baseline_start"]), iso(measurement["baseline_end"])
    if not baseline_start <= baseline_end < start <= end or start < iso(contract.contract_epoch):
        raise ValueError("invalid baseline or reporting period")
    adjusted = measurement["adjustment_minor"]
    if type(adjusted) is not int:
        raise ValueError("exact signed adjustment minor units required")
    cf = contract.cost(gb_num=measurement["gb_num"], gb_den=measurement["gb_den"],
                       index_num=measurement["index_num"], index_den=measurement["index_den"])
    cf += adjusted
    integer(cf)
    net = max(0, cf - integer(measurement["actual_minor"]) - integer(measurement["incremental_minor"]))
    fee = net // 4  # matches existing CIaaS floor policy
    return {"counterfactual_minor": cf, "net_minor": net, "fee_minor": fee,
            "client_retained_minor": net - fee, "currency": contract.currency}


@dataclass(frozen=True)
class Posting:
    tenant: str
    tranche: str
    currency: str
    event_digest: str
    measurement_digest: str
    ipmvp_option: str
    index_vintage: str
    event_date: str
    debit: str
    credit: str
    amount_minor: int


def replay(tenant: str, tranche: str, contract_digest: str, measurement_digest: str,
           events: tuple[str, ...], reader: DigestReader) -> tuple[Posting, ...]:
    """Deterministic subledger replay of admitted, tenant-bound events.

    Reject duplicates and inconsistent order; never post from a preview.
    Cash is recognized only on an admitted collection or advance event.
    """
    c = read_admitted(reader, tenant, contract_digest, "contract")
    m = read_admitted(reader, tenant, measurement_digest, "measurement")
    if c["tranche_id"] != tranche or m["tranche_id"] != tranche or m["contract_digest"] != contract_digest:
        raise ValueError("contract/measurement/tranche mismatch")
    for ref in m["input_digests"]:
        read_admitted(reader, tenant, ref, "measurement_input")
    if not m["input_digests"]:
        raise ValueError("measurement inputs required")
    contract = Rider(**c["rider"])
    fee = settlement(contract, m)["fee_minor"]
    dispute_days = integer(c["dispute_days"])
    posts = []
    seen = set()
    prior = iso(contract.contract_epoch)
    invoiced = recognized = paid = credits = advance = 0
    invoice_seen = acceptance_seen = False

    def post(digest, when, dr, cr, amount):
        if integer(amount):
            posts.append(Posting(tenant, tranche, contract.currency, digest, measurement_digest,
                                 "C", m["index_vintage"], when, dr, cr, amount))

    for digest in events:
        if digest in seen:
            raise ValueError("duplicate event")
        seen.add(digest)
        e = read_admitted(reader, tenant, digest, "accounting_event")
        if e["tranche_id"] != tranche or e["measurement_digest"] != measurement_digest:
            raise ValueError("event scope mismatch")
        when = e["date"]
        day = iso(when)
        if day < prior:
            raise ValueError("events out of chronological order")
        prior = day
        kind, amount = e["kind"], integer(e["amount_minor"])
        if kind == "advance":
            if paid + advance + amount > fee - credits or invoice_seen:
                raise ValueError("invalid advance")
            post(digest, when, "Cash", "CustomerAdvances", amount)
            advance += amount
        elif kind == "invoice":
            if invoice_seen or amount != fee:
                raise ValueError("invoice must match recomputed fee exactly once")
            invoice_seen = True
            invoiced = amount
            post(digest, when, "Receivable", "ContractAsset" if acceptance_seen else "DeferredRevenue", amount)
            post(digest, when, "CustomerAdvances", "Receivable", advance)
            paid += advance
            advance = 0
        elif kind == "acceptance":
            if acceptance_seen or amount != fee or e.get("index_vintage") != m["index_vintage"]:
                raise ValueError("invalid recognition event")
            accepted = read_admitted(reader, tenant, e["acceptance_digest"], "acceptance")
            if (accepted["measurement_digest"] != measurement_digest
                    or accepted["tranche_id"] != tranche or accepted["dispute_resolved"] is not True
                    or accepted["index_vintage"] != m["index_vintage"]
                    or iso(accepted["date"]) < iso(m["reporting_end"])
                    or (day - iso(accepted["date"])).days < dispute_days):
                raise ValueError("acceptance, dispute or index constraint not satisfied")
            acceptance_seen = True
            recognized = amount
            post(digest, when, "DeferredRevenue" if invoice_seen else "ContractAsset",
                 "Revenue", amount)
        elif kind == "collection":
            if not invoice_seen or amount > invoiced - paid - credits:
                raise ValueError("collection exceeds open receivable")
            paid += amount
            post(digest, when, "Cash", "Receivable", amount)
        elif kind == "grid_credit":
            if not invoice_seen or not acceptance_seen or amount > invoiced - paid - credits:
                raise ValueError("credit exceeds recognized open receivable")
            proof = read_admitted(reader, tenant, e["provider_digest"], "grid_provider")
            if (proof["measurement_digest"] != measurement_digest
                    or proof["tranche_id"] != tranche
                    or proof["amount_minor"] != amount or proof["certified"] is not True
                    or proof["interruptible"] is not True or proof["portable"] is not True):
                raise ValueError("grid provider proof or enrolled class missing")
            credits += amount
            post(digest, when, "ContraRevenue", "Receivable", amount)
        else:
            raise ValueError("unsupported accounting event")
    return tuple(posts)


def cash_movements(postings: tuple[Posting, ...]) -> tuple[Posting, ...]:
    """Cash movement view, not a jurisdiction-specific tax return."""
    return tuple(p for p in postings if "Cash" in (p.debit, p.credit))


def unit_economics(*, revenue_minor: int, infra_minor: int, support_minor: int, qc_minor: int) -> dict:
    revenue = integer(revenue_minor)
    cost = sum(integer(i) for i in (infra_minor, support_minor, qc_minor))
    margin = revenue - cost
    return {"gross_margin_minor": margin,
            "margin_fraction": str(Fraction(margin, revenue)) if revenue else None}
