# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Scale grants, tier selections and scale events: the authorised path to scale.

A scale grant is the coordinator owner's signed authorisation to scale the
fleet to a named tier (2, 3 or 4) or to a Scale contract figure, until an
expiry. It is signed with ML-DSA-65 by the coordinator's own key (the
existing v36 signer, ``chronus.fleet.signing``) and verified against that key
before it counts; a grant from any other key, for another fleet, altered
after signing or past its expiry is rejected.

A tier selection is the owner's signed instruction to move the fleet to a
tier: downward at any time, upward only as far as a valid grant authorises.

A scale event records demand that went beyond the current tier's
entitlement: the demand, the entitlement, the next tier, the time and what
happened (admitted under a grant, or queued with "scale available: Tier N+1").

Grant and selection files live in ``<state_dir>/tier/``; ``chronus-fleet tier
grant`` and ``chronus-fleet tier set`` write them on the coordinator and the
coordinator applies them on its next fabric tick.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from chronus.fleet.canonical import canonical_json, iso_utc, utc_now_ns
from chronus.fleet.errors import ScaleGrantRejected
from chronus.fleet.phase import SCALE_TIER_NUMBER, TIER_1, TIER_4, Tier, scale_tier, tier_by_number
from chronus.fleet.signing import FleetSigner, key_id, verify_signature

GRANT_SCHEMA = "chronus.fleet.scale-grant/v1"
SELECTION_SCHEMA = "chronus.fleet.tier-selection/v1"
TIER_DIRNAME = "tier"
SCALE = "scale"
_DURATION = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86_400, "w": 604_800}


def parse_duration(text: str) -> int:
    """Seconds in "30d", "12h", "90m", "3600s" or "2w"."""
    match = _DURATION.match(str(text).lower())
    if not match or int(match.group(1)) < 1:
        raise ScaleGrantRejected(f"expiry {text!r} must look like 30d, 12h, 90m or 2w")
    return int(match.group(1)) * _UNIT_SECONDS[match.group(2)]


def parse_tier(value: Any) -> int:
    """Tier number from 1 to 4, or 5 for "scale"."""
    if isinstance(value, str) and value.strip().lower() == SCALE:
        return SCALE_TIER_NUMBER
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ScaleGrantRejected(f"tier {value!r} must be 1, 2, 3, 4 or scale") from None
    if not TIER_1.number <= number <= SCALE_TIER_NUMBER:
        raise ScaleGrantRejected(f"tier {value!r} must be 1, 2, 3, 4 or scale")
    return number


def _sign(signer: FleetSigner, body: Mapping[str, Any]) -> dict[str, Any]:
    document = dict(body)
    document["signature"] = {"algorithm": "ML-DSA-65", "key_id": signer.key_id, "value": signer.sign(canonical_json(body))}
    return document


def _verified_body(document: Mapping[str, Any], schema: str, public_key: bytes, fleet_id: str) -> dict[str, Any]:
    if not isinstance(document, Mapping) or document.get("schema") != schema:
        raise ScaleGrantRejected(f"not a {schema} document")
    signature = document.get("signature")
    if not isinstance(signature, Mapping) or not isinstance(signature.get("value"), str):
        raise ScaleGrantRejected("document is not signed")
    body = {k: v for k, v in document.items() if k != "signature"}
    if signature.get("key_id") != key_id(public_key):
        raise ScaleGrantRejected("signed by a key other than the coordinator owner's")
    try:
        valid = verify_signature(public_key, canonical_json(body), signature["value"])
    except Exception:
        valid = False
    if not valid:
        raise ScaleGrantRejected("ML-DSA-65 signature does not verify against the coordinator owner's key")
    if body.get("fleet_id") != fleet_id:
        raise ScaleGrantRejected("document was issued for another fleet")
    return body


@dataclass(frozen=True)
class ScaleGrant:
    grant_id: str
    fleet_id: str
    tier_number: int
    warps: int
    storage_tb: int
    contract: str | None
    issued_at_ns: int
    expires_at_ns: int
    key_id: str

    @property
    def tier(self) -> Tier:
        if self.tier_number == SCALE_TIER_NUMBER:
            return scale_tier(self.warps, self.storage_tb, self.contract or "")
        return tier_by_number(self.tier_number)

    def valid_at(self, now_ns: int | None = None) -> bool:
        now = utc_now_ns() if now_ns is None else now_ns
        return self.issued_at_ns <= now < self.expires_at_ns

    def to_dict(self, now_ns: int | None = None) -> dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "tier": self.tier.label,
            "warps": self.warps,
            "storage_tb": self.storage_tb,
            "contract": self.contract,
            "issued_at": iso_utc(self.issued_at_ns),
            "expires_at": iso_utc(self.expires_at_ns),
            "valid": self.valid_at(now_ns),
            "key_id": self.key_id,
        }


