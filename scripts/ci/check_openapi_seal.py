#!/usr/bin/env python3
"""Seal the live OpenAPI document — not a hand-kept fragment.

Hard-fails if the sealed API app (``chronus.service.api.app``) carries a
banned mechanism token. Also seals the live capacity routes on both the
API app and the deploy app (``/v1/capacity/{pool,quote,reserve,admit}``).

The full deploy OpenAPI still contains legacy mechanism-labelled routes
(AL HARAS / Euclid / …). Scrubbing those is deferred; this gate does not
pretend they are clean.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

API_TOKENS = json.dumps(
    {
        "seal-check-token": {
            "tenant_id": "seal",
            "scopes": ["workloads:read", "workloads:write", "evidence:read"],
        }
    }
)
DEPLOY_TOKENS = json.dumps({"seal": "seal-check-token"})


def main() -> int:
    from chronus.core.seal import seal_schema
    from chronus.service.api.routers.procurement import capacity_openapi_fragment

    os.environ["CHRONUS_TENANT_TOKENS"] = API_TOKENS
    from chronus.service.api.app import create_app as create_api_app

    api_schema = create_api_app().openapi()
    seal_schema(api_schema, context="api_openapi")
    capacity_openapi_fragment(api_schema)
    print("api_openapi seal ok")

    os.environ["CHRONUS_TENANT_TOKENS"] = DEPLOY_TOKENS
    from chronus.service.app import create_app as create_deploy_app

    deploy_schema = create_deploy_app().openapi()
    capacity_openapi_fragment(deploy_schema)
    print("deploy_capacity_openapi seal ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
