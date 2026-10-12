"""Test-only strict-M3 provisioning, exactly as an operator admits a tenant.

Live submission is refused unless ``PYTHIA_M3_REQUIRED=1`` (AL HARAS
authorisation + THESEUS proof custody). Tests that exercise the submit path
must therefore stand up the *real* custody plane rather than bypass it:

* THESEUS/OVID storage under ``tmp`` with separate 32-byte integrity and
  custody keys (``PYTHIA_STORAGE_*``);
* one explicit tenant admission through ``scripts/provision_m3_tenant.py``
  (the operator's admission path — never self-registration on boot);
* an AL HARAS keyring with a durable audit directory and a subscription
  token minted by the canonical ``SubscriptionAuthority`` for exactly that
  tenant and actor.

Nothing here relaxes a guard: every check the miner performs at startup and
per submission still runs against these artefacts. The keys are fixed test
values and must never be used outside a temporary directory.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable

TENANT = "e2e-mining-tenant"
ACTOR = "e2e-operator"
_KEY_ID = "e2e"
_KEY = b"e" * 32
_ISSUER = "hyba-subscriptions"


def _mint_token() -> str:
    from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

    return SubscriptionAuthority({_KEY_ID: _KEY}, _ISSUER).issue(
        SubscriptionClaims(
            subscription_id="sub-e2e-mining",
            tenant_id=TENANT,
            issuer=_ISSUER,
            key_id=_KEY_ID,
            capabilities=("hyba.security",),
            actors=(ACTOR,),
            not_before=0,
            expires_at=int(time.time()) + 3600,
        )
    )


def strict_m3_environment(root: Path) -> dict[str, str]:
    """Environment variables for a strict-M3 miner rooted at ``root``."""
    root = Path(root)
    return {
        "PYTHIA_M3_REQUIRED": "1",
        "PYTHIA_STORAGE_DB": str(root / "m3" / "store.db"),
        "PYTHIA_STORAGE_ROOT": str(root / "m3" / "cas"),
        "PYTHIA_STORAGE_CUSTODY_ROOT": str(root / "m3" / "custody"),
        "PYTHIA_STORAGE_INTEGRITY_KEY_HEX": "ab" * 32,
        "PYTHIA_STORAGE_CUSTODY_KEY_HEX": "cd" * 32,
        "PYTHIA_STORAGE_TENANT": TENANT,
        "PYTHIA_M3_TENANT": TENANT,
        "PYTHIA_M3_ACTOR": ACTOR,
        "PYTHIA_M3_AL_HARAS_TOKEN": _mint_token(),
        "AL_HARAS_SUBSCRIPTION_KEYS": json.dumps({_KEY_ID: _KEY.decode()}),
        "AL_HARAS_DATA_DIR": str(root / "al-haras"),
        "AL_HARAS_ISSUER": _ISSUER,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def admit_tenant() -> str:
    """Run the operator admission for the tenant named in the environment."""
    # Load by path: several ``scripts`` packages exist on test sys.paths.
    import importlib.util

    path = _repo_root() / "scripts" / "provision_m3_tenant.py"
    spec = importlib.util.spec_from_file_location("_pythia_provision_m3_tenant", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision(tenant=TENANT, max_records=1_000_000, max_bytes=10**9, approved=True)


def _reset_guardian_cache() -> None:
    try:
        from al_haras_pythia import pythia_guardian_api
    except ImportError:  # pragma: no cover - platform module absent
        return
    pythia_guardian_api.cache_clear()


def provision_strict_m3(
    root: Path,
    setenv: Callable[[str, str], None] | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    """Set the strict-M3 environment, admit the tenant, return its tenant id.

    ``setenv`` defaults to ``os.environ.__setitem__``; pass
    ``monkeypatch.setenv`` from pytest so the environment is restored.
    """
    setter = setenv or os.environ.__setitem__
    for key, value in {**strict_m3_environment(root), **(overrides or {})}.items():
        setter(key, value)
    _reset_guardian_cache()
    return admit_tenant()


def strict_m3_child_env(root: Path) -> dict[str, str]:
    """Admit the tenant and return the strict-M3 variables for a subprocess.

    The admission reads ``os.environ``; it is applied only for the duration
    of the admission and then restored, so the caller's process environment
    is unchanged.
    """
    env = strict_m3_environment(root)
    saved = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    try:
        admit_tenant()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return env
