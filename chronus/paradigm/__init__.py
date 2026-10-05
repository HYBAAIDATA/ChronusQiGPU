"""Paradigm spine — Chronus virtual accelerator systems core.

Chronus is HYBA's GPU offering. This package freezes the systems thesis,
conformance triad, schedule bakeoff, and honesty gates.

Public thesis (frozen in ``thesis.THESIS``):

    Chronus provides a versioned, fail-closed virtual accelerator ABI whose
    receipts bind workload, backend, digest, and trust class; algebraic
    schedules may reorder classical work but never substitute for SHA256d
    or pool acknowledgement.

Triad (must all pass for the spine to be green):

1. **Lemma** — golden-stride bijection (ordering only; theorem_proven pinned).
2. **Systems** — virtual_igpu_v1 conformance (ABI, policy, trust, evidence).
3. **Measurement** — schedule bakeoff with honest negative-result reporting.
4. **Honesty** — chaos cases (tamper, quota, liar hardware root).

Run::

    python -m chronus.paradigm
    python -m pytest tests/test_paradigm_spine.py -q
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "THESIS": ("chronus.paradigm.thesis", "THESIS"),
    "THESIS_ID": ("chronus.paradigm.thesis", "THESIS_ID"),
    "assert_thesis_bounds": ("chronus.paradigm.thesis", "assert_thesis_bounds"),
    "run_triad": ("chronus.paradigm.triad", "run_triad"),
    "TriadReport": ("chronus.paradigm.triad", "TriadReport"),
    "run_bakeoff": ("chronus.paradigm.bakeoff", "run_bakeoff"),
    "run_conformance": ("chronus.paradigm.conformance", "run_conformance"),
    "run_honesty_chaos": ("chronus.paradigm.honesty", "run_honesty_chaos"),
    "ScheduleName": ("chronus.paradigm.schedules", "ScheduleName"),
    "nonce_walk": ("chronus.paradigm.schedules", "nonce_walk"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    mod_name, attr = _EXPORTS[name]
    value = getattr(import_module(mod_name), attr)
    globals()[name] = value
    return value
