"""Aethel certificate writes — Part XI.

``aethel_write`` folds the canonical JSON of {cert, attestation} through
the Zeckendorf codec, places the block at the next Fibonacci index, and
verifies the Cassini quadruple for that address. Every stored address
carries its quadruple — the Cassini claim in Part XV.
"""

from __future__ import annotations

from typing import Any, Optional

from . import substrates
from .result import AETHEL_WRITE_FAILURE, Ok, Result, error
from .types import Attestation, Certificate, digest_of


def aethel_write(
    aethel: substrates.AethelStore,
    cert: Any,
    attest: Optional[Attestation],
) -> Result[dict[str, Any]]:
    """Write a certificate + attestation block into the aethel space."""
    if cert is None or attest is None:
        return error(AETHEL_WRITE_FAILURE, reason="null input")

    cert_payload = cert.to_dict() if hasattr(cert, "to_dict") else cert
    payload = {
        "cert_digest": (
            cert_payload.get("digest")
            if isinstance(cert_payload, dict)
            else digest_of(cert_payload)
        ),
        "masks": cert_payload.get("masks") if isinstance(cert_payload, dict) else None,
        "lucas": cert_payload.get("lucas") if isinstance(cert_payload, dict) else None,
        "attestation": attest.to_dict(),
    }
    try:
        block = substrates.zeckendorf_fold_payload(
            digest_of(payload).encode("utf-8") + b"|" + str(payload).encode("utf-8")
        )
        index_hint = aethel.next_fibonacci_index()
        cassini = aethel.cassini_quadruple(index_hint)
        addr = substrates.aethel_put(aethel, index_hint, block, cassini)
        aethel.commit()
    except Exception as exc:  # fail closed — the write is the receipt
        return error(AETHEL_WRITE_FAILURE, reason=str(exc))
    return Ok({"address": (addr.index, addr.value), "cassini": list(cassini)})


# ---------------------------------------------------------------------------
# Certificate builders — every state transition writes one.
# ---------------------------------------------------------------------------


def standing_certificate(state: Any) -> dict[str, Any]:
    body = {
        "kind": "standing_certificate",
        "multiply": state.multiply,
        "entangle": state.entangle,
        "swarm": state.swarm,
        "honey_pot": state.honey_pot,
        "willow_expose": state.willow_expose,
        "topologies": dict(state.topologies),
    }
    body["digest"] = digest_of(body)
    return body


def throttle_certificate(decision: Any) -> dict[str, Any]:
    body = {
        "kind": "throttle_certificate",
        "mode": dict(decision.mode),
        "reason": decision.reason,
        "scope": decision.scope,
        "started_at": decision.started_at,
        "expires_at": decision.expires_at,
        "blast_radius": decision.blast_radius,
    }
    body["digest"] = digest_of(body)
    return body


def break_glass_certificate(bg: Any) -> dict[str, Any]:
    body = {
        "kind": "break_glass_certificate",
        "actor": bg.actor,
        "reason": bg.reason,
        "activated_at": bg.activated_at,
        "expires_at": bg.expires_at,
    }
    body["digest"] = digest_of(body)
    return body


def response_certificate(cert: Certificate, verdict: bool) -> dict[str, Any]:
    body = {"kind": "response_certificate", "verdict": verdict, "cert": cert.to_dict()}
    body["digest"] = digest_of(body)
    return body
