"""Public receipt-verification and authenticated receipt-creation routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from chronus.security import (
    Ed25519Signer,
    OVIDStorage,
    VerifyEndpoint,
)
from chronus.service.dependencies import get_current_tenant
from chronus.service.models import ErrorResponse, VerificationResult

router = APIRouter(prefix="/verify", tags=["verification"])

# The current API process owns ephemeral signing keys and process-local receipts.
# These are useful for integration testing, but do not provide durable receipt
# custody across process restart or multiple workers.
_ed25519_signer = Ed25519Signer()
_ovid_storage = OVIDStorage()
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
    description="Checks a process-local Ed25519 receipt. This endpoint does not "
    "evaluate release qualification.",
)
async def verify_hash(
    hash_value: str,
) -> VerificationResult:
    """Verify a process-local Ed25519-signed OVID receipt without authentication."""
    if len(hash_value) != 64 or any(
        character not in "0123456789abcdef" for character in hash_value.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="invalid_hash",
                error_code="VF001",
                message="Receipt ID must be a 64-character SHA-256 digest.",
            ).model_dump(),
        )

    receipt = _ovid_storage.get_receipt(hash_value)
    if receipt is None:
        return VerificationResult(
            qualification_status="NOT_FOUND",
            invariant_summary="Receipt not found in this API process.",
        )

    is_valid = _verify_endpoint.verify_receipt(receipt)
    return VerificationResult(
        qualification_status="VERIFIED" if is_valid else "VERIFICATION_FAILED",
        invariant_summary=(
            "Ed25519 receipt signature verified; release qualification was not evaluated."
            if is_valid
            else "Receipt signature verification failed."
        ),
        verification_suite_total_latency_ms=0.0,
    )


@router.post(
    "/receipt",
    response_model=dict,
    summary="Create and store a verification receipt",
    description="Create a process-local Ed25519-signed receipt for a value.",
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
                error="signature_algorithm_unavailable",
                error_code="VF002",
                message="ML-DSA signing is not implemented by this service.",
            ).model_dump(),
        )
    if not use_ed25519:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="signature_required",
                error_code="VF003",
                message="At least one implemented signature algorithm is required.",
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
    signature = _ed25519_signer.sign(receipt_id.encode("ascii"))
    receipt = _ovid_storage.create_receipt(
        receipt_id,
        ed25519_signature=signature,
        latency_ms=0.0,
    )

    return {
        "receipt_id": receipt_id,
        "payload_digest": receipt.hash_value,
        "signature_algorithm": _ed25519_signer.algorithm,
        "ed25519_signature": receipt.ed25519_signature,
        "verify_url": f"/verify/{receipt_id}",
        "auth_required": False,
    }