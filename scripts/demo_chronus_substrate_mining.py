"""Run a bounded Chronus/substrate ordering pass through real SHA-256d."""

from __future__ import annotations

import json
import struct

from mining.hash_pipeline import HashPipeline, double_sha256


class ReferenceHasher:
    backend = "cpu-reference"
    device = "hashlib.sha256d"
    kernel_ms = 0.0
    launches = 0

    def grind_target_batch(self, header80, target_be, nonces):
        self.launches += 1
        checked = 0
        for raw in nonces:
            nonce = int(raw)
            digest = double_sha256(header80[:76] + struct.pack("<I", nonce))
            checked += 1
            if digest[::-1] <= target_be:
                return nonce, digest, checked
        return None, None, checked


def main() -> int:
    candidates = list(range(256))
    pipeline = HashPipeline(host=object(), hasher=ReferenceHasher())
    result, evidence = pipeline.grind_with_chronus_substrate(
        bytes(80),
        bytes.fromhex("00" + "ff" * 31),
        candidates,
        fold_depth=1,
        seed=0,
    )
    payload = {
        "status": "PASS",
        "hashes_computed": result.hashes_computed,
        "winning_nonce": result.winning_nonce,
        "backend": result.backend,
        "ordering": evidence.to_dict(),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())