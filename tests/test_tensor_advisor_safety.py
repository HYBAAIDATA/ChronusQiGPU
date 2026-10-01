"""Mining advisory boundary: mutation attacks must fail closed.

Exercised through ``tensor.advisor``, the re-export consumed by production
code going forward, over the same certified-window contract used by
``hyba.hybrid.tensor_advisor`` (see tests/test_three_layer_runtime.py for
the canonical-module coverage of the identical rule).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from hyba.hybrid.lucas_partition import SpanAssignment
from tensor.advisor import TensorAdviceViolation, apply_tensor_advice


def _windows():
    return [
        SpanAssignment("gpu-1", 0, 10, 0),
        SpanAssignment("asic-1", 10, 20, 1),
        SpanAssignment("igpu-1", 30, 5, 2),
    ]


class _Ranker:
    model_id = "attack-v1"

    def __init__(self, mutate):
        self._mutate = mutate

    def rank(self, job, windows):
        del job
        return self._mutate(list(windows))


def test_pure_reorder_is_accepted():
    windows = _windows()
    reordered, evidence = apply_tensor_advice(
        _Ranker(lambda ws: list(reversed(ws))), object(), windows
    )
    assert sorted(reordered, key=lambda w: w.base_nonce) == sorted(
        windows, key=lambda w: w.base_nonce
    )
    assert evidence.permutation_valid is True
    assert evidence.as_dict()["effect"] == "dispatch_order_only"


def test_duplicate_window_is_rejected():
    windows = _windows()
    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(lambda ws: [ws[0], *ws]), object(), windows)


def test_removed_window_is_rejected():
    windows = _windows()
    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(lambda ws: ws[:-1]), object(), windows)


def test_added_window_is_rejected():
    windows = _windows()
    extra = SpanAssignment("gpu-2", 40, 5, 3)
    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(lambda ws: [*ws, extra]), object(), windows)


def test_resized_window_is_rejected():
    windows = _windows()

    def mutate(ws):
        ws[0] = replace(ws[0], span=ws[0].span + 1)
        return ws

    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(mutate), object(), windows)


def test_retargeted_base_nonce_is_rejected():
    windows = _windows()

    def mutate(ws):
        ws[0] = replace(ws[0], base_nonce=ws[0].base_nonce + 1)
        return ws

    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(mutate), object(), windows)


def test_reassigned_device_is_rejected():
    windows = _windows()

    def mutate(ws):
        ws[0] = replace(ws[0], device_id="someone-elses-device")
        return ws

    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(mutate), object(), windows)


def test_reassigned_face_is_rejected():
    windows = _windows()

    def mutate(ws):
        ws[0] = replace(ws[0], face=ws[0].face + 1)
        return ws

    with pytest.raises(TensorAdviceViolation):
        apply_tensor_advice(_Ranker(mutate), object(), windows)


def test_empty_model_id_is_rejected():
    class _BlankRanker:
        model_id = "   "

        def rank(self, job, windows):
            del job
            return list(windows)

    with pytest.raises(TensorAdviceViolation, match="model_id"):
        apply_tensor_advice(_BlankRanker(), object(), _windows())
