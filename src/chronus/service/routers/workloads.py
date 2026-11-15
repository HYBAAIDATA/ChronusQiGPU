"""Workload submission and management API routes."""

from datetime import datetime
from datetime import timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from chronus.backends.lattice import (
    HardwareUnavailableError,
    LatticeOverflowError,
    ParityVerificationError,
)
from chronus.execution import execution_router
from chronus.execution.qigpu import QiGPUOrchestrator
from chronus.sdk.client import ChronusAPISDK, ChronusSDKError
from chronus.service.dependencies import get_current_tenant, security, service_config
from chronus.service.models import (
    ErrorResponse,
    PaginatedWorkloads,
    WorkloadRequest,
    WorkloadResponse,
    WorkloadStatus,
)
import hashlib
import time
from chronus.core.seal import find_banned_tokens, scrub_dict_strings
from chronus.core.workload_alias import (
    INTERNAL_INGEST_WORKLOAD,
    INTERNAL_SCALING_WORKLOAD,
    externalize_scaling_result,
    normalize_workload_type,
)
from chronus.qualification import QualificationHarness, Tier
from chronus.qualification.harness import verify_transcript_integrity
from chronus.qualification.transcript_store import remember as remember_transcript
from chronus.qualification.transcript_store import recall_by_class
from chronus.security.receipt_signer import receipt_signer
from chronus.storage.connectors import zero_copy_connector_manager
from chronus.service.workload_store import get_workload_store


def _sealed_error_message(message: str) -> str:
    """Customer-visible errors must not leak mechanism tokens."""
    if find_banned_tokens(message):
        return "Workload rejected: invalid or unsupported request."
    return message


def _suspended_tier_fields(contract) -> dict:
    economics = {
        "tier": Tier.SUSPENDED.value,
        "service_level": "envelope.suspended",
        "escalation_threshold": "model_risk_alarm",
        "review_budget_ccu": 0,
        "relative_price_weight": 0.0,
    }
    return {
        "tier": Tier.SUSPENDED.value,
        "qualification_evidence_hash": contract.qualification_evidence_hash,
        "envelope": contract.to_public_dict()["envelope"],
        "tier_contract_version": contract.tier_contract_version,
        "tier_suspended": True,
        "metadata_tier_economics": economics,
        "metadata_qualification_scope": "reference_model_class",
    }


# Include the submission index in reference-model probes when it is small
# enough for exact Decimal residual measurement. Not a backend re-probe.
_MAX_SUBMISSION_PROBE_INDEX = 256


def _scaling_index_from_result(result: object) -> int | None:
    if not isinstance(result, dict):
        return None
    payload = result.get("result")
    if not isinstance(payload, dict):
        payload = result
    index = payload.get("index")
    if isinstance(index, int) and not isinstance(index, bool) and index >= 0:
        return index
    representation = payload.get("representation")
    if isinstance(representation, dict):
        nested = representation.get("index")
        if isinstance(nested, int) and not isinstance(nested, bool) and nested >= 0:
            return nested
    return None


