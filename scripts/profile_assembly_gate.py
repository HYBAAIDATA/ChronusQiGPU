#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from hyba_profiles import AssemblyIntent
from hyba_profiles import ModuleEvidence
from hyba_profiles import Tier
from hyba_profiles import compile_assembly


def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument(
        "--intent-manifest",
        action="store_true",
        help="manifest is a C1 IntentManifest YAML (apiVersion hyba.ai/v1)",
    )
    p.add_argument("--out", default="results/profile_assembly_gate.json")
    a = p.parse_args()
    if a.intent_manifest:
        from hyba_profiles.intent_manifest import load_intent_manifest

        intent = load_intent_manifest(Path(a.manifest))
        key = os.environ.get("HYBA_ASSEMBLY_SIGNING_KEY", "").encode()
        result = compile_assembly(intent, signing_key=key)
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n")
        print(result.gate.status.value)
        raise SystemExit(0 if not result.gate.blockers else 1)
    raw = json.loads(Path(a.manifest).read_text())
    raw["dominant_tiers"] = tuple(Tier(v) for v in raw["dominant_tiers"])
    raw["modules"] = tuple(raw["modules"])
    raw["use_cases"] = tuple(raw["use_cases"])
    raw["economics"] = tuple(raw["economics"])
    raw["module_evidence"] = tuple(ModuleEvidence(**e) for e in raw["module_evidence"])
    key = os.environ.get("HYBA_ASSEMBLY_SIGNING_KEY", "").encode()
    result = compile_assembly(AssemblyIntent(**raw), signing_key=key)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n")
    print(result.gate.status.value)
    raise SystemExit(0 if not result.gate.blockers else 1)


if __name__ == "__main__":
    main()
