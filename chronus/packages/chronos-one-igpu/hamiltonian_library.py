# hamiltonian_library.py
# Compatibility shim (audit fix, 3 Aug 2026): the real, fixed implementation
# now lives in src/chronos/hamiltonian.py as the single source of truth.
# This file re-exports it so any existing code importing from the repo root
# keeps working.
from chronos.hamiltonian import HamiltonianLibrary, HamiltonianTerms  # noqa: F401