def _attach_tier_fields(
    workload_type: object,
    *,
    status: WorkloadStatus,
    result: object = None,
) -> dict:
    """Attach reference-model qualification for scaling.v1.

    Scope is still ``reference_model_class``: residuals come from the harness
    model, not a re-probe of the selected execution backend. When the
    submission index is available and within the probe budget, it is included
    in the measured envelope so evidence tracks the customer's working size.
    """
    if status != WorkloadStatus.COMPLETED:
        return {}
    internal = normalize_workload_type(workload_type)
    if internal != INTERNAL_SCALING_WORKLOAD:
        return {}
    seed = int(hashlib.sha256(b"qualify:" + internal.encode()).hexdigest()[:16], 16)
    harness = QualificationHarness()
    prior = recall_by_class(internal)
    if prior is not None:
        if not verify_transcript_integrity(prior.audit_transcript):
            from chronus.qualification.tiers import TIER_CONTRACT_VERSION, TierContract

            suspended = TierContract(
                tier=Tier.SUSPENDED,
                tier_contract_version=TIER_CONTRACT_VERSION,
                residual_bound_by_size=prior.contract.residual_bound_by_size,
                qualification_evidence_hash=prior.evidence_hash,
                suspended=True,
            )
            return _suspended_tier_fields(suspended)
        contract = harness.reverify_contract(prior)
        if contract.suspended:
            return _suspended_tier_fields(contract)
    from chronus.qualification.harness import _default_probe_sizes

    sizes = _default_probe_sizes(seed)
    submission_index = _scaling_index_from_result(result)
    included_submission = False
    if (
        submission_index is not None
        and submission_index <= _MAX_SUBMISSION_PROBE_INDEX
    ):
        sizes = tuple(sorted(set(sizes) | {submission_index}))
        included_submission = True
    qualified = harness.qualify(internal, seed=seed, sizes=sizes)
    remember_transcript(qualified)
    public = qualified.public_decision_fields()
    return {
        "tier": public["tier"],
        "qualification_evidence_hash": public["qualification_evidence_hash"],
        "envelope": public["envelope"],
        "tier_contract_version": public["tier_contract_version"],
        "tier_suspended": public["suspended"],
        "metadata_tier_economics": public["economics"],
        "metadata_qualification_scope": public["qualification_scope"],
        "metadata_submission_index_probed": included_submission,
    }

_workload_ed25519_signer = receipt_signer
from chronus.service.telemetry import (
    current_tenant_id,
    current_workload_id,
    metrics_registry,
    trace_span,
)

router = APIRouter(prefix="/workloads", tags=["workloads"])

workload_store = get_workload_store()


def workload_counts() -> tuple[int, int]:
    return workload_store.counts()


