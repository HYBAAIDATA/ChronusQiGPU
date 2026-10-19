# Consortium ledger separation — closure of blocker 6

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 6.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.

---

## 1. The defect as stated

> **Consortium ledger**: a digest authenticates serialized data, not its truth.
> Institution strings do not establish independent reviewers. Counter increments
> do not measure hardware throughput. Require replayable computational evidence,
> authenticated producer/verifier identities, stale-value/replay handling and explicit
> separation of formulation, computational verification and device measurement.

Four defects: digest-as-truth confusion, string-as-identity confusion,
counter-as-measurement confusion, and no separation of claim classes.

## 2. Existing machinery

`chronus/consortium_push.py` already implements a governance layer:

| Element | Function |
|---|---|
| Truth gate | sha256-bound measured receipts; first-principles derivations with no-quantum-framework enforcement; falsifiable predictions |
| Cross-check | 2+ peer cross-check |
| Metric ownership | exclusive per metric |
| Monotonicity | fabric never shrinks; stale `from_value` fails closed |
| Ledger | append-only, hash-chained `PushLedger` |
| Operations | `push_cycle`, `diagnose`, `verify_invariants` |

Tested in `tests/test_consortium_push.py`, including the documented example
trajectory.

**The reviewed machinery is sound in mechanism and unsound in semantics.** The
fixes below are about what the ledger's contents are *claimed to mean*, not about
the chain's integrity.

## 3. Digest ≠ truth

A sha256 digest binds bytes. It proves the bytes are the bytes that were
hashed. It proves nothing about whether the bytes are *true*.

**Declared:** every ledger entry separates three fields that must not collapse
into one:

```
payload_digest   : sha256   # integrity of the bytes — the chain's concern
claim_class      : enum     # WHAT KIND of claim the payload makes
evidence_basis   : enum     # HOW the claim was established
```

| `claim_class` | Meaning |
|---|---|
| `FORMULATION` | a mathematical or structural statement |
| `COMPUTATION` | a computed result, replayable from a declared procedure |
| `MEASUREMENT` | a device observation, bound to a device identity |

| `evidence_basis` | Meaning |
|---|---|
| `DERIVED` | proved, with the proof cited |
| `REPLAYED` | recomputed and matched on replay |
| `OBSERVED` | read from a device, with the reading's provenance |

**Rule:** a digest may be cited as evidence of *integrity* only. Citing it as
evidence of *truth* is the defect the review names, and a ledger entry whose
`claim_class` is `FORMULATION` or `DERIVED` must cite the derivation, not the
hash.

**Existing precedent:** `docs/M32_TENSOR_BRIDGE.md` §4 keeps SHA-256d as the
*sole accept authority* while the Tensor only *reorders* — an example of the
same discipline applied to mining. The ledger should follow it.

## 4. Institution strings ≠ independent reviewers

The review: *"Institution strings do not establish independent reviewers."*

`chronus/m5_ultra.py:consortium_fabric()` builds a 7-institution
labelled-edge variant, with every label carrying
`truth_class="quantum_substrate_formulation"` and `measured_by_chronus=False`.

**Declared:** a name in a field is not a reviewer. Required for any entry
claiming peer verification:

```
producer_id   : authenticated identity
verifier_ids  : set of authenticated identities, cardinality >= 2
independence  : declared basis for non-common-mode between producer and verifiers
```

| Field | Constraint |
|---|---|
| `producer_id` | authenticated; not a string literal |
| `verifier_ids` | >= 2, distinct from producer |
| `independence` | states *why* the verifiers are not common-mode |

**Rule:** the review's own wording — *"Institution strings do not establish
independent reviewers"* — means the `independence` field is mandatory and must
state a basis, not assert a status. "Independent" is a conclusion from a basis,
not a label.

**Existing honesty to preserve:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md`
records that *"Deutsch, Turing, Grover, Shor and Schrödinger are review-role
labels, not participating scientists"* and that *"Clay, MIT, Caltech, Oxford,
Cambridge, Princeton, ETH and any Moscow institution are not engaged
supervisors."* Any ledger entry naming an institution inherits that boundary
and must not imply engagement.

## 5. Counter increments ≠ throughput

The review: *"Counter increments do not measure hardware throughput."*

A counter that goes 41 → 42 records that a code path ran. It does not measure
hashes per second, and it cannot, because the counter reads a software state
while throughput is a physical quantity.

**Declared:** throughput claims require a measurement class of their own, and
are inadmissible without:

```
{ value, unit, device_id, wall_clock_interval, method, uncertainty }
```

**Boundary from `claims.yaml`** — three items are **PROHIBITED** outright and
must not appear in any ledger entry, in any form:

| id | text |
|---|---|
| `p-throughput-eh` | "10 EH/s" |
| `p-gpu-equivalence` | "One device equals 20,000 NVIDIA GPUs" |
| `p-exponential-speed` | "Exponential speedup" |

Additionally, `claims.yaml` records `r-lucas-pisot-speedup` as **REFUTED**
(negative log: `al_haras/refuted_claims.py`). Any ledger entry re-asserting a
Lucas/Pisot speedup contradicts the register.

**Rule:** a counter may be reported as a counter. It may not be reported as a
rate.

## 6. Stale-value and replay handling

The machinery declares monotonicity ("fabric never shrinks; stale `from_value`
fails closed"). The requirement is sharper than that.

**Required:**

| Concern | Handling |
|---|---|
| Stale `from_value` | fail closed — already implemented, preserve |
| Replay | a replayed push must be *detectable* as a replay, not silently accepted as an advance |
| Continuity | the gap between `from_value` and `to_value` is either zero or explicitly bridged by an intervening entry |

**Rule:** monotonicity without replay detection permits the same advance to be
counted twice. The chain proves ordering; it does not by itself prove
non-duplication. The non-duplication property must be declared separately.

## 7. Ledger intactness — what can and cannot be claimed

At the baseline, the append-only hash-chained `PushLedger` is **implemented and
tested** (`tests/test_consortium_push.py`). Whether it is **currently intact** is
a different question: there is no read surface exposing the ledger head, so
intactness cannot be verified from outside the process.

**Two distinct claims, never merged:**

| Claim | Basis | Status |
|---|---|---|
| The ledger mechanism enforces the chain | tests | established |
| The ledger at its current head is intact | `verify_invariants` output | **not established from outside** |

**Required artifact:** a read surface exposing the ledger head and the
`verify_invariants` result, so the second claim becomes checkable without
running the process.

## 8. What this document does not do

No implementation, no tests, no code. Does not verify the ledger's current
state. Does not establish reviewer independence. No merge, release or mining
activation. `theorem_proven` remains False.

## 9. Next action

Adopt the three-field separation of §3, the identity requirements of §4, and the
throughput boundary of §5. The read surface of §7 is the first artifact, since
it converts an uncheckable claim into a checkable one.
Owner: @EuclidUltimaPhi. Drafting: `pythiaphi`.
