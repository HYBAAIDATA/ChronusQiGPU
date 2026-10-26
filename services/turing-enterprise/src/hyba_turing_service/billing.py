"""Authenticated Hermitten port. Wire schema requires receiver conformance.

No price/rate/invoice is fabricated locally. Deployment must confirm the endpoint
contract with the real billing owner before enabling this integration.
"""

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .control import Unavailable, canonical


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Unavailable("billing redirects are forbidden")


class HermittenClient:
    def __init__(
        self, base_url, bearer, *, import_path="/v1/usage/import", timeout=10, opener=None
    ):
        p = urllib.parse.urlsplit(base_url)
        if (
            p.scheme != "https"
            or not p.hostname
            or p.username
            or p.password
            or p.query
            or p.fragment
        ):
            raise ValueError("trusted HTTPS billing endpoint required")
        if not bearer or "\n" in bearer or "\r" in bearer:
            raise ValueError("billing credential required")
        if not import_path.startswith("/") or import_path.startswith("//") or ".." in import_path:
            raise ValueError("invalid import path")
        if not 1 <= timeout <= 60:
            raise ValueError("invalid timeout")
        self.base = base_url.rstrip("/")
        self.bearer = bearer
        self.path = import_path
        self.timeout = timeout
        self.opener = opener or urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
        )

    def _call(self, method, path, payload=None, key=None):
        headers = {"Authorization": "Bearer " + self.bearer, "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
        request = urllib.request.Request(
            self.base + path,
            data=canonical(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status < 200 or response.status >= 300:
                    raise Unavailable("billing request rejected")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise Unavailable("billing response too large")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise Unavailable("billing response is not an object")
                return value
        except (urllib.error.URLError, ValueError, OSError):
            raise Unavailable("billing transport unavailable or invalid") from None

    def capabilities(self):
        value = self._call("GET", "/v1/capabilities")
        if value.get(
            "atomic_event_deduplication"
        ) is not True or "turing.usage.v1" not in value.get("schemas", []):
            raise Unavailable("billing receiver contract not confirmed")
        return value

    def accept_usage(self, event, *, idempotency_key):
        supported = self.capabilities().get("schemas", [])
        if event.get("schema") not in supported:
            raise Unavailable("billing event schema unsupported")
        return self._call("POST", self.path, event, idempotency_key)

    def account(self, billing_account):
        result = self._call(
            "GET", "/v1/accounts/" + urllib.parse.quote(billing_account, safe="") + "/statement"
        )
        if result.get("account_id") != billing_account:
            raise Unavailable("billing statement account mismatch")
        return result


def deliver_commercial(plane, token, actor, sink, limit=100):
    plane._authorize(token, actor, "__service_ops__", "turing.ops.billing", operator=True)
    if sink is None:
        raise Unavailable("billing integration not configured")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("invalid delivery limit")
    delivered = 0
    for row in plane.db.execute(
        "SELECT * FROM commercial_events WHERE receipt IS NULL ORDER BY rowid LIMIT ?", (limit,)
    ).fetchall():
        event = json.loads(row["payload"])
        receipt = sink.accept_usage(event, idempotency_key=row["event"])
        if (
            not isinstance(receipt, dict)
            or receipt.get("event_id") != row["event"]
            or not isinstance(receipt.get("receipt_id"), str)
            or not receipt["receipt_id"]
        ):
            raise Unavailable("billing acknowledgement mismatch")
        with plane._transaction():
            changed = plane.db.execute(
                "UPDATE commercial_events SET receipt=? WHERE event=? AND receipt IS NULL",
                (canonical(receipt), row["event"]),
            ).rowcount
            if changed:
                plane._audit(row["tenant"], actor, "commercial_import_ack", receipt)
                delivered += 1
    return delivered


def set_spend_limit(client, account, *, amount, currency, command):
    from decimal import Decimal, InvalidOperation

    if not isinstance(amount, str) or not amount or len(amount) > 40:
        raise ValueError("monetary ceiling must be a decimal string")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount):
        raise ValueError("plain nonnegative decimal required")
    try:
        value = Decimal(amount)
        if not value.is_finite() or value < 0 or len(str(amount)) > 40:
            raise ValueError()
    except (InvalidOperation, TypeError):
        raise ValueError("invalid monetary ceiling") from None
    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or not re.fullmatch(r"[A-Z]{3}", currency)
        or currency.upper() != currency
    ):
        raise ValueError("ISO currency required")
    capabilities = client.capabilities()
    if capabilities.get("spend_authorisation") is not True:
        raise Unavailable("billing spend authority unsupported")
    if (
        not isinstance(command, str)
        or not 1 <= len(command) <= 256
        or "\n" in command
        or "\r" in command
    ):
        raise ValueError("idempotency command required")
    result = client._call(
        "PUT",
        "/v1/accounts/" + urllib.parse.quote(account, safe="") + "/spend-limit",
        dict(amount=str(value), currency=currency),
        command,
    )
    if result.get("account_id") != account:
        raise Unavailable("spend ceiling account mismatch")
    return result


def authorize_spend(client, account, *, job_key, request_digest):
    import time

    if client is None or client.capabilities().get("spend_authorisation") is not True:
        raise Unavailable("billing spend authority unavailable")
    result = client._call(
        "POST",
        "/v1/accounts/" + urllib.parse.quote(account, safe="") + "/work-authorisations",
        dict(job_key=job_key, request_digest=request_digest),
        job_key,
    )
    if (
        result.get("account_id") != account
        or result.get("job_key") != job_key
        or result.get("request_digest") != request_digest
        or not isinstance(result.get("authorization_id"), str)
        or not result["authorization_id"]
        or type(result.get("expires_at")) is not int
        or result["expires_at"] <= time.time()
    ):
        raise Unavailable("spend authorisation identity or expiry mismatch")
    if result.get("approved") is not True:
        from .control import Denied

        raise Denied("commercial expenditure limit reached")
    return result
