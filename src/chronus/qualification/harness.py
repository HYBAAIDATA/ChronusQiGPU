"""QualificationHarness — tiers earned by measured residual decay.

Probe generation measures residual vs input size. Classification is
reproducible for a fixed seed. Public outputs are mechanism-sealed; the
audit transcript keeps full internal provenance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any, Callable, Sequence

from chronus.core.seal import assert_sealed, external_behavior_blurb
from chronus.qualification.tiers import (
    TIER_CONTRACT_VERSION,
    Tier,
    TierContract,
    economics_for_tier,
)

_DECIMAL_PREC = 80

# Internal probe identity — never emitted on external surfaces.
_INTERNAL_PROBE_FAMILY = "metallic_sequence_residual_v1"


@dataclass(frozen=True)
class QualificationResult:
    tier: Tier
    contract: TierContract
    evidence_hash: str
    audit_transcript: dict[str, Any]
    public_view: dict[str, Any]
    economics: dict[str, Any]

    def public_decision_fields(self) -> dict[str, Any]:
        """Fields safe to attach to DecisionObject / API responses."""
        payload = {
            "tier": self.tier.value,
            "qualification_evidence_hash": self.evidence_hash,
            "envelope": self.contract.to_public_dict()["envelope"],
            "tier_contract_version": self.contract.tier_contract_version,
            "suspended": self.contract.suspended,
            "tier_assignment_basis": external_behavior_blurb(),
            # Class-level reference-model measurement — not a claim that this
            # submission's selected backend was re-probed end-to-end.
            "qualification_scope": "reference_model_class",
            "economics": self.economics,
        }
        assert_sealed(json.dumps(payload), context="qualification public view")
        return payload


def _stable_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _sha256_hex(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload)).hexdigest()


def _exact_sequence_term(n: int) -> int:
    """Exact integer term via internal metallic recurrence (provenance path)."""
    from chronus.math.binet_lucas import lucas_recurrence

    return lucas_recurrence(n)


def _metallic_unit() -> Decimal:
    return (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)


def _residual(n: int) -> Decimal:
    """Measured residual |α^n − L_n| — decays geometrically for this class.

    Internal identity: α^n − L_n = −β^n exactly, so the residual is |β|^n.
    Evaluating |β|^n directly avoids subtracting two large nearly-equal values,
    which lets rounding dominate for large n. External surfaces never name α/β.
    """
    with localcontext() as ctx:
        # |β|^n needs ~0.21n decimal digits; keep a generous headroom.
        ctx.prec = max(_DECIMAL_PREC, (n // 4) + 40)
        beta = (Decimal(1) - Decimal(5).sqrt()) / Decimal(2)
        return abs(beta) ** n


def _fit_ratios(sizes: Sequence[int], residuals: Sequence[Decimal]) -> dict[str, Decimal]:
    """Fit simple decay descriptors (exact Decimal arithmetic on logs where defined)."""
    if len(sizes) < 3:
        raise ValueError("need at least 3 probe points to fit an envelope")
    # Per-step geometric base: (r_i / r_{i-1})^(1/Δn) — constant under fixed-base decay.
    bases: list[Decimal] = []
    for i in range(1, len(residuals)):
        dn = sizes[i] - sizes[i - 1]
        if residuals[i - 1] > 0 and residuals[i] > 0 and dn > 0:
            ratio = residuals[i] / residuals[i - 1]
            bases.append(ratio ** (Decimal(1) / Decimal(dn)))
    poly_slope = Decimal(0)
    if residuals[0] > 0 and residuals[-1] > 0:
        ds = Decimal(sizes[-1] - sizes[0])
        if ds > 0:
            poly_slope = (residuals[-1].ln() - residuals[0].ln()) / ds
    mean_base = sum(bases) / Decimal(len(bases)) if bases else Decimal(1)
    base_spread = max(bases) - min(bases) if bases else Decimal(1)
    return {
        "mean_geometric_base": mean_base,
        "base_spread": base_spread,
        "poly_slope": poly_slope,
        "terminal_residual": residuals[-1],
    }


def _classify(fit: dict[str, Decimal], *, degraded: bool = False) -> Tier:
    if degraded:
        return Tier.STATISTICAL
    # Geometric: fixed-base exponential decay with a tight terminal residual.
    if (
        fit["mean_geometric_base"] < Decimal("0.75")
        and fit["base_spread"] < Decimal("0.05")
        and fit["terminal_residual"] < Decimal("1e-6")
    ):
        return Tier.GEOMETRIC
    # Polynomial: residual shrinks with size but not geometrically tight.
    if fit["poly_slope"] < 0 and fit["terminal_residual"] < Decimal("1"):
        return Tier.POLYNOMIAL
    return Tier.STATISTICAL


def _default_probe_sizes(seed: int) -> tuple[int, ...]:
    # Deterministic sizes from seed — same seed ⇒ same sizes ⇒ same transcript.
    rng = _SeedSequence(seed)
    base = (8, 12, 16, 20, 24, 28, 32)
    jitter = tuple(b + (rng.next() % 3) for b in base)
    return jitter


class _SeedSequence:
    """Tiny deterministic LCG so qualification needs no external RNG libs."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFF

    def next(self) -> int:
        self._state = (1664525 * self._state + 1013904223) & 0xFFFFFFFF
        return self._state


