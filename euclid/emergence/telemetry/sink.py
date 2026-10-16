"""Immutable append-only telemetry stream and hash-chained audit sink."""

from __future__ import annotations
from dataclasses import dataclass
import hashlib
import time
from typing import List, Optional, Tuple

from ..models.telemetry import TelemetryRecord, TelemetrySignatureInfo


@dataclass(frozen=True)
class TelemetryBlock:
    """An immutable, cryptographically chained block in the telemetry audit ledger."""
    block_index: int
    timestamp: float
    record: TelemetryRecord
    signature_info: TelemetrySignatureInfo
    previous_block_hash: str
    block_hash: str

    def verify_hash(self) -> bool:
        payload = f"{self.block_index}:{self.previous_block_hash}:{self.record.compute_digest()}:{self.signature_info.signature_hex}"
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return hmac_compare(expected, self.block_hash)


def hmac_compare(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a, b)


class TelemetryStream:
    """Append-only telemetry sink with hash-chained integrity verification and access control."""

    GENESIS_HASH = "0" * 64

    def __init__(self, stream_id: str = "default_telemetry_stream", max_retention_records: int = 100_000):
        self.stream_id = stream_id
        self.max_retention_records = max_retention_records
        self._blocks: List[TelemetryBlock] = []

    def append(self, record: TelemetryRecord, signature_info: TelemetrySignatureInfo) -> TelemetryBlock:
        prev_hash = self._blocks[-1].block_hash if self._blocks else self.GENESIS_HASH
        block_idx = len(self._blocks)
        now = time.time()

        payload = f"{block_idx}:{prev_hash}:{record.compute_digest()}:{signature_info.signature_hex}"
        block_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        block = TelemetryBlock(
            block_index=block_idx,
            timestamp=now,
            record=record,
            signature_info=signature_info,
            previous_block_hash=prev_hash,
            block_hash=block_hash,
        )
        self._blocks.append(block)

        if len(self._blocks) > self.max_retention_records:
            self._blocks.pop(0)

        return block

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        if not self._blocks:
            return True, None

        for i, block in enumerate(self._blocks):
            if i == 0 and block.previous_block_hash != self.GENESIS_HASH and block.block_index == 0:
                return False, f"Genesis block mismatch at index 0"

            if i > 0 and block.previous_block_hash != self._blocks[i - 1].block_hash:
                return False, f"Hash-chain broken at block {i}: prev_hash mismatch"

            if not block.verify_hash():
                return False, f"Hash verification failed at block {i}"

        return True, None

    def get_records(self) -> List[TelemetryRecord]:
        return [b.record for b in self._blocks]

    def count(self) -> int:
        return len(self._blocks)
