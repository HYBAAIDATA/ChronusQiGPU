"""Regression tests for deterministic production work ordering."""

from __future__ import annotations

import pytest

from Intelligence.four_layer_stack import ordering_mode_for_window
from mining.hash_pipeline import HashPipeline, double_sha256, nonce_order_fingerprint


class _FakeHasher:
    backend = "cpu"
    device = "test-cpu"
    kernel_ms = 0.0
    launches = 0

    def grind_target_batch(self, _header, _target, candidate_nonces):
        winner = int(candidate_nonces[0]) if len(candidate_nonces) else None
        win_hash = None
        if winner is not None:
            win_hash = double_sha256(_header[:76] + winner.to_bytes(4, "little"))
        return winner, win_hash, len(candidate_nonces)


def test_ordering_cutover_is_explicit_and_inclusive() -> None:
    assert ordering_mode_for_window(4095) == "amplitude-score-stable"
    assert ordering_mode_for_window(4096) == "amplitude-score-stable"
    assert ordering_mode_for_window(4097) == "deterministic-turing"
    assert ordering_mode_for_window(5000) == "deterministic-turing"


def test_preordered_grind_does_not_score_again() -> None:
    pipe = HashPipeline(host=object(), hasher=_FakeHasher())
    nonces = [7, 8, 9]
    result = pipe.grind(
        bytes(80),
        b"\xff" * 32,
        nonces,
        preordered=True,
        sealed_fingerprint=nonce_order_fingerprint(nonces),
    )

    assert result.winning_nonce == 7
    assert result.hashes_computed == 3
    assert result.candidates_scored == 3
    assert result.candidates_passed_filter == 3
    assert result.scoring_backend == "preordered"
    assert result.scoring_device == "deterministic-schedule"


def test_preordered_grind_requires_and_verifies_content_seal() -> None:
    pipe = HashPipeline(host=None, hasher=_FakeHasher())
    nonces = [19, 3, 11]

    with pytest.raises(ValueError, match="requires sealed_fingerprint"):
        pipe.grind(bytes(80), b"\x00" * 32, nonces, preordered=True)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        pipe.grind(
            bytes(80),
            b"\x00" * 32,
            nonces,
            preordered=True,
            sealed_fingerprint=nonce_order_fingerprint([19, 11, 3]),
        )


def test_preordered_grind_preserves_schedule_order() -> None:
    pipe = HashPipeline(host=None, hasher=_FakeHasher())
    nonces = [19, 3, 11]
    seen: list[int] = []

    def observe(_header, _target, candidate_nonces):
        seen.extend(int(nonce) for nonce in candidate_nonces)
        return None, None, len(candidate_nonces)

    pipe._grind_in_order = observe  # type: ignore[method-assign]
    result = pipe.grind(
        bytes(80),
        b"\x00" * 32,
        nonces,
        preordered=True,
        sealed_fingerprint=nonce_order_fingerprint(nonces),
    )

    assert seen == nonces
    assert result.winning_nonce is None
    assert result.hashes_computed == 3


def test_backend_candidate_cannot_bypass_consensus_recheck() -> None:
    class LyingHasher(_FakeHasher):
        def __init__(self):
            self.backend = "cpu"
            self.device = "lying-test"
            self.kernel_ms = 0.0
            self.launches = 0

    pipe = HashPipeline(host=None, hasher=LyingHasher())
    pipe._grind_in_order = lambda *_args: (0, b"\x00" * 32, 1)  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="independent SHA-256d"):
        pipe.grind(bytes(80), b"\xff" * 32, [0])


def test_contiguous_m32_window_uses_exact_lane_path() -> None:
    class M32Hasher(_FakeHasher):
        def __init__(self):
            self.backend = "opencl:gpu"
            self.device = "m32-test"
            self.kernel_ms = 0.0
            self.launches = 0
            self.called = False

        def grind_target_m32(self, _header, _target, base_nonce, lane_order, count):
            self.called = True
            assert base_nonce == 0
            assert count == 64
            assert len(lane_order) == 32
            return None, None, count

        def grind_target_batch(self, *_args):
            raise AssertionError("aligned M32 window should not fall back to batch order")

    hasher = M32Hasher()
    pipe = HashPipeline(host=None, hasher=hasher)
    result = pipe.grind(bytes(80), b"\x00" * 32, list(range(64)))

    assert hasher.called
    assert result.hashes_computed == 64
    assert result.scoring_backend == "m32-device-order"
