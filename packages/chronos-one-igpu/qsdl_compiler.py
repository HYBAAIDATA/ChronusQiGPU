# qsdl_compiler.py
# Compatibility shim (audit fix, 3 Aug 2026): the real, fixed implementation
# now lives in src/chronos/qsdl_compiler.py as the single source of truth.
# This also removes the original hard SyntaxError ("qsd l_source") that
# prevented chronos_gpu_demo.py from importing at all.
from chronos.qsdl_compiler import QSDLCompiler, QScene, ManifoldConfig  # noqa: F401
