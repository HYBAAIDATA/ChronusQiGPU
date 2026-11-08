"""Public receipt-verification and authenticated receipt-creation routes."""

import time

from fastapi import APIRouter, Depends, HTTPException, status

from chronus.security import OVIDStorage, VerifyEndpoint
from chronus.security.receipt_signer import receipt_signer
from chronus.storage.connectors import zero_copy_connector_manager
from chronus.service.dependencies import get_current_tenant
from chronus.service.models import ErrorResponse, VerificationResult

router = APIRouter(prefix="/verify", tags=["verification"])

# API receipts use a shared process-local Ed25519 key. They are not durable
# across restarts and do not carry ML-DSA or STARK claims.
_ed25519_signer = receipt_signer
_ovid_storage: OVIDStorage = zero_copy_connector_manager.ovid
_verify_endpoint = VerifyEndpoint(
    ml_dsa_signer=None,
    ed25519_signer=_ed25519_signer,
    zk_stark_verifier=None,
    ovid_storage=_ovid_storage,
)


@router.get(
    "/{hash_value}",
    response_model=VerificationResult,
    summary="Verify a hash with no authentication required",
    description="Checks process-local Ed25519 receipt signatures. This endpoint does not establish release qualification or ML-DSA/STARK verification.",
)
async def verify_hash(
    hash_value: str,
) -> VerificationResult:
    """Verify an in-process Ed25519 receipt or zero-copy pointer."""
    started = time.perf_counter()
    stripped_hash = hash_value.strip()
    is_valid_format = (
        (len(stripped_hash) == 64 and all(c in "0123456789abcdef" for c in stripped_hash.lower()))
        or stripped_hash.startswith("o1_")
        or stripped_hash.startswith("ptr_ovid_")
        or (len(stripped_hash) >= 8 and all(c in "0123456789abcdef" for c in stripped_hash.lower()))
    )
    if not is_valid_format:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="invalid_hash",
                error_code="VF001",
                message="Receipt ID must be a 64-character SHA-256 digest, an OVID handle (o1_...), or zero-copy pointer (ptr_ovid_...).",
            ).model_dump(),
        )

    receipt = _ovid_storage.get_receipt(stripped_hash)
    if receipt is None and stripped_hash.startswith("ptr_ovid_"):
        pointer = _ovid_storage.resolve_pointer(stripped_hash)
        if pointer is not None:
            ed_sig = _ed25519_signer.sign(pointer.content_hash.encode("ascii"))
            receipt = _ovid_storage.create_pointer_receipt(
                pointer.pointer_id,
                ed25519_signature=ed_sig,
                latency_ms=0.0,
                receipt_handle=f"o1_apex_{pointer.content_hash[:8]}",
            )

    if receipt is None:
        try:
            from chronus.security.al_haras.sovereign import sovereign_ovid_chain
            for r in sovereign_ovid_chain:
                r_handle = getattr(r, "receipt_handle", None)
                r_id = getattr(r, "receipt_id", None)
                r_hash = getattr(r, "hash_value", None)
                if stripped_hash in (r_handle, r_id, r_hash) or (r_handle and r_handle.startswith(stripped_hash)):
                    receipt = r
                    break
        except Exception:
            pass

    if receipt is None:
        return VerificationResult(
            qualification_status="NOT_FOUND",
            invariant_summary="Receipt not found in this API process.",
            total_release_gates_evaluated=0,
            release_gates_passed=0,
            total_invariants_evaluated=0,
            invariants_passed=0,
            verification_suite_total_latency_ms=0.0,
            raw_payload_exposed=False,
            auth_required=False,
        )

    detailed = _verify_endpoint.verify_receipt_detailed(receipt.receipt_id)
    is_valid = detailed.get("valid", False)
    if not is_valid:
        is_valid = _verify_endpoint.verify_receipt(receipt)

    return VerificationResult(
        qualification_status="VERIFIED" if is_valid else "VERIFICATION_FAILED",
        invariant_summary=(
            "Process-local Ed25519 receipt signature verified; this is not a release qualification."
            if is_valid
            else "Receipt signature verification failed or is not supported by this process."
        ),
        total_release_gates_evaluated=0,
        release_gates_passed=0,
        total_invariants_evaluated=1 if is_valid else 0,
        invariants_passed=1 if is_valid else 0,
        verification_suite_total_latency_ms=(time.perf_counter() - started) * 1000,
        receipt_id=receipt.receipt_id,
        receipt_handle=receipt.receipt_handle or receipt.receipt_id,
        hash_value=receipt.hash_value,
        ed25519_verified=detailed.get("ed25519_verified", bool(receipt.ed25519_signature)),
        ml_dsa_verified=detailed.get("ml_dsa_verified", bool(receipt.ml_dsa_signature)),
        stark_quotient_verified=detailed.get("stark_quotient_verified", receipt.stark_proof is not None),
        polynomial_identity="not evaluated (STARK verification unavailable)",
        raw_payload_exposed=False,
        auth_required=False,
        metadata=receipt.metadata,
    )


@router.post(
    "/receipt",
    response_model=dict,
    summary="Create and store a verification receipt",
    description="Create a process-local Ed25519 receipt. ML-DSA is unavailable in this implementation.",
)
async def create_receipt(
    hash_value: str,
    use_ml_dsa: bool = False,
    use_ed25519: bool = True,
    tenant_id: str = Depends(get_current_tenant),
) -> dict:
    """Create a process-local Ed25519 receipt for a supplied value."""
    if use_ml_dsa:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                error="algorithm_unavailable",
                error_code="VF005",
                message="ML-DSA signing is not implemented. No signature was created.",
            ).model_dump(),
        )
    if not use_ed25519:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="signature_required",
                error_code="VF003",
                message="Ed25519 signing must be enabled.",
            ).model_dump(),
        )
    if not hash_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="invalid_payload",
                error_code="VF004",
                message="Receipt payload must not be empty.",
            ).model_dump(),
        )

    receipt_id = _ovid_storage.store(hash_value.encode("utf-8"))
    ed25519_signature = _ed25519_signer.sign(receipt_id.encode("ascii")) if use_ed25519 else None
    ml_dsa_signature = None
    prefix = tenant_id[:4] if tenant_id else "apex"
    receipt_handle = f"o1_{prefix}_{receipt_id[:8]}"
    receipt = _ovid_storage.create_receipt(
        receipt_id,
        ml_dsa_signature=ml_dsa_signature,
        ed25519_signature=ed25519_signature,
        latency_ms=0.0,
        receipt_handle=receipt_handle,
        metadata={
            "tenant_id": tenant_id,
            "storage_scope": "process-local",
            "input_kind": "sha256_digest_text",
        },
    )

    primary_algo = "Ed25519 (process-local)"

    return {
        "receipt_id": receipt_id,
        "receipt_handle": receipt_handle,
        "payload_digest": receipt.hash_value,
        "signature_algorithm": primary_algo,
        "ed25519_signature": receipt.ed25519_signature,
        "ml_dsa_signature": receipt.ml_dsa_signature,
        "verify_url": f"/verify/{receipt_id}",
        "auth_required": False,
    }
