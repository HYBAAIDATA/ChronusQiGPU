# Production-Readiness Replacement Plan (continuation)

## Goal
Replace every defective production implementation with correct exact implementations,
migrate all canonical callers, preserve legitimate research/reference capabilities,
and certify the canonical product as production-ready (all zero counters).

## Production Contract (from prior report)
- Pure quantum math only in the canonical route.
- No mock, demo, stub, heuristic, numerical approximation, classical substitute,
  or legacy fallback in the canonical route.
- Replacement-first rule: replace defective implementation BEFORE retiring the old
  production route. Preserve legacy/research/reference implementations under an
  explicitly non-production boundary.
- Command-of-authority: PYTHIA owns mining plans/decisions; CHRONUS executes the
  sealed plan. Learned/advisory ordering must not override PYTHIA.
- Receipt binding: every execution receipt must bind requested/planned/executed
  algorithm, implementation module/digest, execution mode, substrate, plan digest,
  exact-geometry/certificate digest, iterations/work, SHA-256d verification,
  fallback_used, and fallback_reason.
- Canonical route requires requested == planned == executed.

## Canonical Finished Route
PYTHIA authority -> sealed Hendrix plan -> exact M32 topology ->
exact phi-weighted 11D -> exact H4/600 fabric -> actual Hendrix/quantum execution
-> CHRONUS execution -> real SHA-256d -> independent consensus verification
-> THESEUS/OVID custody -> restart/replay -> submission boundary.

## Step 1: Audit the production scope
Files to audit (from session context):
- chronus/seam/{scale,kernel,__init__}.py
- chronus/readiness.py
- chronus/virtual_igpu/evidence.py
- euclid/__init__.py
- gpu/reference.py
- Intelligence/lucas_scales.py
- kellogg/scales.py
- scripts/chronus_production_gate.py
- scripts/chronus_wheel_acceptance.py

## Step 2: Replace older numerical solver APIs with exact equivalents
Target modules (older numerical routes):
1. Intelligence/predictive_solver.py -> exact integrator
2. Intelligence/lucas_scales.py (M31 numerical scale) -> exact M31 lane
3. kellogg/scales.py (exact Phi-algebra) -> exact 11D restoration

## Step 3: Replace inherited operational-policy shortcuts
Target modules:
1. chronus/seam/kernel.py (dispatch fallback) -> authoritative sealed-plan route
2. chronus/seam/scale.py (scale policy) -> exact scale contract
3. chronus/mla1517/mining/execution_router.py (heuristic ordering)

## Step 4: Exact production implementations
Implement exact Hendrix, exact M32 certificate, exact 11D restoration, exact
H4/600 certificate, sealed plan handling, scheduler substitution,
quantum-walk normalization, receipt implementation identity, and
SHA-256d verification in the appropriate modules.

## Step 5: Migration of canonical callers
Migrate every canonical caller to the new exact implementations.

## Step 6: Mutation/adversarial tests
Test that disabling exact Hendrix, substituting old numerical implementation,
corrupting certificates, mutating sealed plan, substituting heuristic/simulation
implementations, altering receipt identity, and falsifying SHA-256d candidates
each fail closed.

## Step 7: Backward compatibility
Every old public API gets an explicit compatibility facade (old -> new canonical).
No legacy computation preserved underneath.

## Step 8: Verify installed artifacts
Native wheel, portable wheel, fresh process, restart/replay, clean environment.

## Step 9: Closure metrics
CAPABILITIES_REMOVED_WITHOUT_REPLACEMENT=0
PRODUCTION_NUMERICAL_FALLBACKS=0
PRODUCTION_HEURISTIC_SUBSTITUTIONS=0
PRODUCTION_SIMULATION_SUBSTITUTIONS=0
PRODUCTION_STUBS_MOCKS_DEMOS=0
ALGORITHM_IDENTITY_VIOLATIONS=0
UNMIGRATED_PRODUCTION_CALLERS=0
UNREVIEWED_PRODUCTION_PATHS=0
OPEN_MATERIAL_DEFECTS=0
