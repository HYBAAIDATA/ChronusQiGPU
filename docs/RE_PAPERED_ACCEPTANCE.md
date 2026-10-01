# Re-papered PYTHIA acceptance protocol

The previous review failed because a traceability checklist was allowed to
stand in for a behavioral test. This document replaces that practice.

## Rule

A claim is accepted only when the test exercises the behavior named by the
claim. Presence of a class name, field, comment, or function is not evidence.

## Required test classes

### 1. Structured search

The test must prove that the M32 allocator:

- covers all 32 lanes;
- does not duplicate a nonce;
- includes arbitrary starting nonces;
- preserves the negotiated job template;
- checks every visited candidate using the real SHA256d target predicate.

`chronus/mla1517/mining/solver.py` and
`scripts/re_paper_gate.py` exercise these properties.

### 2. Corpus observation

A corpus claim must carry:

- the exact source file and block range;
- the exact score function;
- the threshold and denominator;
- the PoW verification rule;
- a reproducible command;
- a matched null/control result.

A percentage such as “62% phi-resonant” is not accepted until those fields are
present. A resonance percentage is not a hashrate measurement and does not
admit a pool share.

### 3. TOE and five-intelligence path

The TOE is implemented in Python under `Intelligence/toe_bridge.py` and is
registered by the Python subsystem registry. The acceptance test must prove
that it is actually on the mining call graph:

- measured mining input enters `TOEBridge`;
- tomography/trajectory/causal-ladder output is recorded;
- the selected intelligence contributes an observable decision;
- no hardcoded theorem result or constant success is used;
- the decision changes work ordering or safety state;
- the resulting candidate still passes the independent SHA256d predicate.

The current canonical runtime has the measured chooser and proof boundary, but
its direct coordinator construction does not yet invoke TOE. That is an open
integration defect, not a research classification.

### 4. Job acquisition and submission

The live test must receive a real Stratum job, build candidates from that job,
submit only with explicit approval, and record the pool's actual response. A
local “accepted” counter, fixed nonce, or mocked socket is invalid.

### 5. iGPU and hashrate

The hardware test must prove:

- the intended OpenCL device is selected;
- the submitted kernel executes on that device;
- no CPU fallback occurred;
- work count and elapsed time come from the device/runtime;
- hashrate is derived from measured work or accepted shares under a matched
  control condition.

Until this runs on the office host, the repository may be deployment-ready but
must not claim to be online, earning, or operating at a particular hashrate.

## Gate

Run the local behavioral gate with:

```bash
python3 scripts/re_paper_gate.py
```

Run the strict deployment gate on the target host with the real device and
credentials. It must fail closed when OpenCL, MMIO, the negotiated pool job,
or the external proof adapter is unavailable.
