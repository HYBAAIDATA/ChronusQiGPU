"""Production mining execution hasher backed by the Chronus Virtual iGPU.

PYTHIA authorises an exact ordered nonce batch; this hasher submits it to
Chronus as a ``SHA256D_SCAN`` workload and independently re-verifies every
returned candidate on the host. PYTHIA keeps search/plan authority; Chronus
only executes. Any failure raises, so the execution router records a
fail-closed DEVICE_ERROR rather than a result.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Sequence

from .abi import ExecutionPolicy, Workload, WorkloadKind
from .client import ChronusClient
from .host_verify import CandidateVerificationError, sha256d, verify_hits

_KNOWN_HEADER = bytes(range(80))


class ChronusVirtualIGPUHasher:
    """Router-facing hasher (``grind_target_batch``) over ``ChronusClient``."""

    backend = "chronus_vigpu"
    vendor = None
    k_gold = k_m32 = k_range = None

    def __init__(
        self,
        client: ChronusClient | None = None,
        *,
        tenant: str = "mining",
        execution_policy: str = ExecutionPolicy.PREFERRED_ACCELERATOR.value,
        allow_software_fallback: bool = True,
        grind_batch: int = 1 << 16,
    ) -> None:
        if not 0 < int(grind_batch) <= 1_000_000:
            raise ValueError("grind_batch must be in 1..1_000_000")
        self.client = client or ChronusClient()
        self.tenant = tenant
        self.execution_policy = execution_policy
        self.allow_software_fallback = allow_software_fallback
        self.grind_batch = int(grind_batch)
        self.launches = 0
        self.kernel_ms = 0.0
        self.device = "Chronus Virtual iGPU (unbound)"
        self.fallback_reason: str | None = None
        self.last_result: dict[str, Any] | None = None
        self.last_adapter_kind: str | None = None
        self.last_verification: dict[str, Any] | None = None

    @property
    def physical_device_executed(self) -> bool:
        """True only when the last executing adapter was not the software emulator."""
        return bool(self.last_adapter_kind) and self.last_adapter_kind != "software"

    def _submit(self, header: bytes, target_be: bytes, nonces: list[int]) -> dict[str, Any]:
        workload = Workload(
            id=str(uuid.uuid4()),
            kind=WorkloadKind.SHA256D_SCAN,
            tenant=self.tenant,
            input={
                "header80_hex": bytes(header).hex(),
                "target_hex": bytes(target_be).hex(),
                "nonces": nonces,
            },
            execution_policy=self.execution_policy,
            allow_software_fallback=self.allow_software_fallback,
        )
        result = self.client.submit(workload)
        if result.status != "ok":
            raise RuntimeError(f"Chronus execution did not succeed: {result.status}")
        self.launches += 1
        self.kernel_ms += float(result.device_time_ns or 0) / 1e6
        adapter_id = result.actual_adapter_id or result.adapter_id
        self.last_adapter_kind = "software" if adapter_id == "cpu-emulator" else adapter_id
        self.device = f"Chronus Virtual iGPU ({adapter_id})"
        self.last_result = result.to_dict()
        return dict(result.output or {})

    def grind_target_batch(
        self, header80: bytes, target_be: bytes, nonces: Sequence[int]
    ) -> tuple[int | None, bytes | None, int]:
        header = bytes(header80)
        if len(header) != 80:
            raise ValueError("header80 must be exactly 80 bytes")
        batch = [int(n) for n in nonces]
        if not batch:
            return None, None, 0
        target_int = int.from_bytes(bytes(target_be), "big")
        done = 0
        started = time.perf_counter()
        for offset in range(0, len(batch), self.grind_batch):
            part = batch[offset : offset + self.grind_batch]
            output = self._submit(header, target_be, part)
            hits = list(output.get("hits") or ())
            checked = int(output.get("checked") or 0)
            if not hits and checked != len(part):
                raise CandidateVerificationError(
                    f"Chronus checked {checked} nonces; expected {len(part)}"
                )
            verified = verify_hits(header[:76], hits, target_int, allowed_nonces=set(part))
            self.last_verification = {
                "oracle": "host_hashlib_sha256d",
                "status": "passed",
                "verified_hits": len(verified),
                "wall_s": time.perf_counter() - started,
            }
            if verified:
                hit = verified[0]
                nonce = int(hit["nonce"])
                digest = sha256d(header[:76] + nonce.to_bytes(4, "little"))
                return nonce, digest, done + max(1, checked)
            done += checked
        return None, None, done

    def self_check(self) -> None:
        """Execute a real known-answer workload; raise if Chronus cannot run it correctly."""
        header = _KNOWN_HEADER
        nonces = [0, 1, 2, 3]
        target = b"\xff" * 32
        nonce, digest, done = self.grind_target_batch(header, target, nonces)
        expected = sha256d(header[:76] + (0).to_bytes(4, "little"))
        if nonce != 0 or digest != expected or done < 1:
            raise CandidateVerificationError("Chronus Virtual iGPU known-answer self-check failed")


__all__ = ["ChronusVirtualIGPUHasher"]
