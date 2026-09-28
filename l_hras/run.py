"""Deployment entry point — Part XVII.

    python -m l_hras.run --config config.toml

Loads and validates the config, initializes the Guardian, and brings it
to standing. ``--self-test`` then fires one signed benign request and
one forged request through respond() so the standing report shows both
sides of the verdict boundary. Exit status is 0 only when the Guardian
stands; every failure fails closed with a non-zero exit and the
taxonomy code on stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .claims import claims_report
from .config import load_config
from .guardian import initialize, respond, stand
from .selfdefense import write_manifest
from .types import (
    AdversaryClass,
    Request,
    RequestAttestation,
    RequestKind,
    signed_request,
)


def _self_test(lhras) -> dict:
    benign = Request(
        kind=RequestKind.BENIGN,
        attestation=RequestAttestation(token="", payload_digest=""),
        actor="self-test",
        action="read",
        telemetry=[0.9, 1.0, 1.1],
        state=[[1.0, 0.0], [0.0, 0.0]],
        position=(0.25, 0.25),
        target=(0.25, 0.25),
        adversary_class=AdversaryClass.BENIGN,
        attack_vector=[0.1, 0.2, 0.3],
        observation={"severity": 0.1},
    )
    benign = signed_request(lhras.cfg.trust_root, benign, issuer="self-test")
    benign_result = respond(lhras, benign)

    forged = Request(
        kind=RequestKind.ADVERSARIAL,
        attestation=RequestAttestation(
            token="0" * 64, payload_digest=benign.payload_digest()
        ),
        adversary_class=AdversaryClass.APT,
        adversary_id="forged-1",
    )
    forged_result = respond(lhras, forged)

    return {
        "benign": {
            "ok": benign_result.is_ok,
            "allowed": benign_result.value.allowed if benign_result.is_ok else None,
            "error": benign_result.error.code if benign_result.is_err else None,
        },
        "forged": {
            "ok": forged_result.is_ok,
            "error": forged_result.error.code if forged_result.is_err else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l_hras.run", description="L-HRAS — The Guardian")
    parser.add_argument("--config", required=True, help="path to config.toml")
    parser.add_argument("--self-test", action="store_true", help="fire a signed benign + a forged request after standing")
    parser.add_argument("--claims", action="store_true", help="print the claims register and exit")
    parser.add_argument("--write-manifest", action="store_true", help="regenerate the code-integrity manifest and exit")
    args = parser.parse_args(argv)

    if args.write_manifest:
        manifest = write_manifest()
        print(json.dumps({"manifest": manifest, "files": len(manifest)}))
        return 0

    if args.claims:
        print(json.dumps(claims_report(), indent=2))
        return 0

    cfg_result = load_config(args.config)
    if cfg_result.is_err:
        print(f"config: {cfg_result.error}", file=sys.stderr)
        return 2
    cfg = cfg_result.value

    started = initialize(cfg)
    if started.is_err:
        print(f"initialize: {started.error}", file=sys.stderr)
        return 3
    lhras = started.value

    standing = stand(lhras)
    if standing.is_err:
        print(f"stand: {standing.error}", file=sys.stderr)
        return 4

    report = {
        "standing": True,
        "state": standing.value.to_dict(),
        "swarm": {"id": lhras.swarm.id, "workers": len(lhras.swarm.workers)},
        "health": lhras.standing_state.monitor.run_checks(),
        "metrics": dict(lhras.metrics.counters),
        "at": time.time(),
    }
    if args.self_test:
        report["self_test"] = _self_test(lhras)

    print(json.dumps(report, indent=2, default=str))
    print("The Guardian stands.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
