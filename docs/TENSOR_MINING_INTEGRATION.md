# Tensor → Mining Integration Plan

## Purpose

Wire the Kellogg Tensor into the live mining path as a **navigator**, not a
controller. The Tensor reorders and prunes the search space; SHA-256d remains
the sole accept authority.

## State After Implementation

| Component | Status |
|-----------|--------|
| `src/lib/mining_service.ts` | SHA-256d sole accept authority ✅ |
| `src/lib/mining_runtime.ts` | Mining loop + `tensorNavigate()` wiring ✅ |
| `src/lib/quantum_walker_aqo.ts` | M32 walker produces candidates ✅ |
| `src/lib/kellogg_operator.ts` | Tensor complete, honest, validated ✅ |
| `src/lib/m32_tensor_bridge.ts` | Bridge: M32 → S = (X,G,M,g,χ,H*) ✅ |
| Tensor → mining wiring | **Wired** ✅ |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  MINING WITH TENSOR NAVIGATION                                       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  M32 WALKER (quantum_walker_aqo.ts)                          │   │
│  │  • Icosahedral quantum walk                                  │   │
│  │  • Produces candidate nonces                                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────▼──────────────────────────────────┐   │
│  │  KELLOGG TENSOR (m32_tensor_bridge.ts — Navigator)           │   │
│  │  • Structured search space S = (X, G, M, g, χ, H*)           │   │
│  │  • Reorders candidates by geodesic proximity                 │   │
│  │  • Prunes candidates outside the active face set             │   │
│  │    (only when EUCLID_TENSOR_PRUNE=true)                      │   │
│  │  • Does NOT change accept criteria                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────▼──────────────────────────────────┐   │
│  │  SHA-256d (mining_service.ts meetsTarget — Judge)            │   │
│  │  • Sole accept authority                                     │   │
│  │  • Verifies every candidate                                  │   │
│  │  • Rejects non-matching candidates                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────────────────▼──────────────────────────────────┐   │
│  │  SUBMIT                                                      │   │
│  │  • Accepted candidates → pool                                │   │
│  │  • Provenance logged                                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation

### Phase 1: Bridge Construction ✅

- [x] Build `src/lib/m32_tensor_bridge.ts`
- [x] Map M32 faces → Tensor X (`m32FaceSet`)
- [x] Map M32 operators → Tensor G (`M32_ADJACENCY` generators)
- [x] Map M32 geometry → Tensor M (`m32GeodesicDistances`)
- [x] Map M32 weights → Tensor g (`m32PhiMetricDiagonal`)
- [x] Map M32 depth → Tensor χ (`tensorTruncationRank`, χ = 8)
- [x] Map mining target → Tensor H* (`targetFace` marked solution)

### Phase 2: Navigator Wiring ✅

- [x] `MiningRuntime.tensorNavigate()` consumes Tensor reordering
- [x] `MiningService.executeMiningStep` probes in navigated order
- [x] Preserve SHA-256d as sole authority (`meetsTarget` unchanged)
- [x] Add Tensor navigation telemetry (`tensor.navigate` event, `tensorNav`
      in step result and runtime status)
- [x] No target modification anywhere in the bridge

### Phase 3: Verification ✅

- [x] Test M32 face count = 32 (12 pentagonal + 20 triangular)
- [x] Test Tensor X = M32 faces
- [x] Test SHA-256d authority preserved (pure permutation of probe list)
- [x] Test O(1) lookup (`TensorCandidateTable`)
- [x] Test Cassini parity holds per candidate
- [x] Test determinism, pruning, env fallback (`EUCLID_TENSOR_NAV=false`)
- [ ] Benchmark Tensor navigation speedup against live share acceptance

### Phase 4: Production Rollout

- [ ] Deploy to staging
- [ ] Run parallel with current mining
- [ ] Compare share acceptance rate
- [ ] Verify identical acceptance criteria
- [ ] Promote to production

## Operator Controls

| Env var | Default | Effect |
|---------|---------|--------|
| `EUCLID_TENSOR_NAV` | on | `=false` bypasses navigation (Born order, telemetry `fallback: true`) |
| `EUCLID_TENSOR_PRUNE` | off | `=true` prunes candidates to the top-χ active faces |

## Rule Preservation

**AGENTS.md §4.5:** any Tensor→mining integration may only reorder or prune
the search space while SHA-256d stays the sole accept authority.

**Enforcement:**
- `meetsTarget()` / `sha256d` is the only accept path — the bridge module
  contains no hashing and no target comparison
- No target comparison outside SHA-256d
- No candidate bypass of SHA-256d check

## Telemetry

Per cycle (`euclid:telemetry` / `tensor.navigate` event and
`MiningStepResult.tensorNav`):
- `candidatesIn` / `candidatesOut` — candidates entering / leaving navigation
- `reorderedPositions` — probe positions changed
- `pruned` — candidates removed (0 unless `EUCLID_TENSOR_PRUNE=true`)
- `activeFaces` — faces retained
- `cassiniVerified` — per-candidate parity certificate
- `fallback` — navigator bypassed (disabled or failed)
- `durationMs` — navigation time

## Failure Modes

| Failure | Response |
|---------|----------|
| Tensor navigation throws | Fall back to Born order; `fallback: true` telemetry |
| `EUCLID_TENSOR_NAV=false` | Bypass navigation entirely |
| Tensor reorders incorrectly | Alert; disable via env flag |
| SHA-256d bypass detected | Halt mining; alert |
| Target modification detected | Halt mining; alert |

## The One-Line Summary

**The Tensor is a navigator. The M32 walker is the search space. SHA-256d
is the judge. Wired: M32 → Tensor → SHA-256d → submit. Discipline preserved:
no target modification, no acceptance bypass, no fake shortcut. Verified:
face count, X mapping, authority preservation, O(1) lookup, Cassini parity.**

## Success Criteria

- [x] Tensor navigates the M32 search space
- [x] SHA-256d remains sole authority
- [ ] Share acceptance rate improves (or stays equal) — needs live benchmark
- [x] O(1) lookup path provided (`TensorCandidateTable`)
- [x] No target modification
- [x] All tests pass
- [x] Telemetry shows Tensor effectiveness
