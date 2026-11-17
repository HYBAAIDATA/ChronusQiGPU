# hyba_trust

Trust states, promotion authority and demotion cascade for derived knowledge atoms
(facts and summaries). Internal HYBA Data library; standard library only.

It implements the v5 "promotion authority + retroactive demotion" design, with the
review fixes below. No `MEMORY_FABRIC` or `AGI_ORCHESTRATOR` exists in this repository,
so nothing calls it yet: `consolidate()` is the hook an orchestrator would use in
place of writing extracted facts straight to semantic memory.

## What it does

- **Seven trust states** (`proposed`, `quarantined`, `probation`, `canonical`, `disputed`,
  `demoted`, `retracted`) with a legal-transition table. Every change is appended to the
  atom's history and to a hash-chained promotion ledger; nothing is overwritten.
- **Promotion by review, not by confidence.** `propose()` routes each atom by risk tier:
  LOW 72 h, MEDIUM 24 h, HIGH 8 h, REGULATORY 4 h. HIGH needs two distinct human
  approvers; REGULATORY also needs a named signatory. Proposers, generating agents and
  amenders can never approve. Reviewers must act on the current `review_packet()`
  (evidence, provenance, blast radius, conflicts), or the review is refused.
- **Probation decides by clock.** After 30 days, a clean probation atom becomes canonical;
  one with disputes, incorrect serves or a stale ancestor is demoted.
- **Demotion cascade.** Entering `demoted`, `retracted` or `disputed` walks `derived_from`
  transitively (summaries must record lineage), marks every descendant stale, disputes
  any authoritative descendant, notifies affected use-case owners, blocks production
  use cases until re-derived or acknowledged, and writes a cascade manifest. All of
  this happens before the call returns.
- **Retroactive demotion, appeals, un-retract.** An atom canonical for more than 30 days
  has its dependent outputs sampled for re-checking. Appeals are capped at two and go to
  second line; the decision on the second appeal is final. Un-retracting needs two
  distinct second-line actors.
- **Degraded mode.** A proposal whose review is overdue moves to `quarantined` only. It
  is projected as `UNVERIFIED`, never as authority.
- **Invariants and metrics.** `check_invariants()` re-checks the bypass rules over the
  whole fabric. `metrics` reports backlog age p95, cascade latency, quarantine leak
  rate, demotion recurrence and per-reviewer overturn rate, all from the fabric's
  own records.

## Differences from the v5 pseudocode

| # | v5 | Here |
|---|----|------|
| 1 | Dual control checked after the transition | Checked before; one approval leaves the atom where it was |
| 2 | A reviewer could amend, then approve their own edit | Amenders become authors and cannot approve |
| 3 | Cascade disputed canonical descendants only | Probation descendants are disputed too, so they cannot auto-promote |
| 4 | No `probation -> disputed` | Added |
| 5 | Each disputed descendant re-ran the cascade | One pass with a visited set, one manifest per root; terminates on cycles |
| 6 | Anyone authorised could un-retract | Two distinct second-line actors |
| 7 | `proposed` could not reach `probation`/`demoted`, so reviews could not apply | Added |
| 8 | Probation demoted atoms before the 30 days elapsed | Decided only at TTL |
| 9 | Appeals could loop | Capped at two; the second-line decision on the second is final |

The tests include one per fix. Each was checked by reverting the fix and confirming
the test fails.

Two additions the pseudocode left open:

- **Quarantine expiry.** It had a 14-day TTL with no rule; an unreviewed quarantined
  atom now becomes `demoted` when it expires.
- **Notification delivery.** Notifications are written to `outbox` inside the cascade,
  but delivered by the caller (`deliver_notifications`). A delivery outage cannot block
  a demotion, and failed notices stay visible for retry.

## Limits

- In-memory and single-process: no persistence, locking or concurrent writers yet.
- Actors are passed in, not authenticated. Identity and role assignment belong to the
  caller's identity system.
- The ledger's hash chain shows tampering within one record; it is not a signature.
- LOW/MEDIUM "auto review + human spot check" is modelled as: a deterministic sample
  (10% / 25%, by atom id) must be reviewed by a person; the rest may be decided by an
  `auto_reviewer` actor.
- Conflicts are detected only between atoms that share a `key` with different content.
- **Residual risk:** reviewer throughput is the bottleneck, and under SLA pressure people
  rubber-stamp. Watch `reviewer_overturn_rate` and the 48 h retro-review deadline
  (`overdue_retro_reviews`).

## Tests

```
cd packages/hyba_trust
python -m pytest -q
```
