# Quantum Causal Discovery — Deprecation & Redirect Package (3 Aug 2026)

<aside>
🔀

**Status: diagnosis verified in sandbox, redirect patch drafted, not yet merged.** Unlike the three primitives fixed in the [Quantum Primitives Rebuild — Integration Package (3 Aug 2026)](Quantum%20Primitives%20Rebuild%20%E2%80%94%20Integration%20Package%20(%20bb36a12f42954716851c5d6d448424f0.md), `asi/quantum_causal_discovery.py::QuantumCausalDiscovery` in `HYBA_Unified_Backend` is not a case of "broken math, known real fix." There is no single-formula substitution that turns its underlying computation into genuine directed causal discovery, and it duplicates a real, working implementation that already exists elsewhere. The honest fix here is **deprecation and redirect**, not a rebuild.

</aside>

## The problem

The module's own docstring claims it can identify "causal structures that are invisible to classical methods" via "quantum superposition, entanglement, and interference." Tracing the actual computation in `quantum_superposition_test`:

```python
corr = np.corrcoef(data[:, i], data[:, j])[0, 1]
...
phase_shift = corr * np.pi / 2
state_j = state_j * np.exp(1j * phase_shift)
interference = np.abs(np.vdot(state_i, state_j)) ** 2
causal_strength = interference / self.phi
```

The only real input from the data is the ordinary Pearson correlation coefficient `corr`, which is symmetric (`corr(i,j) == corr(j,i)`) by definition. Everything downstream — the qubit rotation, the "interference" inner product, the φ-normalization — is a fixed, deterministic function of that one symmetric number. Nothing in this formula can distinguish "i causes j" from "j causes i": the quantum notation is decorative dressing on a scalar correlation, not a source of new directional information.

## Verified in sandbox, 3 Aug 2026

I ran the unmodified algorithm on synthetic data with a known causal chain (X0→X1→X2, X3 independent, n=4,000) and tested whether its reported "stronger direction" for each variable pair is a real property of the causal structure, or an artifact of the order variables happen to be indexed in. A real causal-discovery result must be invariant to how you label/order the same variables; a loop-order artifact will not be.

**Method:** ran `entanglement_based_discovery` once in original variable order, then again after relabeling the same four variables (swap 0↔3, 1↔2) and mapping the result back to the original labels.

**Result — the "stronger direction" call flips for every non-tied pair, purely from relabeling:**

| **Pair** | **Original order (i→j / j→i)** | **Relabeled + remapped (i→j / j→i)** | **Conclusion** |
| --- | --- | --- | --- |
| 0,1 | 0.000055 / 0.000042 → "0→1 stronger" | 0.000043 / 0.000056 → "1→0 stronger" | ❌ flipped |
| 1,2 | 0.000055 / 0.000042 → "1→2 stronger" | 0.000042 / 0.000055 → "2→1 stronger" | ❌ flipped |
| 0,3 | 0.000041 / 0.000054 → "3→0 stronger" | 0.000054 / 0.000041 → "0→3 stronger" | ❌ flipped |
| 2,3 | 0.000056 / 0.000043 → "2→3 stronger" | 0.000042 / 0.000055 → "3→2 stronger" | ❌ flipped |
| 0,2 | 0.000034 / 0.000034 → tie | 0.000034 / 0.000034 → tie | uninformative both times |
| 1,3 | 0.000034 / 0.000034 → tie | 0.000034 / 0.000034 → tie | uninformative both times |

Every pair where the algorithm reported a directional "winner" reversed that winner under nothing more than relabeling the same variables with the same underlying data — proof the directionality is a loop-iteration-order artifact, not a causal signal.

**A second, independent bug:** `causal_strength[i, j] = strength * self.phi_inverse ** iteration` *overwrites* rather than accumulates across the 100 default iterations, so by the final iteration the stored value is multiplied by φ⁻⁹⁹ ≈ 3×10⁻²¹ — the matrix the caller actually receives is numerically indistinguishable from zero everywhere, regardless of input data.

## What this means

This is not "broken math with a known fix," unlike the quantum walk, teleportation, and hash function in the other package. There is no single-formula substitution that turns a symmetric correlation coefficient into genuine causal direction. That already-solved problem is what `CausalStructureDiscovery` (BIC-scored DAG search over hypotheses) does correctly, and it already exists in `HYBA_Data/quantum_substrate/intelligence/causal.py` — independently re-verified this session (see [HYBA Data — Product Suite: From Verified Mathematics to Sovereign Security (McKinsey View)](../HYBA%20Data%20%E2%80%94%20Product%20Suite%20From%20Verified%20Mathematic%208f35848baf3c4bf39d151b7f7fdde01d.md), Section 5 item 4: zero structural Hamming error recovering a known X0→X1→X2 chain, near-zero confidence correctly reported on independent noise).

**Recommended fix: deprecate and redirect, don't rebuild.** Keep the module importable (don't break existing callers) but make it honest about what it is and where to go instead.