def issue_grant(
    signer: FleetSigner,
    fleet_id: str,
    tier: Any,
    expires_in_s: int,
    *,
    warps: int | None = None,
    storage_tb: int | None = None,
    contract: str | None = None,
    now_ns: int | None = None,
) -> dict[str, Any]:
    """A signed grant to a tier (2 to 4) or to a Scale contract figure (explicit warps and TB)."""
    number = parse_tier(tier)
    if number == TIER_1.number:
        raise ScaleGrantRejected("Tier 1 needs no grant")
    if number == SCALE_TIER_NUMBER:
        if warps is None or storage_tb is None or not contract:
            raise ScaleGrantRejected("a Scale grant needs --warps, --storage-tb and --contract (the contract figure)")
        try:
            target = scale_tier(warps, storage_tb, contract)
        except ValueError as exc:
            raise ScaleGrantRejected(str(exc)) from exc
    else:
        target = tier_by_number(number)
    if not isinstance(expires_in_s, int) or expires_in_s < 1:
        raise ScaleGrantRejected("a grant needs an expiry in the future")
    issued = utc_now_ns() if now_ns is None else now_ns
    body = {
        "schema": GRANT_SCHEMA,
        "grant_id": "grant-" + secrets.token_hex(8),
        "fleet_id": fleet_id,
        "tier": target.number,
        "tier_label": target.label,
        "warps": target.warps,
        "storage_tb": target.storage_tb,
        "contract": target.contract,
        "issued_at_ns": issued,
        "issued_at": iso_utc(issued),
        "expires_at_ns": issued + expires_in_s * 1_000_000_000,
        "expires_at": iso_utc(issued + expires_in_s * 1_000_000_000),
    }
    return _sign(signer, body)


def verify_grant(document: Mapping[str, Any], public_key: bytes, fleet_id: str) -> ScaleGrant:
    """The grant, once its signature, fleet and figures check out (expiry is checked when used)."""
    body = _verified_body(document, GRANT_SCHEMA, public_key, fleet_id)
    try:
        grant = ScaleGrant(
            grant_id=str(body["grant_id"]),
            fleet_id=str(body["fleet_id"]),
            tier_number=parse_tier(body["tier"]),
            warps=int(body["warps"]),
            storage_tb=int(body["storage_tb"]),
            contract=body.get("contract"),
            issued_at_ns=int(body["issued_at_ns"]),
            expires_at_ns=int(body["expires_at_ns"]),
            key_id=key_id(public_key),
        )
        tier = grant.tier
    except (KeyError, TypeError, ValueError) as exc:
        raise ScaleGrantRejected(f"grant is malformed: {exc}") from exc
    if grant.tier_number == TIER_1.number:
        raise ScaleGrantRejected("Tier 1 needs no grant")
    if grant.tier_number <= TIER_4.number and (tier.warps, tier.storage_tb) != (grant.warps, grant.storage_tb):
        raise ScaleGrantRejected(f"grant figures do not match {tier.label}")
    if grant.expires_at_ns <= grant.issued_at_ns:
        raise ScaleGrantRejected("grant expires before it is issued")
    return grant


def issue_selection(signer: FleetSigner, fleet_id: str, tier: Any, now_ns: int | None = None) -> dict[str, Any]:
    """A signed instruction to move the fleet to a tier (up only as far as a grant authorises)."""
    issued = utc_now_ns() if now_ns is None else now_ns
    body = {
        "schema": SELECTION_SCHEMA,
        "selection_id": "select-" + secrets.token_hex(8),
        "fleet_id": fleet_id,
        "tier": parse_tier(tier),
        "issued_at_ns": issued,
        "issued_at": iso_utc(issued),
    }
    return _sign(signer, body)


def verify_selection(document: Mapping[str, Any], public_key: bytes, fleet_id: str) -> dict[str, Any]:
    body = _verified_body(document, SELECTION_SCHEMA, public_key, fleet_id)
    body["tier"] = parse_tier(body.get("tier"))
    return body


def write_document(state_dir: str | Path, document: Mapping[str, Any]) -> Path:
    """Persist a grant or selection where the coordinator picks it up; read back to confirm."""
    directory = Path(state_dir).expanduser() / TIER_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    ident = document.get("grant_id") or document.get("selection_id")
    if not isinstance(ident, str) or not re.fullmatch(r"(grant|select)-[0-9a-f]{16}", ident):
        raise ScaleGrantRejected("document has no valid id")
    path = directory / f"{ident}.json"
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    if path.read_text(encoding="utf-8") != text:
        raise ScaleGrantRejected(f"{path} did not read back as written")
    return path


def read_documents(state_dir: str | Path) -> list[tuple[str, dict[str, Any]]]:
    """(file name, document) for every grant and selection, oldest first."""
    directory = Path(state_dir).expanduser() / TIER_DIRNAME
    if not directory.is_dir():
        return []
    found = []
    for path in directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(document, dict) and type(document.get("issued_at_ns")) is int:
            found.append((path.name, document))
    found.sort(key=lambda item: (item[1]["issued_at_ns"], item[0]))
    return found


@dataclass
class ScaleEvent:
    kind: str
    subject: str
    demand: dict[str, int]
    entitlement: dict[str, Any]
    next_tier: str
    outcome: str
    message: str
    grant_id: str | None = None
    event_id: str = field(default_factory=lambda: "scale-" + secrets.token_hex(6))
    recorded_at: str = field(default_factory=iso_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "subject": self.subject,
            "demand": dict(self.demand),
            "entitlement": dict(self.entitlement),
            "next_tier": self.next_tier,
            "outcome": self.outcome,
            "message": self.message,
            "grant_id": self.grant_id,
            "recorded_at": self.recorded_at,
        }
