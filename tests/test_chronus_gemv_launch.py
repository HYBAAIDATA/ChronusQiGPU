"""GEMV launches: global range padded to the local size, args bound to the kernel."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from chronus.engine import ResidentChronusEnsemble, ResidentChronusState, _round_to_local


class _Kernel:
    def __init__(self, calls: list, name: str) -> None:
        self._calls = calls
        self._name = name

    def __call__(self, queue, global_size, local_size, *args) -> None:
        self._calls.append((self._name, global_size, local_size, len(args)))


class _FakeEngine:
    uses_fp64 = True

    def __init__(self, local: int) -> None:
        self.calls: list = []
        self._local = local
        self.cl = SimpleNamespace(
            mem_flags=SimpleNamespace(READ_ONLY=1, READ_WRITE=2),
            Buffer=lambda ctx, flags, nbytes: object(),
        )
        self.context = object()
        self.queue = SimpleNamespace(finish=lambda: None)

    def program(self, _source, _options):
        return SimpleNamespace(
            cgemv_lr=_Kernel(self.calls, "cgemv_lr"),
            cgemv_batch=_Kernel(self.calls, "cgemv_batch"),
        )

    def default_local_size(self, _kernel, _requested=None) -> int:
        return self._local

    def write_buffer(self, _buffer, _array, _offset) -> None:
        return None

    def read_buffer(self, _buffer, array, _offset):
        return array


def test_round_to_local():
    assert _round_to_local(1, 64) == 64
    assert _round_to_local(64, 64) == 64
    assert _round_to_local(65, 64) == 128
    assert _round_to_local(100, 32) == 128


def test_state_apply_pads_global_range_and_binds_args():
    engine = _FakeEngine(local=64)
    state = ResidentChronusState(100, engine=engine)
    state.apply(np.eye(100))
    assert engine.calls == [("cgemv_lr", (128,), (64,), 7)]


def test_ensemble_apply_pads_global_range_and_binds_args():
    engine = _FakeEngine(local=32)
    ensemble = ResidentChronusEnsemble(5, 3, engine=engine)
    ensemble.apply()
    assert engine.calls == [("cgemv_batch", (32,), (32,), 8)]
