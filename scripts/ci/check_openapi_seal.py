#!/usr/bin/env python3
"""Seal the live OpenAPI document — not a hand-kept fragment.

Hard-fails if the sealed API app (``chronus.service.api.app``) carries a
banned mechanism token. Also seals the procurement route fragment and the
deploy app's ``/v1/capacity/{pool,quote,reserve,admit}`` paths only.

The full deploy OpenAPI still contains legacy mechanism-labelled routes
(AL HARAS / Euclid / …). Scrubbing those is deferred to the migration
target; this gate does not pretend they are clean.
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

CAPACITY_PATHS = (
    "/v1/capacity/pool",
    "/v1/capacity/quote",
    "/v1/capacity/reserve",
    "/v1/capacity/admit",
)


def main() -> int:
    from chronus.core.seal import seal_schema
    from chronus.service.api.routers.procurement import openapi_fragment

    openapi_fragment()

    os.environ["CHRONUS_TENANT_TOKENS"] = API_TOKENS
    from chronus.service.api.app import create_app as create_api_app

    seal_schema(create_api_app().openapi(), context="api_openapi")
    print("api_openapi seal ok")

    os.environ["CHRONUS_TENANT_TOKENS"] = DEPLOY_TOKENS
    from chronus.service.app import create_app as create_deploy_app

    deploy_paths = create_deploy_app().openapi().get("paths", {})
    missing = [path for path in CAPACITY_PATHS if path not in deploy_paths]
    if missing:
        raise SystemExit(f"deploy app missing sealed capacity routes: {missing}")
    fragment = {path: deploy_paths[path] for path in CAPACITY_PATHS}
    seal_schema(fragment, context="deploy_capacity_openapi")
    print("deploy_capacity_openapi seal ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
