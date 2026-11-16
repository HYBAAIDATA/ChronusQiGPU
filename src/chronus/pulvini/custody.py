"""PULVINI V3 complete-fold artifact custody on canonical OVID/THESEUS.

Unlike the archived standalone audit ledger, this adapter uses ProductionTriad
for durable custody. Every residual kernel is serialised. No claim of physical
compression, external authentication or tenant authorization is made here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import struct

import numpy as np

from chronus.config import runtime_bounds
from chronus.pulvini import FoldEvidence, FoldState, unfold_verified
from chronus.tensor.folded_compute import FoldedTensorExecutor, VerifiedFoldedOperand
from chronus.triad import ProductionTriad, TriadReceipt

MAGIC = b"PVF1"
MAX_HEADER = 8192


@dataclass(frozen=True)
class PulviniCustodyRecord:
    triad_receipt: TriadReceipt
    artifact_sha256: str
    original_sha256: str
    fold_depth: int


def encode_complete_fold(operand: VerifiedFoldedOperand) -> bytes:
    if not isinstance(operand, VerifiedFoldedOperand):
        raise ValueError("verified complete fold required")
    state, evidence = operand.state, operand.evidence
    if state.depth != evidence.depth or state.normalization != evidence.normalization:
        raise ValueError("fold chronology and receipt disagree")
    unfolded = unfold_verified(state, receipt=evidence)
    if not np.all(np.isfinite(unfolded)):
        raise ValueError("non-finite original")
    dtype = state.folded.dtype
    if dtype not in (np.dtype('float64'), np.dtype('complex128')):
        raise ValueError("unsupported fold scalar dtype")
    if any(k.dtype != dtype for k in state.kernels):
        raise ValueError("mixed kernel dtype")
    arrays = (state.folded, *state.kernels)
    header = {
        "schema": "chronus.pulvini.complete-fold/1",
        "normalization": state.normalization,
        "sizes": list(state.sizes),
        "original_shape": list(state.original_shape),
        "original_dtype": state.original_dtype,
        "scalar_dtype": dtype.str,
        "array_lengths": [int(a.size) for a in arrays],
        "evidence": asdict(evidence),
    }
    raw_header = json.dumps(header, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw_header) > MAX_HEADER:
        raise ValueError("fold envelope exceeds header policy")
    return MAGIC + struct.pack('>I', len(raw_header)) + raw_header + b''.join(
        np.ascontiguousarray(a).tobytes() for a in arrays
    )


def decode_complete_fold(payload: bytes, *, max_elements: int = 1_000_000) -> VerifiedFoldedOperand:
    if not isinstance(payload, bytes) or len(payload) < 12 or payload[:4] != MAGIC:
        raise ValueError("invalid complete-fold artifact")
    hlen = struct.unpack('>I', payload[4:8])[0]
    if not 0 < hlen <= MAX_HEADER or len(payload) < hlen + 8:
        raise ValueError("fold header bound violation")
    h = json.loads(payload[8:8+hlen])
    if not isinstance(h, dict) or h.get('schema') != 'chronus.pulvini.complete-fold/1':
        raise ValueError("unrecognised fold contract")
    sizes = h.get('sizes')
    lengths = h.get('array_lengths')
    shape = h.get('original_shape')
    if (not isinstance(sizes, list) or not 1 <= len(sizes) <= 33 or
        not isinstance(lengths, list) or len(lengths) != len(sizes) or
        not isinstance(shape, list) or not 0 <= len(shape) <= 8 or
        any(type(x) is not int or x < 1 for x in sizes) or
        any(type(x) is not int or x < 0 for x in lengths) or
        any(type(x) is not int or x < 1 for x in shape) or
        sizes[0] > max_elements or math.prod(shape) != sizes[0] or
        lengths[0] != sizes[-1]):
        raise ValueError("invalid fold geometry")
    dtype = np.dtype(h.get('scalar_dtype'))
    if dtype not in (np.dtype('float64'), np.dtype('complex128')):
        raise ValueError("unsupported fold dtype")
    expected_size = sum(lengths) * dtype.itemsize
    if len(payload) != 8 + hlen + expected_size:
        raise ValueError("fold payload length mismatch")
    values = []
    offset = 8 + hlen
    for length in lengths:
        n = length * dtype.itemsize
        values.append(np.frombuffer(payload[offset:offset+n], dtype=dtype).copy())
        offset += n
    state = FoldState(folded=values[0], kernels=tuple(values[1:]),
                      sizes=tuple(sizes), original_shape=tuple(shape),
                      original_dtype=h.get('original_dtype'),
                      normalization=h.get('normalization'))
    data = h.get('evidence')
    if not isinstance(data, dict):
        raise ValueError("missing fold receipt")
    evidence = FoldEvidence(**data)
    if evidence.retained_bytes != expected_size or evidence.depth != state.depth:
        raise ValueError("retained accounting invalid")
    # Full reconstruction and original digest check are mandatory before return.
    unfolded = unfold_verified(state, receipt=evidence)
    if unfolded.size != sizes[0]:
        raise ValueError("recovery changed element count")
    return VerifiedFoldedOperand(state=state, evidence=evidence)


class PulviniCustodyAdapter:
    """Authenticated callers supply a ProductionTriad; no second ledger."""

    def __init__(self, triad: ProductionTriad, *, depth: int = 4,
                 max_elements: int = 1_000_000):
        self.triad = triad
        self.executor = FoldedTensorExecutor(depth=depth, max_elements=max_elements)

    def put(self, tenant_id: str, data: np.ndarray) -> PulviniCustodyRecord:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id required")
        operand = self.executor.fold(data)
        encoded = encode_complete_fold(operand)
        limit = runtime_bounds()["max_payload_bytes"]
        if len(encoded) + (len(encoded) & 1) > limit:
            raise ValueError("folded artifact exceeds THESEUS configured payload bound")
        receipt = self.triad.put(tenant_id, encoded)
        if self.triad.verify(receipt) is not True:
            raise ValueError("custody verification failed")
        return PulviniCustodyRecord(receipt,
                                   hashlib.sha256(encoded).hexdigest(),
                                   operand.evidence.input_sha256,
                                   operand.state.depth)

    def read(self, record: PulviniCustodyRecord) -> VerifiedFoldedOperand:
        if not isinstance(record, PulviniCustodyRecord):
            raise ValueError("record required")
        if self.triad.verify(record.triad_receipt) is not True:
            raise ValueError("custody continuity not verified")
        content = self.triad.materialise(record.triad_receipt)
        if hashlib.sha256(content).hexdigest() != record.artifact_sha256:
            raise ValueError("custody fold artifact hash mismatch")
        operand = decode_complete_fold(content, max_elements=self.executor.max_elements)
        if operand.evidence.input_sha256 != record.original_sha256 or operand.state.depth != record.fold_depth:
            raise ValueError("source digest/depth mismatch")
        return operand