## Integration patch

**1. Rename the current file** `asi/quantum_causal_discovery.py` → `asi/quantum_causal_discovery_legacy.py` (preserve the code as-is for audit; it is not being deleted, just marked non-canonical).

**2. Replace `asi/quantum_causal_discovery.py` with a thin, honest redirect shim:**

```python
"""
Quantum-Inspired Causal Discovery Algorithm — DEPRECATED
==========================================================

This module previously claimed to identify "causal structures invisible to
classical methods" via quantum superposition/entanglement/interference.

Verified 3 Aug 2026: the core quantum_superposition_test computation reduces
entirely to a fixed, deterministic function of the ordinary (symmetric)
Pearson correlation coefficient between the two variables. The "direction"
it reports for a given variable pair is not stable under relabeling the same
variables and re-running the identical algorithm -- i.e. it is an artifact
of loop-iteration order, not a real directional signal. A second bug causes
the returned causal_strength matrix to be scaled by
phi_inverse ** (n_iterations - 1) (~3e-21 at the default 100 iterations),
making it numerically indistinguishable from zero regardless of input.

The original implementation is preserved unmodified for reference/audit at
asi.quantum_causal_discovery_legacy. It is not called by this shim and
should not be used for any live causal-discovery workflow.

Use HYBA_Data's quantum_substrate.intelligence.causal.CausalStructureDiscovery
instead: a BIC-scored DAG search that was independently re-executed and
verified this session (zero structural Hamming error recovering a known
causal chain; near-zero confidence correctly reported on independent noise).
"""

import warnings

from asi.quantum_causal_discovery_legacy import (
    QuantumCausalDiscovery as _LegacyQuantumCausalDiscovery,
)
from asi.quantum_causal_discovery_legacy import (
    QuantumCausalGraph,
    QuantumCausalInferenceEngine as _LegacyQuantumCausalInferenceEngine,
    QuantumCausalState,
)

_DEPRECATION_MSG = (
    "asi.quantum_causal_discovery.QuantumCausalDiscovery is deprecated: its "
    "causal-direction output is a verified loop-order artifact, not a real "
    "signal (see module docstring). Use "
    "HYBA_Data.quantum_substrate.intelligence.causal.CausalStructureDiscovery."
)

class QuantumCausalDiscovery(_LegacyQuantumCausalDiscovery):
    def __init__(self, *args, **kwargs):
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)

class QuantumCausalInferenceEngine(_LegacyQuantumCausalInferenceEngine):
    def __init__(self, *args, **kwargs):
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)

__all__ = [
    "QuantumCausalState",
    "QuantumCausalGraph",
    "QuantumCausalDiscovery",
    "QuantumCausalInferenceEngine",
]
```

This keeps every existing import path working (`from asi.quantum_causal_discovery import QuantumCausalDiscovery` still resolves), but now raises a `DeprecationWarning` naming the exact defect and the correct replacement every time it's instantiated, and the module docstring can no longer be quoted to support an "invisible to classical methods" claim externally.

**3. Grep the codebase for any live callers** of `asi.quantum_causal_discovery` and migrate them to `HYBA_Data`'s `CausalStructureDiscovery` where feasible; keep the shim only for backward-compatibility during migration.

## Test evidence

Sandbox script `test_quantum_causal_discovery.py` reproduces the permutation test above against a synthetic causal chain (X0→X1→X2, X3 independent, n=4,000, seed=42). Re-run it against the shim before merging to confirm the wrapper doesn't alter the legacy class's runtime behavior (it shouldn't — it only wraps `__init__` to add the warning).

## Rollout checklist

- [ ]  Rename `asi/quantum_causal_discovery.py` → `asi/quantum_causal_discovery_legacy.py`
- [ ]  Add the redirect shim above as the new `asi/quantum_causal_discovery.py`
- [ ]  Grep for and migrate any live callers to `HYBA_Data`'s `CausalStructureDiscovery`
- [ ]  Remove or rewrite any marketing/doc references to "invisible to classical methods" for this module
- [ ]  Update Product Suite Section 5, item 4 to point at the merged commit once this lands