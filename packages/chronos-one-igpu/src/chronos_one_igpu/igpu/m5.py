"""Bind the canonical M5 descriptor to ONE iGPU, never to invented hardware.

M5 pad specifications remain evidence-labelled algebra/model inputs. Work is
executed and independently checked by the existing ResidentRuntime. No model
core count, bandwidth, Hilbert dimension or AI projection becomes a capability
or a measured multiplier. PYTHIA's sealed mining plans are unchanged.
"""
from __future__ import annotations

import hashlib
from ..m5_ultra import PadFabric, m5_ultra_fabric
from .resident import ResidentConfig, ResidentRuntime, canonical


def model_digest(model):
    if not isinstance(model, PadFabric):
        raise TypeError("canonical M5 PadFabric required")
    return hashlib.sha256(canonical(model.as_dict())).hexdigest()


class M5ResidentRuntime:
    """Immutable model snapshot plus a bounded resident execution session."""

    def __init__(self, gpu, config=None, model=None):
        model = m5_ultra_fabric() if model is None else model
        if not isinstance(model, PadFabric):
            raise TypeError("canonical M5 PadFabric required")
        # A descriptor must not certify itself as measured execution.
        if model.measured_by_chronus:
            raise ValueError("M5 descriptor is not execution evidence")
        self._quantum_model = model
        self._model_bytes = canonical(model.as_dict())
        self._model_digest = model_digest(model)
        self.resident = gpu.resident(
            config if config is not None else ResidentConfig(host_binding="native")
        )

    def manifest(self):
        import json
        return {
            "schema": "chronos_m5_resident/1",
            "model": json.loads(self._model_bytes),
            "model_digest": self._model_digest,
            "model_is_execution_evidence": False,
            "resident": self.resident.manifest(),
            "physical_throughput_multiplier": None,
            "host_gpu_qualification": "UNQUALIFIED",
            "mining_authority": "PYTHIA",
            "executor_authority": "CHRONUS",
        }

    def execute(self, kind, payload, **kwargs):
        result = self.resident.execute(kind, payload, **kwargs)
        receipt = {
            "schema": "chronos_m5_execution/1",
            "model_digest": self._model_digest,
            "model_is_execution_evidence": False,
            "execution": result,
        }
        receipt["receipt_digest"] = hashlib.sha256(canonical(receipt)).hexdigest()
        self.verify(receipt, payload)
        return receipt

    def verify(self, receipt, payload):
        if not isinstance(receipt, dict) or set(receipt) != {
            "schema", "model_digest", "model_is_execution_evidence", "execution",
            "receipt_digest",
        }:
            raise ValueError("M5 receipt contract mismatch")
        body = dict(receipt)
        digest = body.pop("receipt_digest")
        if digest != hashlib.sha256(canonical(body)).hexdigest():
            raise ValueError("M5 receipt digest mismatch")
        if (receipt["schema"] != "chronos_m5_execution/1"
                or receipt["model_digest"] != self._model_digest
                or receipt["model_is_execution_evidence"] is not False):
            raise ValueError("M5 model/execution identity mismatch")
        return ResidentRuntime.verify(receipt["execution"], payload)

    def execute_quantum(self, algorithm, *, require_host_gpu=False):
        from ..adapters.base import BackendAbsent
        from .m5_quantum import execute_quantum
        if type(require_host_gpu) is not bool:
            raise ValueError("explicit physical execution policy required")
        if require_host_gpu:
            raise BackendAbsent("exact M5 gate algebra has no qualified physical GPU executor")
        return execute_quantum(self._quantum_model, algorithm)

    def verify_quantum(self, receipt, algorithm):
        from .m5_quantum import verify_quantum
        return verify_quantum(receipt, self._quantum_model, algorithm)
