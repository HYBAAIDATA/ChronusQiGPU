# tests/benchmarks package marker
import pkgutil
from pathlib import Path
__path__ = pkgutil.extend_path(__path__, __name__)
_root_bench = str(Path(__file__).resolve().parent.parent.parent / "benchmarks")
if _root_bench not in __path__:
    __path__.append(_root_bench)