@router.post(
    "/submit",
    response_model=WorkloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a computational workload",
    description="Submit a workload to the Chronus computational substrate for exact algebraic processing.",
)
async def submit_workload(
    request: WorkloadRequest,
    tenant_id: str = Depends(get_current_tenant),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> WorkloadResponse:
    """Execute on the mathematical reference backend or a configured adapter."""
    if request.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="Request tenant_id does not match authenticated tenant.",
            ).model_dump(),
        )

    current_tenant_id.set(tenant_id)
    start_wall_time = time.time()
    try:
        with trace_span("api_ingestion", {"tenant_id": request.tenant_id, "workload_type": str(request.workload_type)}):
            pass
        if service_config.execution_backend_url:
            sdk = ChronusAPISDK(
                tenant_id=request.tenant_id,
                access_token=credentials.credentials,
                region=request.region,
                base_url=service_config.execution_backend_url,
            )
            try:
                submission = await run_in_threadpool(
                    sdk.submit_workload,
                    payload_bytes=request.payload_bytes,
                    workload_type=request.workload_type,
                    representation_mode=request.representation_mode,
                    priority=request.priority,
                    callback_url=request.callback_url,
                    metadata=request.metadata,
                    backend_preference=request.backend_preference,
                )
            finally:
                sdk.close()
            workload_id = submission.get("workload_id")
            if not workload_id:
                raise ChronusSDKError(
                    "Execution adapter returned no workload ID",
                    status_code=502,
                    response=submission,
                )
            parsed_id = UUID(workload_id)
            backend_status = WorkloadStatus(submission["status"])
            result = submission.get("result")
            if (
                normalize_workload_type(request.workload_type) == INTERNAL_SCALING_WORKLOAD
                and isinstance(result, dict)
            ):
                result = externalize_scaling_result(result)
                scrub_dict_strings(result, context="scaling.v1 adapter result")
            receipt = submission.get("verification_receipt")
            ccu_cost = submission.get("ccu_cost")
        else:
            backend_preference = request.backend_preference
            if backend_preference == "auto":
                backend_preference = QiGPUOrchestrator(execution_router).auto_select(
                    request.workload_type
                )[0]
            internal_workload = request.internal_workload_type()
            is_folding = internal_workload in (
                "PV_LATTICE_FOLD",
                "TRINITY_SCALE_FOLD_STORE",
                INTERNAL_INGEST_WORKLOAD,
            )
            is_storage = internal_workload in (
                "PHYLOTAXIS_STORE",
                "THESEUS_RETRIEVE",
                "OVID_NORM_PROOF",
                "ZERO_COPY_CONNECTOR_EXECUTE",
            )
            with trace_span("execution_dispatch", {"backend": backend_preference, "workload_type": str(request.workload_type)}):
                if is_folding:
                    with trace_span("algebraic_folding"):
                        pass
                if is_storage:
                    with trace_span("ovid_storage"):
                        pass
                execution = await run_in_threadpool(
                    execution_router.execute,
                    request.payload_bytes,
                    internal_workload,
                    backend_preference,
                )
            parsed_id = uuid4()
            backend_status = WorkloadStatus.COMPLETED
            result = execution.to_dict()
            if internal_workload == INTERNAL_SCALING_WORKLOAD and isinstance(result, dict):
                result = externalize_scaling_result(result)
                scrub_dict_strings(result, context="scaling.v1 result")
            raw_digest = (result.get("result") or {}).get("execution_digest") if isinstance(result, dict) else None
            if not raw_digest:
                raw_digest = hashlib.sha256(str(result).encode("utf-8")).hexdigest()
            raw_digest_str = str(raw_digest)

            # Store only the result-digest text, then sign its content address.
            # These are process-local Ed25519 receipts: no ML-DSA or STARK proof.
            receipt_id = zero_copy_connector_manager.ovid.store(
                raw_digest_str.encode("utf-8")
            )
            slug = tenant_id.replace("tenant_", "").replace("-", "_")
            prefix_slug = slug[:4] if slug else "apex"
            receipt_handle = f"o1_{prefix_slug}_{receipt_id[:8]}"
            ed_sig = _workload_ed25519_signer.sign(receipt_id.encode("ascii"))

            zero_copy_connector_manager.ovid.create_receipt(
                receipt_id,
                ed25519_signature=ed_sig,
                latency_ms=0.0,
                receipt_handle=receipt_handle,
                metadata={
                    "tenant_id": tenant_id,
                    "receipt_scope": "workload_result_digest",
                    "source_result_digest": raw_digest_str,
                    "storage_scope": "process-local",
                },
            )
            receipt = receipt_handle
            ccu_cost = None
    except (ValueError, LatticeOverflowError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="invalid_or_unsupported_workload",
                error_code="WL001",
                message=_sealed_error_message(str(exc)),
            ).model_dump(),
        ) from exc
    except ChronusSDKError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error="execution_adapter_error",
                error_code="EXE002",
                message="Chronus accelerator adapter rejected or could not process the workload.",
            ).model_dump(),
        ) from exc
    except HardwareUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error="accelerator_unavailable",
                error_code="EXE003",
                message="The selected accelerator could not execute the workload.",
            ).model_dump(),
        ) from exc
    except ParityVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error="accelerator_parity_failure",
                error_code="EXE004",
                message="Accelerator result failed exact parity verification.",
            ).model_dump(),
        ) from exc

    tier_fields = _attach_tier_fields(
        request.workload_type, status=backend_status, result=result
    )
    economics = tier_fields.pop("metadata_tier_economics", None)
    qualification_scope = tier_fields.pop("metadata_qualification_scope", None)
    submission_index_probed = tier_fields.pop("metadata_submission_index_probed", None)
    metadata = dict(request.metadata or {})
    if economics is not None:
        metadata["tier_economics"] = economics
    if qualification_scope is not None:
        metadata["qualification_scope"] = qualification_scope
    if submission_index_probed is not None:
        metadata["submission_index_probed"] = submission_index_probed
    # Relative price weight is a multiplier on a measured/base CCU only.
    # Do not invent an absolute cost from the weight when no meter exists.
    if economics is not None and ccu_cost is not None:
        ccu_cost = float(ccu_cost) * float(economics.get("relative_price_weight", 1.0))

    workload = WorkloadResponse(
        workload_id=parsed_id,
        status=backend_status,
        workload_type=request.workload_type,
        representation_mode=request.representation_mode,
        priority=request.priority,
        tenant_id=request.tenant_id,
        region=request.region,
        ccu_cost=ccu_cost,
        result=result,
        verification_receipt=receipt,
        callback_url=request.callback_url,
        metadata=metadata or None,
        completed_at=(
            datetime.now(timezone.utc)
            if backend_status == WorkloadStatus.COMPLETED
            else None
        ),
        tier=tier_fields.get("tier"),
        qualification_evidence_hash=tier_fields.get("qualification_evidence_hash"),
        envelope=tier_fields.get("envelope"),
        tier_contract_version=tier_fields.get("tier_contract_version"),
        tier_suspended=tier_fields.get("tier_suspended"),
    )
    current_workload_id.set(str(parsed_id))
    elapsed_duration = time.time() - start_wall_time
    metrics_registry.record_request(request.tenant_id, str(backend_status), str(request.workload_type))
    metrics_registry.record_execution_latency(elapsed_duration)
    metrics_registry.record_ccu(request.tenant_id, float(ccu_cost or 1.0))

    workload_store.save(workload)
    return workload

