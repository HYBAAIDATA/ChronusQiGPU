# Organism integration: specialists under the EUCLID composition root

`EuclidRuntime.production()` is the single composition root. With
`organism=True` (the default) it calls `EuclidRuntime.compose_organism()`, which
registers the specialist organs below on the existing `OrganRegistry` /
`Delegator` / `RightsLedger`. It does not start a second runtime, planner or
intelligence hierarchy.

## Capability graph (as wired)

```text
caller ──► EuclidRuntime.dispatch_specialist(organ, request, tenant, actor, token)
             │
             ├─ AL HARAS boundary (ALHaras.evaluate)   only when a guardian is supplied
             │     deny ─► evidence "governance-denial", returned as data (caller replans)
             │
             ├─ EUCLID Delegator gates  (registered, capability, creator right,
             │                           confident, safe, healthy)
             │     veto ─► returned as data with organ health
             │
             ├─ turing  ─► TuringQuantumOrgan ─► turing backends.select_backend/execute
             ├─ chronus ─► ChronusComputeOrgan ─► chronus.mla1517.mining.BackendRegistry
             └─ triad   ─► TriadCustodyOrgan  ─► aethel.triad (THESEUS put/get/verify, OVID fold)

EuclidRuntime.heal_organ(organ) ─► salamander AutonomicControlPlane
      action "requalify-organ" (REQUALIFY) ─► owner probe ─► independent verifier
      "euclid.delegator-redispatch" (fresh dispatch through all delegator gates)

all steps ─► EvidenceChain (hash-linked)  +  ReachabilityMatrix (sealed, persisted
             to <state_dir>/cognition_reachability.json)
```

Adapters live in `euclid/organ_adapters/specialists.py`. Each returns the
owner's own evidence and its `owner` field; none upgrades a truth class.

## Ownership is preserved

| Organ | Owner | EUCLID authority | Truth boundary kept |
|---|---|---|---|
| `turing` | TURING | read-only dispatch | `truth_class`, `execution_class`, `measured_qpu` come from the backend; hardware preference is refused (`truth_class: refused`) because no QPU adapter ships |
| `chronus` | CHRONUS | read-only dispatch | only probed lanes bind; unavailable lanes return `bound: False` with the probe reason; only the CPU lane executes in this organ and its sha256d equals `chronus.mla1517.mining.pow.sha256d` |
| `triad` | THESEUS / OVID | read-only dispatch | custody digests are sha256 of the payload; OVID fold must round-trip |
| AL HARAS | AL HARAS | gate only | subscription token, tenant, actor, allowed operations, payload size; no token is ever self-issued by EUCLID |
| Salamander | Salamander | bounded action | one registered action kind (REQUALIFY); success requires the independent verifier; no source mutation |

Mining consensus (header, nonce semantics, target, sha256d validity,
credentials, share validation, submission, acknowledgement) stays outside
EUCLID; `startup_report()["authority_boundary"]` still lists it as forbidden.

## Measured reachability (tests/test_organism_integration.py)

| Component | Stage reached by the tests | Evidence |
|---|---|---|
| `turing.backends` | OUTCOME_OBSERVED | Bell program executes `exact`; QPU preference refused |
| `chronus.backend_registry` | OUTCOME_OBSERVED | CPU sha256d scan equals reference; CUDA/Metal/remote/ASIC selection matches census |
| `aethel.triad` | OUTCOME_OBSERVED | put/get digest equality, fold round-trip, verify |
| `al_haras.guardian` | CHANGES_DECISION | prohibited op denied without result, allowed op succeeds, missing token denied |
| `salamander.control_plane` | FEEDBACK_CLOSED | degraded organ vetoed → requalified → verified → dispatch admitted; an unverifiable repair stays unverified and degraded |
| reachability file | survives process restart | `ReachabilityMatrix.load` verifies the seal after `close()` |

## Honest negatives in this environment

Probed on the Windows VM used for this change: CPU lane available; OpenCL
(`pyopencl` missing), CUDA (`cupy` missing), Metal (requires Darwin), remote GPU
(no endpoint configured) and ASIC (no channel configured) unavailable. No
physical QPU provider exists. `super_asic` binds only as a composite over the
CPU lane. These are asserted, not skipped.

## Open gaps (not proven here)

1. Cognition episodes (`CognitionCore`) do not yet select specialists on their
   own; specialist dispatch is caller-driven. Specialists therefore stop at
   OUTCOME_OBSERVED, not FEEDBACK_CLOSED, for TURING/CHRONUS/Triad.
2. THESEUS custody opened by `TriadCustodyOrgan` is process-local; restart of
   custody content is not verified by this path.
3. Transfer of specialist outcomes into later behaviour (TRANSFER_VERIFIED) is
   not demonstrated for the specialists.
4. Device lanes (OpenCL/CUDA/Metal/remote/ASIC) and QPU execution are
   unverified because the substrates are absent.
5. `startup_report()["intelligence_readiness"]` remains `NOT_CERTIFIED`.
