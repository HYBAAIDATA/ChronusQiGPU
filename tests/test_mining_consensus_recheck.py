from __future__ import annotations

import pytest

from mining.hash_pipeline import HashPipeline


class MaliciousHasher:
    """Backend fixture that falsely reports a winning nonce and digest."""

    backend = "malicious-test-backend"
    device = "fixture"

    def grind_target_batch(self, header80, target_be, nonces):
        nonce = int(list(nonces)[0])
        return nonce, bytes(32), 1


def test_backend_candidate_must_survive_independent_sha256d_recheck():
    pipeline = HashPipeline(hasher=MaliciousHasher())
    with pytest.raises(
        RuntimeError,
        match="backend candidate failed independent SHA-256d target recheck",
    ):
        pipeline.grind(
            bytes(80),
            b"\xff" * 32,
            [1],
        )