@router.get(
    "/{workload_id}",
    response_model=WorkloadResponse,
    summary="Get workload status and results",
    description="Retrieve the current status and results of a submitted workload.",
)
async def get_workload(
    workload_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> WorkloadResponse:
    """Get workload status by ID.

    Returns the current lifecycle state, CCU cost, and results
    if the workload has completed.
    """
    workload_id_str = str(workload_id)

    workload = workload_store.get(workload_id_str)
    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error="workload_not_found",
                error_code="WL003",
                message=f"Workload {workload_id} not found.",
            ).model_dump(),
        )

    # Verify tenant access
    if workload.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="You do not have access to this workload.",
            ).model_dump(),
        )

    return workload


@router.get(
    "",
    response_model=PaginatedWorkloads,
    summary="List workloads with pagination",
    description="List all workloads for the authenticated tenant with pagination support.",
)
async def list_workloads(
    page: int = 1,
    page_size: int = 50,
    tenant_id: str = Depends(get_current_tenant),
) -> PaginatedWorkloads:
    """List workloads with pagination.

    Returns a paginated list of workloads submitted by the authenticated tenant.
    """
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorResponse(
                error="invalid_pagination",
                error_code="WL005",
                message="page must be positive and page_size must be between 1 and 100.",
            ).model_dump(),
        )
    items, total = workload_store.list_for_tenant(
        tenant_id, offset=(page - 1) * page_size, limit=page_size
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedWorkloads(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.delete(
    "/{workload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a workload",
    description="Cancel a pending or running workload.",
)
async def cancel_workload(
    workload_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> None:
    """Cancel a workload by ID.

    Attempts to cancel a workload that is queued or executing.
    Completed or failed workloads cannot be cancelled.
    """
    workload_id_str = str(workload_id)

    workload = workload_store.get(workload_id_str)
    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error="workload_not_found",
                error_code="WL003",
                message=f"Workload {workload_id} not found.",
            ).model_dump(),
        )

    if workload.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="You do not have access to this workload.",
            ).model_dump(),
        )

    if workload.status in (
        WorkloadStatus.COMPLETED,
        WorkloadStatus.FAILED,
        WorkloadStatus.CANCELLED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="workload_not_cancellable",
                error_code="WL004",
                message=f"Workload {workload_id} is in {workload.status} state and cannot be cancelled.",
            ).model_dump(),
        )

    workload.status = WorkloadStatus.CANCELLED
    workload.completed_at = datetime.now(timezone.utc)
    workload_store.save(workload)