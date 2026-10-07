"""Chronus algebraic search optimisation for the mining execution fabric.

The generated search plan is portable across CPU, GPU, ASIC, and Super ASIC
hashing routes.  Consensus verification remains SHA-256d so stronger execution
technology can scale without creating an incompatible proof.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

from quantum_compute_substrate.phi_tensor_core import FoldState, QuantumFoldTensorCore


@dataclass(frozen=True)
class SubstrateOrderingEvidence:
    candidate_count: int
    original_dim: int
    folded_dim: int
    fold_depth: int
    compression_ratio: float
    reconstruction_error_l2: float
    state_norm: float
    transformed_norm: float
    permutation_preserved: bool
    input_fingerprint: str
    output_fingerprint: str
    operator: str = "phi-tensor-diffusion"
    role: str = "SEARCH_OPTIMIZATION"
    execution_scope: str = "CPU/GPU/ASIC/SUPER_ASIC"
    consensus_authority: bool = False
    consensus_rule: str = "SHA256d(header) <= target"
    claim_lane: str = "RESTRICTED (INTERNAL)"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ChronusSubstrateMiningBridge:
    """Build accelerator-portable search plans with the integrated tensor core."""

    def __init__(self, *, seed: int = 0) -> None:
        self.seed = int(seed)

    @staticmethod
    def _validate_nonces(nonces: Sequence[int]) -> list[int]:
        normalized: list[int] = []
        for raw in nonces:
            if isinstance(raw, bool):
                raise ValueError("nonce candidates must be uint32 integers")
            nonce = int(raw)
            if nonce != raw or not 0 <= nonce <= 0xFFFFFFFF:
                raise ValueError("nonce candidates must be uint32 integers")
            normalized.append(nonce)
        if len(set(normalized)) != len(normalized):
            raise ValueError("nonce candidates must be unique")
        return normalized

    @staticmethod
    def _fingerprint(nonces: list[int]) -> str:
        # Deferred import avoids a module cycle while using the canonical seal.
        from mining.hash_pipeline import nonce_order_fingerprint

        return nonce_order_fingerprint(nonces).hex()

    def order(
        self,
        nonces: Sequence[int],
        scores: Sequence[float],
        *,
        fold_depth: int = 1,
    ) -> tuple[list[int], SubstrateOrderingEvidence]:
        """Return a sealed permutation and measured substrate evidence."""

        if not isinstance(fold_depth, int) or isinstance(fold_depth, bool) or fold_depth < 0:
            raise ValueError("fold_depth must be a non-negative integer")
        candidates = self._validate_nonces(nonces)
        values = np.asarray(scores, dtype=np.float64)
        if values.ndim != 1 or values.size != len(candidates):
            raise ValueError("scores must be one-dimensional and match candidate count")
        if not np.all(np.isfinite(values)) or np.any(values < 0.0):
            raise ValueError("scores must be finite and non-negative")

        if not candidates:
            evidence = SubstrateOrderingEvidence(
                candidate_count=0,
                original_dim=0,
                folded_dim=0,
                fold_depth=0,
                compression_ratio=1.0,
                reconstruction_error_l2=0.0,
                state_norm=0.0,
                transformed_norm=0.0,
                permutation_preserved=True,
                input_fingerprint=self._fingerprint([]),
                output_fingerprint=self._fingerprint([]),
            )
            return [], evidence

        if not np.any(values):
            values = np.ones(values.size, dtype=np.float64)
        state = FoldState(values.astype(np.complex128), 0, values.size).normalize()
        core = QuantumFoldTensorCore(core_id=0, dim=values.size, seed=self.seed)
        transformed = core.amplitude_amplification(state)
        if not core.integrity_check(state) or not core.integrity_check(transformed):
            raise RuntimeError("substrate transformation failed norm integrity")

        probabilities = np.abs(transformed.data) ** 2
        order = np.lexsort((np.arange(values.size), -probabilities))
        ordered = [candidates[int(index)] for index in order]
        permutation_preserved = sorted(ordered) == sorted(candidates)
        if not permutation_preserved:
            raise RuntimeError("substrate ordering changed the candidate set")

        folded = transformed.fold(target_depth=fold_depth)
        reconstruction_error = folded.reconstruction_error(transformed)
        evidence = SubstrateOrderingEvidence(
            candidate_count=len(candidates),
            original_dim=transformed.dim,
            folded_dim=folded.dim,
            fold_depth=folded.depth,
            compression_ratio=float(transformed.dim / folded.dim),
            reconstruction_error_l2=reconstruction_error,
            state_norm=state.norm,
            transformed_norm=transformed.norm,
            permutation_preserved=permutation_preserved,
            input_fingerprint=self._fingerprint(candidates),
            output_fingerprint=self._fingerprint(ordered),
        )
        return ordered, evidence


__all__ = ["ChronusSubstrateMiningBridge", "SubstrateOrderingEvidence"]


# ---------------------------------------------------------------------------
# Virtual iGPU execution path (optional, fail-closed)
# ---------------------------------------------------------------------------
def submit_via_virtual_igpu(
    plan: Any,
    *,
    header80: bytes | None = None,
    target_hex: str | None = None,
    tenant: str = "mining",
    execution_policy: str = "preferred_accelerator",
    allow_software_fallback: bool = True,
    endpoint: str | None = None,
    delivery_mode: str = "embedded",
) -> dict[str, Any]:
    """Route a portable search plan through Chronus Virtual iGPU.

    SHA-256d re-verification remains the validity oracle. The Virtual iGPU
    returns a receipt; a found nonce is not pool-accepted until the mining
    stack submits and receives acknowledgement separately.
    """
    from chronus.virtual_igpu import ChronusClient
    from chronus.virtual_igpu.abi import DeliveryMode, Workload, WorkloadKind
    import uuid

    if hasattr(plan, "__dict__") and not isinstance(plan, dict):
        plan_dict = {
            k: getattr(plan, k)
            for k in dir(plan)
            if not k.startswith("_") and not callable(getattr(plan, k))
        }
        # Prefer dataclasses.asdict when available
        try:
            from dataclasses import asdict, is_dataclass

            if is_dataclass(plan):
                plan_dict = asdict(plan)
        except Exception:
            pass
    else:
        plan_dict = dict(plan)

    if header80 is not None:
        if not isinstance(header80, (bytes, bytearray)) or len(header80) != 80:
            raise ValueError("header80 must be exactly 80 bytes")
        if target_hex is None:
            raise ValueError("target_hex is required for SHA256d execution")
        try:
            target_int = int(target_hex, 16)
        except (TypeError, ValueError) as exc:
            raise ValueError("target_hex is malformed") from exc
        if target_int < 0 or target_int >= 1 << 256:
            raise ValueError("target_hex is outside the uint256 range")
    else:
        target_int = None

    # The delivery mode is explicit and never inferred from an endpoint:
    # embedded + endpoint and remote + no endpoint are both rejected by the client.
    delivery_mode = DeliveryMode(str(delivery_mode)).value
    client = ChronusClient(delivery_mode=delivery_mode, endpoint=endpoint)
    payload = {
        "plan": plan_dict,
        "header80_hex": header80.hex() if isinstance(header80, (bytes, bytearray)) else header80,
        "target_hex": target_hex,
    }
    # Prefer SHA256D_SCAN when header material is present; else fold plan as STORE proof
    if header80 is not None:
        kind = WorkloadKind.SHA256D_SCAN if hasattr(WorkloadKind, "SHA256D_SCAN") else WorkloadKind.SHA256D_VERIFY
        windows = list(plan_dict.get("windows") or ())
        if windows:
            normalized: list[tuple[int, int]] = []
            for window in windows:
                start = int(window["start"])
                count = int(window["count"])
                if start < 0 or count <= 0 or start + count > 1 << 32:
                    raise ValueError("plan contains an invalid nonce window")
                normalized.append((start, count))
            normalized.sort()
            for previous, current in zip(normalized, normalized[1:]):
                if previous[0] + previous[1] != current[0]:
                    raise ValueError(
                        "Virtual iGPU SHA256d requires contiguous nonce windows"
                    )
            start_nonce = normalized[0][0]
            count = sum(item[1] for item in normalized)
        else:
            start_nonce = int.from_bytes(bytes(header80)[76:80], "little")
            count = 1
        body = {
            "header80_hex": payload["header80_hex"],
            "target_hex": target_hex,
            "start_nonce": start_nonce,
            "count": count,
            "plan": plan_dict,
        }
    else:
        kind = WorkloadKind.FOLD if hasattr(WorkloadKind, "FOLD") else WorkloadKind.STORE
        body = payload

    workload = Workload(
        id=str(uuid.uuid4()),
        kind=kind,
        tenant=tenant,
        input=body,
        execution_policy=execution_policy,
        allow_software_fallback=allow_software_fallback,
        delivery_mode=delivery_mode,
    )
    result = client.submit(workload)
    if result.status != "ok":
        raise RuntimeError(f"Chronus execution did not succeed: {result.status}")

    host_verification: dict[str, Any] | None = None
    if header80 is not None:
        output = dict(result.output or {})
        hits = list(output.get("hits") or ())
        checked = int(output.get("checked") or 0)
        if not hits and checked != count:
            raise RuntimeError(
                f"Chronus checked {checked} nonces; expected {count}"
            )
        from chronus.virtual_igpu.host_verify import CandidateVerificationError, verify_hits

        try:
            verified_hits = verify_hits(
                bytes(header80)[:76],
                hits,
                target_int,
                nonce_range=(start_nonce, count),
            )
        except CandidateVerificationError as exc:
            raise RuntimeError(f"Chronus SHA256d candidate rejected: {exc}") from exc
        host_verification = {
            "status": "passed",
            "oracle": "host_hashlib_sha256d",
            "checked_candidates": len(verified_hits),
            "verified_hits": verified_hits,
        }

    out = result.to_dict() if hasattr(result, "to_dict") else dict(result.__dict__)
    if host_verification is not None:
        out["host_verification"] = host_verification
    out["share_state"] = "local_result"  # not pool-accepted
    out["validity_oracle"] = "sha256d_reverify_required"
    return out
