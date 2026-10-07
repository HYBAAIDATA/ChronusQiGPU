# TURING — First-Workload Readiness (owner decision document)

Status: **PROPOSAL.**  Choosing the first workload is an owner decision;
this document bounds the candidates, records what is executable today,
and proposes one canonical choice.  Nothing below claims evidence that
was not produced by a command listed here.

## What "ready" means

TURING is ready for a first workload when three things hold:

1. **The workload is defined** — a single, bounded request on the
   canonical run surface, not an open-ended "run some quantum thing".
2. **It executes end-to-end** — every pipeline stage produces its
   evidence state (`PASS`/`GATED`/`FAIL`, never silently skipped).
3. **Its evidence survives the process** — custody receipts durable on
   disk; replay and the certificate boundary verifiable after a real
   restart, not just from live objects.

## Proposed first workload (canonical, minimal, end-to-end)

A 2-qubit Bell state through the certified pipeline with durable custody:

```python
from turing_universal_quantum_computer import Program
from turing_universal_quantum_computer.pipeline import VQCRequest, run_pipeline

request = VQCRequest(
    program=Program(2).then("h", 0).then("cx", 0, 1),
    marginal_of=(0, 1),
    custody=True,
    replay=True,
    custody_dir="<bound dir>",     # durable THESEUS store — required for
)                                  # restart-grade evidence
report = run_pipeline(request)
```

Expected evidence (measured on this branch):

| Artefact | Contract |
| --- | --- |
| `report.verdict` | `PASS` |
| stage states | all `PASS` except `chronus_lane` `GATED` (CPU-only box — declared, not hidden) |
| custody receipts | exactly {`program`, `result`, `witness`, `certificate`}; every `durable_index` non-`None` |
| replay | all `PASS`, run against a re-attached store — `digest_verified`, `theseus_verify`, `recovered` all true |
| restart replay | `SharedTuring.replay()` after `CompositionRoot` restart: `passed` via `replay_source="durable_graph"` |

Program digest (deterministic, reproducible across hosts):

```
e279d3382249cd8020b0027024500d664336e2a6933ee2708c1add14395c1c2e
```

Not deterministic per run — record but do not equality-assert: custody
`uid`s (uuid4), `certificate_digest` (embeds the run nonce), witness
timestamps.  The *contents* are content-addressed and digest-verified;
the identifiers are per-run.

## Reproduction fixtures (executable, in tree)

- `turing_universal_quantum_computer/tests/test_vqc_custody_durable.py` —
  commit → close → fresh-process `open_custody(durable_dir)` → recover →
  replay; durable `durable_index` asserted; in-process-only custody
  asserted to keep the honest short guarantee.
- `tests/test_shared_system_relations_production.py::
  test_turing_replay_recovers_boundary_from_durable_graph_after_restart` —
  canonical shared path: `CompositionRoot` restart, then
  `turing.replay()` resolves program/result/certificate/witness from the
  durable binding graph and the certificate boundary passes.
- `turing_universal_quantum_computer/tests/turing_custody_restart_child.py`
  — the fresh-process helper (same convention as
  `tests/euclid_custody_restart_child.py`).

## Alternatives the owner may prefer

| Candidate | Exercises | Cost |
| --- | --- | --- |
| QASM-parsed request (`qasm=` instead of `program=`) | the parse/refusal boundary | same machinery, adds parse stage |
| `mining.fault_tolerant_asic` capacity verification | the capacity surface (Mining) | **not a run workload** — mathematical capacity only; recommended as the *second* workload |
| `verify_pure_quantum_math.py` reproduction | capacity certificate + self-checks | already executable: exit 0, 6/6 checks, `exact_mathematical_capacity_not_executed_work` |

The Bell request is proposed as first because it is the smallest request
that touches every evidence stage — validate → compile → execute →
measure → verify → custody → replay — including the restart boundary.

## Measured state on this branch (what the read-only audit could not run)

- `pytest turing_universal_quantum_computer/tests/` — executed (see PR
  evidence pack for counts)
- `scripts/verify_pure_quantum_math.py` — exit 0, all six checks true
- Lean proofs — five theorems verified by source read
  (`PureQuantumMath.Axioms.lean`); compilation unverifiable on this host
  (no toolchain) — now additionally built in CI on
  `turing_universal_quantum_computer/formal`
- GPU/QPU stages — `GATED` on this host by construction

## Deferred to the owner

- The literal first workload (the Bell proposal above vs an alternative).
- Whether `chronus_lane=GATED` on CPU-only hosts is acceptable for the
  first-workload sign-off, or a GPU host is required.
- The capacity-surface workload ordering.
