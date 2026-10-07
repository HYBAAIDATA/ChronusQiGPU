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


class MaliciousM32Hasher:
    """M32 backend fixture that falsely reports a winning nonce and digest."""

    backend = "malicious-m32-test-backend"
    device = "fixture"

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        return int(base_nonce), bytes(32), int(count)


def test_m32_backend_candidate_must_survive_independent_sha256d_recheck():
    pipeline = HashPipeline(hasher=MaliciousM32Hasher())
    with pytest.raises(
        RuntimeError,
        match="backend candidate failed independent SHA-256d target recheck",
    ):
        pipeline.grind_m32(
            bytes(80),
            b"\xff" * 32,
            0,
            tuple(range(32)),
            32,
        )
