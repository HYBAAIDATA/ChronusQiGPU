"""Canonical router adapter for the separately installed Chronos ONE iGPU."""

from __future__ import annotations

import hashlib


class ChronusOneIGPUHasher:
    @property
    def backend(self):
        if self.last_batch_evidence and self.last_batch_evidence.get("physical_device_executed"):
            return self.last_batch_evidence["backend"] + ":chronus_one_igpu"
        return "chronus_one_igpu"

    vendor = None
    device = "Chronos ONE iGPU"
    grind_batch = 4096
    k_gold = k_m32 = k_range = None

    def __init__(self, igpu, *, current_epoch=None):
        self.igpu = igpu
        self.current_epoch = current_epoch
        self.launches = 0
        self.kernel_ms = 0.0
        self.physical_device_executed = False
        self.last_batch_evidence = None

    def grind_target_hendrix_plan(self, header, target_be, artifact, position, count):
        from chronus.igpu.execution_identity import verify_contract, verify_receipt
        verify_contract(artifact["execution_contract"],self.igpu)
        result = self.igpu.execute_hendrix(
            artifact,
            header,
            target_be,
            position=position,
            count=count,
            current_epoch=self.current_epoch,
        )
        verify_receipt(result,artifact,igpu=self.igpu)
        self.last_batch_evidence = result
        self.physical_device_executed = bool(result["physical_device_executed"])
        self.launches += int(result["kernel_launch_count"])
        self.kernel_ms += result.get("kernel_seconds", 0.0) * 1000
        nonce = result["nonce"]
        return (
            nonce,
            bytes.fromhex(result["digest"]) if nonce is not None else None,
            result["sha256d_evaluations"],
        )

    def grind_target_batch(self, header, target_be, nonces):
        """Explicit compatibility batches; no contiguous-order substitution."""
        result = self.igpu.execute_nonce_batch(header, target_be, nonces)
        self.physical_device_executed = bool(result["physical_device_executed"])
        self.launches += int(result["kernel_launch_count"])
        self.last_batch_evidence = result
        nonce = result["nonce"]
        return (
            nonce,
            bytes.fromhex(result["digest"]) if nonce is not None else None,
            result["sha256d_evaluations"],
        )

    def self_check(self):
        header = bytes(range(80))
        nonce, digest, done = self.grind_target_batch(header, b"\xff" * 32, [3, 1])
        expected = hashlib.sha256(
            hashlib.sha256(header[:76] + (3).to_bytes(4, "little")).digest()
        ).digest()
        if nonce != 3 or digest != expected or not 1 <= done <= 2:
            raise RuntimeError("ONE iGPU ordered-batch self-check failed")
