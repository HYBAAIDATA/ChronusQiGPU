#!/usr/bin/env python3
"""Seal the live OpenAPI document — not a hand-kept fragment.

Fails if any path, field name, or enum value on /v1 carries a banned
mechanism token. Also seals the procurement route fragment.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

# Auth must be configured for app import side-effects / readiness elsewhere.
os.environ.setdefault(
    "CHRONUS_TENANT_TOKENS",
    json.dumps(
        {
            "seal-check-token": {
                "tenant_id": "seal",
                "scopes": ["workloads:read", "workloads:write", "evidence:read"],
            }
        }
    ),
)

from chronus.core.seal import seal_schema  # noqa: E402
from chronus.service.api.app import create_app  # noqa: E402
from chronus.service.api.routers.procurement import openapi_fragment  # noqa: E402


def main() -> int:
    openapi_fragment()  # raises if the fragment itself is dirty
    app = create_app()
    schema = app.openapi()
    seal_schema(schema, context="live_openapi")
    print("openapi seal ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
