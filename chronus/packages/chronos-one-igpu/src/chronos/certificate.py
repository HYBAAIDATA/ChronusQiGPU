"""Backend-bound certificate and measured/modelled classification."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, hmac, json
from .adapters.base import ExecutionReceipt

@dataclass(frozen=True)
class ExtendedCertificate:
    rung: int
    value: int
    mask: int
    prime: int
    cassini: bool
    operation: str
    backend_name: str
    backend_kind: str
    device_id: str
    kernel_digest: str
    pipeline_spec: str
    execution_mode: str
    latency_cycles: int | None
    throughput_rps: float
    power_watts: float | None
    classification: str
    digest: str
    signature: str | None = None

def bind_record(record, receipt: ExecutionReceipt, execution_mode: str) -> ExtendedCertificate:
    classification = "MEASURED" if receipt.measured else "MODELED"
    payload = {
        "rung": record.rung, "value": record.value, "mask": record.zeckendorf_mask,
        "prime": record.prime_address, "cassini": record.cassini_pass,
        "operation": "lucas-pipeline", "backend": receipt.backend,
        "kind": receipt.backend_kind, "device": receipt.device_id,
        "kernel": receipt.kernel_digest, "spec": receipt.pipeline_spec,
        "mode": execution_mode, "latency": receipt.latency_cycles,
        "throughput": receipt.throughput_rps, "power": receipt.power_watts,
        "classification": classification,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ExtendedCertificate(record.rung, record.value, record.zeckendorf_mask, record.prime_address, record.cassini_pass, "lucas-pipeline", receipt.backend, receipt.backend_kind, receipt.device_id, receipt.kernel_digest, receipt.pipeline_spec, execution_mode, receipt.latency_cycles, receipt.throughput_rps, receipt.power_watts, classification, digest)

def sign_certificate(cert: ExtendedCertificate, secret: bytes) -> ExtendedCertificate:
    sig = hmac.new(secret, cert.digest.encode(), hashlib.sha256).hexdigest()
    return ExtendedCertificate(**{**asdict(cert), "signature": sig})

def verify_signature(cert: ExtendedCertificate, secret: bytes) -> bool:
    return cert.signature == hmac.new(secret, cert.digest.encode(), hashlib.sha256).hexdigest()
