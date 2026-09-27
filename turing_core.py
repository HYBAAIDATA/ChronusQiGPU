"""Repository entrypoint for the shared zero-external-dependency Turing mathematics.

The installed implementation lives with the canonical runtime. Both import layouts
expose the same mathematical objects; the root retains its legacy probe schedule.
"""

import importlib.util
import sys
from pathlib import Path

_python = Path(__file__).parent / "mla1517_platform_v3.4" / "python"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_math = _load("pythia_turing_math", _python / "pythia_turing_math.py")
for _name in dir(_math):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_math, _name)
_schedule = _load("_mla1517_turing_schedule", _python / "turing_core.py")
TuringScheduleError = _schedule.TuringScheduleError
iter_nonce_schedule = _schedule.iter_nonce_schedule
validate_schedule = _schedule.validate_schedule
complete_nonce_schedule = _schedule.complete_nonce_schedule

if __name__ == "__main__":
    _math.run_self_verification()
    print("[PASS] TURING & PYTHIA core self-verification")
