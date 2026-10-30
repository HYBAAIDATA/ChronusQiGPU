# EUCLID — Recovery Mechanism Verification Scripts

**HYBA | EUCLID**

<aside>

**Status: implemented, verified — 19 July 2026.** Two standalone verification scripts validate the resiliency protocols: Probationary Recovery (organism_beta drops to rep 0.25 after SLA breach, recovers via φ₁-attenuated steps) and Chronicle Fork Reconciliation (partition at E5, divergent forks A6→A7 and B6→B7, DAG merge with LCA detection). Both scripts pass all assertions.

</aside>

## Verification 1: Probationary Recovery

### Script: `euclid/verify_reputation_recovery.py`

Simulates organism_beta dropping to reputation 0.25 (below the 0.3 active threshold) after the 6.081ms SLA breach witnessed in the Joint Verification Suite.

### Verification Steps

| Step | Assertion | Result |
| --- | --- | --- |
| [1] | rep=0.25 → state=PROBATIONARY | ✅ PASS |
| [2] | Enters probation with required_tests=3 | ✅ PASS |
| [3] | φ₁ recovery step: 0.05 × 0.618034 = 0.0309 | ✅ PASS |
| [3a] | Test 1: rep=0.2809, state=PROBATIONARY | ✅ PASS |
| [3b] | Test 2: rep=0.3118, state=PROBATIONARY | ✅ PASS |
| [3c] | Test 3: rep=0.3427, state=HEALTHY (rep ≥ 0.3) | ✅ PASS |
| [4] | Graduated to HEALTHY at rep=0.3427 | ✅ PASS |
| [5] | Failure → SUSPENDED, rep=0.00, cannot re-enter | ✅ PASS |

### φ₁ Recovery Arithmetic

```
Expected: 0.25 + 3 × (0.05 × 0.618034) = 0.25 + 0.0927051 = 0.3427
Actual:   0.25 + 0.0309 + 0.0309 + 0.0309 = 0.3427 ✅
```

### Key Behaviors Verified

- **Restricted to low-risk dispatches:** PROBATIONARY nodes cannot participate in active consensus — `evaluate_node_health()` returns PROBATIONARY until graduation
- **φ₁-attenuated recovery:** Each success adds exactly 0.05 × φ⁻¹ ≈ 0.0309 — slow, deliberate recovery prevents rapid trust oscillation
- **Immediate suspension on failure:** Any probation failure → rep zeroed, SUSPENDED, barred from automatic re-entry — operator clearance required

## Verification 2: Chronicle Fork Reconciliation

### Script: `euclid/verify_chronicle_reconciliation.py`

Simulates a network partition at Event E5. Group A (local) appends A6→A7. Group B (remote) appends B6→B7. After partition heals, `ReconcilableChronicle.reconcile_diverged_branch()` merges both histories via a DAG `MergeChronicleEvent`.

### Verification Steps

| Step | Assertion | Result |
| --- | --- | --- |
| [1] | Shared history E1→E2→E3→E4→E5 (5 events) | ✅ PASS |
| [2] | Chain B fork: E5 → B6 → B7 (7 events) | ✅ PASS |
| [3] | Chain A fork: E5 → A6 → A7 (7 events) | ✅ PASS |
| [4] | Reconciliation succeeds | ✅ PASS |
| [5] | LCA correctly identified as E5 | ✅ PASS |
| [6] | Merge links A7 tip + B7 tip | ✅ PASS |
| [7] | Merge event hash verified | ✅ PASS |
| [8] | Historical ledger preserved: 10 events, E1 hash intact | ✅ PASS |
| [9] | Post-reconciliation LCA = B7 (imported during merge) | ✅ PASS |

### DAG Topology After Reconciliation

```
E1 → E2 → E3 → E4 → E5 (LCA)
                      ├── A6 → A7 ─┐
                      └── B6 → B7 ─┤
                                    └── MERGE
```

The `MergeChronicleEvent` carries:

- `predecessor_hash` → A7 (branch A tip)
- `divergent_predecessor_hash` → B7 (branch B tip)
- `common_ancestor_hash` → E5 (LCA)

### Key Behaviors Verified

- **LCA detection:** `find_last_common_ancestor()` correctly identifies the most recent event hash shared by both chains — E5 before reconciliation, B7 after import
- **Divergent segment integrity:** Each remote block's `predecessor_hash` chain and `calculate_hash()` are verified before import — broken links or hash mismatches are rejected
- **No historical mutation:** Original events (E1-E5, A6-A7) are never touched — the merge is purely additive
- **Merge event hash:** `calculate_hash()` binds both branch tips, the LCA, and the reconciliation payload into a single cryptographic identity

## Canonical Files

| File | Purpose |
| --- | --- |
| `euclid/verify_reputation_recovery.py` | Standalone probationary recovery verification — 5-step assertion suite |
| `euclid/verify_chronicle_reconciliation.py` | Standalone fork reconciliation verification — 9-step assertion suite |
| `euclid/reputation_recovery.py` | ProbationaryRecoveryManager — φ₁-attenuated recovery steps |
| `euclid/chronicle_reconciliation.py` | ReconcilableChronicle — DAG merge with LCA detection |

</content>