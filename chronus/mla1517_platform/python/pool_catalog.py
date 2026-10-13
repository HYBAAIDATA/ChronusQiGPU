"""The mining pools PYTHIA may use, and how each one is configured.

The control API's startup contract and the mining worker both resolve pools
here, so the identity the API reports is the one the worker mines with.

``domains`` identify a configured endpoint as belonging to a pool;
``default`` is used only when no endpoint is configured for it (NiceHash has
none: its stratum host must be set).

* ``PYTHIA_POOLS`` (default ``braiins,viabtc``) lists the pools in failover
  order; ``PYTHIA_POOL_PROFILE`` (or ``MLA1517_POOL_PROFILE``) moves one to
  the front as the primary.
* The primary takes the canonical ``MLA1517_STRATUM_USER`` / ``_PASSWORD`` /
  ``_ENDPOINT``, then its own ``MLA1517_<POOL>_*`` values.
* A failover pool takes its own ``MLA1517_<POOL>_*`` values, then the
  caller's fallback user and password.
* The password defaults to ``x``; the endpoint to the catalog default.
"""

from __future__ import annotations

import os
from typing import NamedTuple

POOL_CATALOG: dict[str, dict] = {
    "braiins": {"domains": ("braiins.com",), "default": "stratum.braiins.com:3333"},
    "viabtc": {"domains": ("viabtc.io", "viabtc.com"), "default": "btc.viabtc.io:3333"},
    "nicehash": {"domains": ("nicehash.com",), "default": None, "extranonce_subscribe": True},
    "ckpool": {"domains": ("ckpool.org",), "default": "solo.ckpool.org:3333"},
}

DEFAULT_STRATUM_PASSWORD = "x"


class PoolSettings(NamedTuple):
    name: str
    endpoint: str | None
    user: str | None
    password: str


def pool_names() -> list[str]:
    """Configured pools, primary first."""
    names = [n.strip().lower() for n in os.getenv("PYTHIA_POOLS", "braiins,viabtc").split(",")]
    names = [n for n in names if n]
    profile = (os.getenv("PYTHIA_POOL_PROFILE") or os.getenv("MLA1517_POOL_PROFILE") or "").strip()
    if profile:
        profile = profile.lower()
        if profile in names:
            names.remove(profile)
        names.insert(0, profile)
    return names


def pool_settings(
    name: str,
    *,
    primary: bool,
    fallback_user: str | None = None,
    fallback_password: str | None = None,
) -> PoolSettings:
    """Endpoint and credentials for one catalog pool, before validation."""
    if name not in POOL_CATALOG:
        raise KeyError(name)
    prefix = f"MLA1517_{name.upper()}"

    def configured(suffix: str) -> str | None:
        canonical = os.getenv(f"MLA1517_STRATUM_{suffix}") if primary else None
        value = (
            canonical
            or os.getenv(f"{prefix}_{suffix}")
            or os.getenv(f"{name.upper()}_{suffix}")
            or ""
        )
        if not value.strip():
            return None
        # Passwords are opaque; hosts and workers are not.
        return value if suffix == "PASSWORD" else value.strip()

    return PoolSettings(
        name=name,
        endpoint=configured("ENDPOINT") or POOL_CATALOG[name]["default"],
        user=configured("USER") or fallback_user or None,
        password=configured("PASSWORD") or fallback_password or DEFAULT_STRATUM_PASSWORD,
    )
