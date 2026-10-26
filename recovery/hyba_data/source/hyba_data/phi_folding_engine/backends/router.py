"""Compatibility shim — canonical implementation moved to `pulvini.folding_engine.backends.router`.

This stub will be removed after one governed deprecation cycle.
"""
from __future__ import annotations

import importlib as _importlib
import sys as _sys

_canonical = _importlib.import_module('pulvini.folding_engine.backends.router')
for _name, _val in vars(_canonical).items():
    if _name.startswith('_') and _name not in {'__all__', '__doc__', '__version__'}:
        continue
    globals()[_name] = _val
__all__ = getattr(_canonical, '__all__', [k for k in vars(_canonical) if not k.startswith('_')])
__canonical_module__ = 'pulvini.folding_engine.backends.router'

def __getattr__(name: str):
    return getattr(_canonical, name)

def __dir__():
    return sorted(set(globals()) | set(dir(_canonical)))
