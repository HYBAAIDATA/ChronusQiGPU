# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""HYBA Mine pool catalogue: ViaBTC, Braiins, NiceHash and ckpool only.

The four pools and their order are the owner's standing rule. Nothing outside
this catalogue can be configured, and no profile asks a pool for a lower share
difficulty: the password field carries the pool's own placeholder only.

Endpoints are the ones each pool publishes for Bitcoin Stratum V1 (checked on
11 November 2026, sources below). Profiles list endpoints in preference order;
with the default TLS policy ``prefer`` a pool's TLS endpoints are tried first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple

TLS_POLICIES = ("prefer", "require", "off")


@dataclass(frozen=True)
class PoolEndpoint:
    host: str
    port: int
    tls: bool

    def __post_init__(self) -> None:
        if not self.host or not isinstance(self.host, str):
            raise ValueError("endpoint host must be a non-empty string")
        if not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError("endpoint port must be in [1, 65535]")

    @property
    def url(self) -> str:
        return f"stratum+{'ssl' if self.tls else 'tcp'}://{self.host}:{self.port}"

    def to_dict(self) -> dict:
        return {"host": self.host, "port": self.port, "tls": self.tls, "url": self.url}


@dataclass(frozen=True)
class PoolProfile:
    pool_id: str
    name: str
    endpoints: Tuple[PoolEndpoint, ...]
    username_format: str
    username_example: str
    password_hint: str
    extranonce_subscribe: bool
    notes: str
    source: str

    def ordered_endpoints(self, tls_policy: str = "prefer") -> Tuple[PoolEndpoint, ...]:
        if tls_policy not in TLS_POLICIES:
            raise ValueError(f"tls policy must be one of {', '.join(TLS_POLICIES)}")
        if tls_policy == "require":
            chosen = tuple(e for e in self.endpoints if e.tls)
        elif tls_policy == "off":
            chosen = tuple(e for e in self.endpoints if not e.tls)
        else:
            # Prefer TLS without an implicit downgrade after a TLS failure.
            chosen = tuple(e for e in self.endpoints if e.tls)
            if not chosen:
                chosen = tuple(e for e in self.endpoints if not e.tls)
        if not chosen:
            raise ValueError(f"{self.name} publishes no endpoint for TLS policy '{tls_policy}'")
        return chosen

    def to_dict(self) -> dict:
        return {
            "pool_id": self.pool_id,
            "name": self.name,
            "endpoints": [e.to_dict() for e in self.endpoints],
            "username_format": self.username_format,
            "username_example": self.username_example,
            "password_hint": self.password_hint,
            "notes": self.notes,
            "source": self.source,
        }


POOL_CATALOG = {
    "viabtc": PoolProfile(
        pool_id="viabtc",
        name="ViaBTC",
        endpoints=(
            PoolEndpoint("btc-ssl.viabtc.io", 551, True),
            PoolEndpoint("btc.viabtc.io", 3333, False),
            PoolEndpoint("btc.viabtc.io", 443, False),
        ),
        username_format="<ViaBTC account or sub-account>.<worker>",
        username_example="hyba.macbook",
        password_hint="any value (ViaBTC ignores it; '123' is customary)",
        extranonce_subscribe=False,
        notes="PPS+/PPLNS pool; the SSL endpoint is btc-ssl.viabtc.io:551.",
        source="support.viabtc.com 'Mining Pools Information' (BTC), checked 2026-11-11",
    ),
    "braiins": PoolProfile(
        pool_id="braiins",
        name="Braiins Pool",
        endpoints=(
            PoolEndpoint("stratum.braiins.com", 3333, False),
            PoolEndpoint("stratum.braiins.com", 443, False),
        ),
        username_format="<Braiins username>.<worker>",
        username_example="hyba.imac",
        password_hint="anything (Braiins does not use it)",
        extranonce_subscribe=False,
        notes="FPPS pool; Stratum V1 is plain TCP (3333, backup 443).",
        source="academy.braiins.com/braiins-pool/quick-start, checked 2026-11-11",
    ),
    "nicehash": PoolProfile(
        pool_id="nicehash",
        name="NiceHash",
        endpoints=(
            PoolEndpoint("sha256asicboost.auto.nicehash.com", 443, True),
            PoolEndpoint("sha256asicboost.auto.nicehash.com", 9200, False),
        ),
        username_format="<NiceHash BTC mining address>.<worker>",
        username_example="bc1q...your-nicehash-mining-address.macbook",
        password_hint="x",
        extranonce_subscribe=True,
        notes="SHA256AsicBoost market; port 443 is TLS, 9200 is plain TCP.",
        source=(
            "NiceHash SHA256AsicBoost stratum host (TCP 9200, TLS 443) as reported in "
            "bitaxeorg/ESP-Miner issue #251; confirm in the NiceHash stratum generator. Checked 2026-11-11"
        ),
    ),
    "ckpool": PoolProfile(
        pool_id="ckpool",
        name="ckpool (solo.ckpool.org)",
        endpoints=(
            PoolEndpoint("solo.ckpool.org", 3333, False),
            PoolEndpoint("eusolo.ckpool.org", 3333, False),
            PoolEndpoint("stratum.ckpool.org", 3333, False),
        ),
        username_format="<your BTC address>.<worker>",
        username_example="bc1q...your-address.imac",
        password_hint="x (ignored)",
        extranonce_subscribe=False,
        notes="Solo pool: the reward goes to the address only when a block is found.",
        source=(
            "solo.ckpool.org welcome page as summarised by BitcoinWiki (stratum.ckpool.org:3333 main "
            "V1 endpoint) and the D-Central solo guide (solo.ckpool.org:3333). Checked 2026-11-11"
        ),
    ),
}

POOL_IDS = tuple(POOL_CATALOG)

_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_@+:-]*(\.[A-Za-z0-9][A-Za-z0-9_-]{0,63})$")


def get_pool(pool_id: str) -> PoolProfile:
    key = (pool_id or "").strip().lower()
    if key not in POOL_CATALOG:
        raise ValueError(
            f"unknown pool '{pool_id}'; HYBA Mine mines only on: {', '.join(POOL_IDS)}"
        )
    return POOL_CATALOG[key]


def validate_username(pool_id: str, username: str) -> None:
    """Check the shape of a pool login without revealing it in the error."""
    profile = get_pool(pool_id)
    if not isinstance(username, str) or not 3 <= len(username) <= 128:
        raise ValueError(f"{profile.name} username must be 3-128 characters: {profile.username_format}")
    if any(ch.isspace() for ch in username):
        raise ValueError(f"{profile.name} username must not contain spaces")
    if not _USERNAME.match(username):
        raise ValueError(
            f"{profile.name} username must look like {profile.username_format} "
            "(letters, digits, '_', '-', then '.' and a worker name)"
        )


def validate_password(password: str) -> None:
    if not isinstance(password, str) or not 1 <= len(password) <= 256:
        raise ValueError("pool password must be 1-256 characters (use the pool's placeholder)")
    if any(ch in password for ch in "\r\n\x00"):
        raise ValueError("pool password must not contain line breaks or NUL")
