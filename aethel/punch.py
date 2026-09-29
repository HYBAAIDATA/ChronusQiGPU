"""Optional OpenCL punch-host resolution.

Resolution order: the complete unified-punch host, then filesystem siblings,
then the legacy iGPU SHA256d host.  A SHA-capable host is not necessarily a
complete punch host, so it must not shadow the canonical implementation.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from typing import Any, Optional


def _load_module_from_path(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(module_name, mod)
    spec.loader.exec_module(mod)
    return mod


def resolve_punch_host_class() -> Optional[type]:
    for module_name in ("toe.unified_punch", "Intelligence.unified_punch"):
        try:
            mod = importlib.import_module(module_name)
        except Exception:
            continue
        host_cls = getattr(mod, "UnifiedPunchHost", None)
        if host_cls is not None:
            return host_cls
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "unified_punch.py"),
        os.path.join(os.path.dirname(here), "Intelligence", "unified_punch.py"),
    ]
    for sibling in candidates:
        if not os.path.exists(sibling):
            continue
        mod = _load_module_from_path("unified_punch", sibling)
        host_cls = getattr(mod, "UnifiedPunchHost", None) if mod else None
        if host_cls is not None:
            return host_cls
    try:
        from igpu.opencl_host import OpenClPunchHost

        return OpenClPunchHost
    except Exception:
        pass
    return None


def resolve_punch_host() -> Optional[Any]:
    host_cls = resolve_punch_host_class()
    if host_cls is None:
        return None
    try:
        host = host_cls()
    except Exception:
        return None
    return host