class QualificationHarness:
    """Run probes, fit envelopes, classify tiers, seal public views."""

    def __init__(
        self,
        *,
        residual_fn: Callable[[int], Decimal] | None = None,
        probe_family: str = _INTERNAL_PROBE_FAMILY,
    ) -> None:
        self._residual_fn = residual_fn or _residual
        self._probe_family = probe_family

    def qualify(
        self,
        workload_class: str,
        *,
        seed: int,
        sizes: Sequence[int] | None = None,
        degrade: bool = False,
        signer: Callable[[bytes], str] | None = None,
    ) -> QualificationResult:
        with localcontext() as ctx:
            ctx.prec = _DECIMAL_PREC
            probe_sizes = tuple(sizes) if sizes is not None else _default_probe_sizes(seed)
            residuals = [self._residual_fn(n) for n in probe_sizes]
            if degrade:
                # Deliberately inflate residuals so classification drops a tier.
                residuals = [
                    r + Decimal("10") + Decimal(i) for i, r in enumerate(residuals)
                ]
            fit = _fit_ratios(probe_sizes, residuals)
            tier = _classify(fit, degraded=degrade)

            bound_points = tuple(
                (int(size), format(residual, "f"))
                for size, residual in zip(probe_sizes, residuals)
            )
            # Audit transcript — FULL provenance (mechanism names allowed here).
            audit_body = {
                "workload_class": workload_class,
                "probe_family": self._probe_family,
                "seed": seed,
                "sizes": list(probe_sizes),
                "residuals": [format(r, "f") for r in residuals],
                "fit": {k: format(v, "f") for k, v in fit.items()},
                "tier": tier.value,
                "tier_contract_version": TIER_CONTRACT_VERSION,
                "degraded_probe": degrade,
                "qualification_scope": "reference_model_class",
                "internal_identities": {
                    "sequence": "L_n",
                    "cross_check": "L_n = F_{n-1} + F_{n+1}",
                    "float64_boundary_index": 70,
                },
            }
            evidence_hash = _sha256_hex(audit_body)
            signature = (signer or self._default_signer)(_stable_json(audit_body))
            audit_transcript = {
                **audit_body,
                "evidence_hash": evidence_hash,
                "signature": signature,
            }

            suspended = tier == Tier.SUSPENDED
            contract = TierContract(
                tier=tier,
                tier_contract_version=TIER_CONTRACT_VERSION,
                residual_bound_by_size=bound_points,
                qualification_evidence_hash=evidence_hash,
                suspended=suspended,
            )
            economics = economics_for_tier(tier).to_public_dict()
            public_view = {
                "tier": tier.value,
                "qualification_evidence_hash": evidence_hash,
                "envelope": contract.to_public_dict()["envelope"],
                "tier_contract_version": TIER_CONTRACT_VERSION,
                "suspended": suspended,
                "tier_assignment_basis": external_behavior_blurb(),
                "qualification_scope": "reference_model_class",
                "economics": economics,
            }
            assert_sealed(json.dumps(public_view), context="qualification public_view")
            return QualificationResult(
                tier=tier,
                contract=contract,
                evidence_hash=evidence_hash,
                audit_transcript=audit_transcript,
                public_view=public_view,
                economics=economics,
            )

    def reverify_contract(self, result: QualificationResult) -> TierContract:
        """Re-run the same seed/sizes; suspend on envelope violation."""
        audit = result.audit_transcript
        sizes = tuple(audit["sizes"])
        seed = int(audit["seed"])
        degrade = bool(audit.get("degraded_probe", False))
        fresh = self.qualify(
            audit["workload_class"],
            seed=seed,
            sizes=sizes,
            degrade=degrade,
        )
        # Compare residuals against contracted bounds (exact string form).
        for (size, bound), (_, fresh_bound) in zip(
            result.contract.residual_bound_by_size, fresh.contract.residual_bound_by_size
        ):
            if Decimal(fresh_bound) > Decimal(bound):
                suspended = TierContract(
                    tier=Tier.SUSPENDED,
                    tier_contract_version=TIER_CONTRACT_VERSION,
                    residual_bound_by_size=fresh.contract.residual_bound_by_size,
                    qualification_evidence_hash=fresh.evidence_hash,
                    suspended=True,
                )
                return suspended
        if fresh.evidence_hash != result.evidence_hash:
            # Seed/size locked — hash mismatch is also a model-risk alarm.
            return TierContract(
                tier=Tier.SUSPENDED,
                tier_contract_version=TIER_CONTRACT_VERSION,
                residual_bound_by_size=fresh.contract.residual_bound_by_size,
                qualification_evidence_hash=fresh.evidence_hash,
                suspended=True,
            )
        return fresh.contract

    @staticmethod
    def _default_signer(body: bytes) -> str:
        # Ed25519 over the canonical transcript body with the process-local
        # receipt key. Not durable key custody; not ML-DSA release signing.
        from chronus.security.receipt_signer import receipt_signer

        return receipt_signer.sign(body)


def verify_transcript_integrity(
    transcript: dict[str, Any],
    *,
    verifier: Callable[[bytes, str], bool] | None = None,
) -> bool:
    """Tamper check: body hash must match AND the stored signature must verify.

    ``verifier(message, signature_hex)`` defaults to the process-local receipt
    signer. Callers that passed a custom ``signer`` to ``qualify()`` must supply
    the matching verifier here.
    """
    body = {
        key: value
        for key, value in transcript.items()
        if key not in ("evidence_hash", "signature")
    }
    if _sha256_hex(body) != transcript.get("evidence_hash"):
        return False
    signature = transcript.get("signature")
    if not isinstance(signature, str):
        return False
    if verifier is not None:
        return bool(verifier(_stable_json(body), signature))
    from chronus.security.receipt_signer import receipt_signer

    return receipt_signer.verify(_stable_json(body), signature)
