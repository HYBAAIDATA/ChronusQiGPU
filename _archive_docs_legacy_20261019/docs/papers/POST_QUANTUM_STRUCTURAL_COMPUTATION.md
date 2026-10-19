# From Classical Execution to Quantum Algorithms to Post-Quantum Structural Computation

## Abstract

This paper defines a performance and truth framework for the next stage of the
PYTHIA/AETHEL/Tensor/TURING/iGPU system. It separates three different things
that are often conflated:

1. **Classical execution** — exact or approximate algorithms executed by CPU,
   OpenCL, or other classical hardware.
2. **Quantum computation** — algorithms executed under a quantum resource model,
   with qubits, quantum gates, oracle/query assumptions, measurement, and
   physical or fault-tolerant implementation requirements.
3. **Post-Quantum Structural Computation (PQSC)** — the proposed PYTHIA stage:
   exact mathematical state and operator construction, deterministic structural
   scheduling, Lucas/Pisot index ladders, AETHEL state transport, Tensor
   transformations, TURING ordering, and classical iGPU execution.

PQSC is a project-defined term in this paper. It is **not** a claim of physical
quantum computation and it must not be confused with post-quantum cryptography.
Its performance must be measured as classical wall-clock performance, dispatch
efficiency, work coverage, and exactness—not as an assumed quantum speedup.

The central rule is:

> Lucas/Pisot structure may change ordering, scheduling, representation, and
> control-plane cost. It does not multiply raw SHA-256d throughput unless a
> benchmark measures that change on the same work and hardware.

## 1. Scope and system boundary

The repository's production path is documented as:

```text
Stratum job
  → exact header and target construction
  → AETHEL state/storage boundary
  → Tensor fold/transformation
  → TURING deterministic nonce schedule
  → iGPU/OpenCL SHA-256d execution
  → independent target verification
  → stale-job gate
  → mining.submit
  → pool boolean acknowledgement
```

This is an implementation path, not proof of quantum hardware or quantum
advantage. The handover audit explicitly separates source-level implementation,
mock-pool acceptance, and real-pool acceptance. [^https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/blob/main/docs/CLIENT_HANDOVER_AUDIT.md]

The repository already provides an observed-throughput harness and a solver
scaling harness. They report measured H/s and explicitly refuse Lucas/Pisot
extrapolation. [^https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/blob/main/legacy/scripts/bench_hashrate.py] [^https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/blob/main/legacy/scripts/bench_scaling_curve.py]

## 2. Stage I — classical baseline

### 2.1 Definition

The classical baseline is the same consensus workload executed without a
quantum resource assumption:

```text
fixed 80-byte header template
+ fixed target
+ fixed nonce window
+ fixed backend and device
+ fixed verifier
+ fixed duration
```

The primary measured quantity is:

\[
H_{\mathrm{classical}} = \frac{\text{unique nonce evaluations}}{\text{wall-clock seconds}}.
\]

A valid baseline must identify the backend, device, kernel configuration,
launch count, hashes, elapsed time, and truth class. A socket connection or
`mining.notify` event is not a hashrate measurement.

### 2.2 Exact classical state cost

For a dense classical representation of an \(n\)-qubit state,

\[
|\psi\rangle = \sum_{i=0}^{2^n-1} \alpha_i |i\rangle,
\]

there are \(2^n\) amplitudes. Exact arithmetic adds numerator/denominator or
algebraic-number bit complexity. A classical state-vector implementation
therefore does not inherit a quantum speedup merely because its data structure
is called a Hilbert-space vector. Classical simulation is generally limited by
exponential state growth. [^https://mqt.readthedocs.io/en/stable/handbook/02_simulation.html]

### 2.3 Baseline metrics

The baseline report must include:

- raw SHA-256d H/s;
- validated H/s, if per-digest validation is actually performed;
- unique nonce coverage;
- duplicate work percentage;
- host dispatch overhead;
- kernel time and launch count;
- device identity and backend;
- temperature, power, and memory data or explicit `null` status;
- failure/restart count;
- exact header, target, and nonce-window fingerprints.

No baseline number is licensed by this paper until the harness emits it.

## 3. Stage II — quantum computational model

### 3.1 What quantum computation changes

A quantum algorithm changes the computational resource model. Its relevant
resources can include:

- qubit count;
- circuit depth;
- gate count;
- oracle/query count;
- entanglement and connectivity requirements;
- measurement count;
- error-correction overhead;
- state-preparation and readout cost.

These are not interchangeable with CPU instructions, GPU work-items, or
classical H/s.

### 3.2 Examples of qualified quantum advantages

Grover search provides a quadratic query reduction in the unstructured oracle
model, but the oracle is an explicit resource assumption and the result does
not automatically transfer to an arbitrary classical implementation. [^https://link.aps.org/doi/10.1103/PhysRevX.14.041029]

The QFT can have a compact quantum circuit representation, but a classical
state-vector simulation must still represent and evolve the underlying state.
A QFT gate-count claim is therefore not an end-to-end classical runtime claim.
The classical FFT baseline and all state-preparation, oracle, measurement, and
hardware costs must be stated separately. [^https://arxiv.org/html/2606.18981v1]

### 3.3 What is not implied

The following do not follow from mathematical notation alone:

- exponential classical speedup;
- physical superposition;
- physical interference;
- fault tolerance;
- polynomial convergence of VQE or QAOA;
- lossless tensor compression of arbitrary states;
- automatic error correction from a topological invariant;
- accepted mining shares.

The strict quantum architecture already preserves this boundary: exact
certificates are mathematical witnesses, not consensus authorities or physical
quantum devices. [^https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/blob/main/docs/STRICT_QUANTUM_ARCHITECTURE.md]

## 4. Stage III — proposed PQSC

### 4.1 Definition

PQSC is the proposed post-quantum stage of this project:

```text
exact algebra
  → structural invariants
  → deterministic schedule compilation
  → Lucas/Pisot index selection
  → AETHEL persistence/transport
  → Tensor representation and fold
  → TURING ordering
  → classical CPU/OpenCL/iGPU execution
  → independent consensus verification
```

The term means **after the quantum-formal design stage in the architecture**,
not “more quantum than quantum” and not a proven new physical computing
paradigm.

### 4.2 Lucas index ladder

The first proposed optimization ladder is:

\[
\mathcal{L} = \{10, 12, 15, 18, 20\}.
\]

These are **indices/configuration points**, not raw throughput multipliers.
The implementation must record, for each run:

```json
{
  "scale_family": "lucas_pisot_index_ladder",
  "scale_index": 10,
  "schedule_fingerprint": "...",
  "nonce_window_fingerprint": "...",
  "backend": "opencl",
  "device": "...",
  "raw_sha256d_hps": 0,
  "scaling_efficiency": 0,
  "truth_class": "measured"
}
```

The values 12, 15, 18, and 20 must be run as separate configurations. They
must not be presented as \(10\times\), \(12\times\), \(15\times\),
\(18\times\), or \(20\times\) performance without independent measurement.

### 4.3 What Lucas structure may legitimately optimize

A Lucas/Pisot layer may be useful for:

- deterministic candidate ordering;
- schedule partitioning;
- exact state fingerprints;
- sparse or structured representation selection;
- cache and batch boundaries;
- reproducible work allocation;
- control-plane pruning where the pruning proof preserves the required work;
- dispatch overhead and queue utilization;
- candidate prioritization under a non-uniform, evidence-backed objective.

For a cryptographic hash function modeled as a random function, reordering nonce
attempts alone does not increase the probability per hash. If every nonce still
must be evaluated, the raw SHA-256d workload is unchanged.

### 4.4 What it cannot claim without evidence

PQSC cannot claim:

- raw H/s multiplied by a Lucas index;
- a quantum speedup from a classical iGPU;
- exponential mining acceleration;
- fewer consensus evaluations unless the omitted work is formally proven safe;
- pool acceptance from a schedule certificate;
- an effective EH/s number derived from one small-device measurement.

## 5. Performance comparison

| Stage | Primary resource | Correct performance metric | What is currently licensed |
|---|---|---|---|
| Classical | CPU/OpenCL/iGPU wall clock | measured unique H/s, dispatch, energy, failure rate | benchmark result only |
| Quantum algorithm | qubits, gates, queries, depth, readout | algorithmic resource count plus hardware execution | model-level complexity only |
| PQSC | exact arithmetic + schedule + classical execution | measured H/s, schedule cost, nonce coverage, efficiency | deterministic structural optimization |

The central comparison is not:

```text
classical H/s × Lucas index = PQSC H/s
```

It is:

```text
same job + same nonce window + same device
→ baseline configuration
→ PQSC configuration
→ repeated measured comparison
```

For solver count \(N\), report:

\[
\eta(N) = \frac{H(N)}{N \cdot H(1)},
\]

where \(H(1)\) and \(H(N)\) are measured under the same kernel, work-item
configuration, thermal protocol, and target host. The repository scaling
harness already treats this as an observed efficiency rather than an
extrapolation. [^https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/blob/main/legacy/scripts/bench_scaling_curve.py]

## 6. Pre-registered target vector

The requested performance hypothesis is recorded before implementation and
measurement:

| Paradigm | Expected normalized cost | Interpretation |
|---|---:|---|
| Classical baseline | **20** | reference cost for the fixed workload |
| Quantum algorithmic model | **13** | model-level resource cost, not classical wall-clock time |
| PQSC | **5** | target measured structural-execution cost |

These values are **pre-registered targets, not fabricated results**. They must
be tested against one fixed workload, one success criterion, and an explicit
unit. Because lower is better in the requested vector, the unit is interpreted
as normalized cost/time/work, not H/s. If the intended metric is H/s, the
ordering must be inverted before testing: higher H/s is better.

The three numbers are not directly interchangeable unless the experiment
defines a common cost function. The quantum value `13` is a resource-model
target unless a physical quantum backend is available. A classical simulation
that prints `13` is not evidence of a quantum result.

### Target acceptance rule

For a fixed workload `W`, record:

```text
C_classical(W)       = measured baseline cost
C_quantum_model(W)   = declared gate/query/resource cost
C_pqsc(W)            = measured PQSC cost
```

The expected target vector is:

```text
C_classical(W) ≈ 20
C_quantum_model(W) ≈ 13
C_pqsc(W) ≤ 5
```

The report must include raw values, units, tolerance, commit SHA, workload
fingerprint, device/backend, schedule fingerprint, and truth class. A test must
fail or report `unproven` when the observed result misses the target; it must
never substitute the target number so that the test passes.

## 7. Experimental protocol before optimization

No Lucas optimization should be enabled in the production path until the
following matrix exists:

| Run | Scale | Repeats | Required evidence |
|---|---:|---:|---|
| Baseline | none | 3 | H/s, device, kernel, nonce coverage |
| L10 | 10 | 3 | same workload and schedule fingerprint |
| L12 | 12 | 3 | same workload and schedule fingerprint |
| L15 | 15 | 3 | same workload and schedule fingerprint |
| L18 | 18 | 3 | same workload and schedule fingerprint |
| L20 | 20 | 3 | same workload and schedule fingerprint |

Each result must include:

- exact commit SHA;
- exact configuration;
- exact header and target fingerprints;
- disjoint nonce interval proof;
- raw H/s;
- validated H/s or explicit unavailable status;
- dispatch overhead;
- thermal/power status;
- error and restart count;
- schedule fingerprint;
- truth class.

The comparison must be run on the same host and device. Cross-host or
cross-thermal comparisons are not a scaling curve.

## 8. Falsifiable hypotheses

### H1 — Control-plane efficiency

PQSC reduces schedule construction or dispatch overhead relative to the
classical baseline while preserving the exact nonce set.

**Pass condition:** lower measured overhead with identical nonce coverage.

### H2 — Execution efficiency

PQSC increases measured device H/s by improving batching, queue utilization,
or kernel dispatch.

**Pass condition:** repeated H/s improvement on the same device with no
increase in duplicate work or validation failures.

### H3 — Cryptographic work conservation

Lucas ordering does not change raw SHA-256d cost for a fixed nonce set.

**Pass condition:** any reported gain is explained by measured dispatch,
backend, or work-coverage changes—not by an index multiplier.

### H4 — No false quantum claim

PQSC remains a classical exact structural execution layer unless a separate
physical quantum resource and a formally specified algorithm are introduced.

**Pass condition:** all reports preserve `theorem_proven: false` and label
unmeasured performance as unavailable or theoretical.

## 9. Decision gate

Before enabling the Lucas ladder in production:

1. baseline measurements exist;
2. all five scale points have repeated measurements;
3. nonce coverage is identical or formally accounted for;
4. no duplicate-work increase is hidden;
5. no raw H/s multiplier is inferred from the index;
6. exact invariants remain green;
7. independent SHA-256d verification remains authoritative;
8. real pool acceptance remains a separate operational gate.

Until those conditions are met, the status is:

```text
PQSC: implemented as a proposal
Lucas optimization: benchmark pending
quantum speedup: not claimed
physical quantum computer: not present
mining success: not claimed
```

## 10. Conclusion

Classical computation gives the measured execution baseline. Quantum
computation provides a different resource model with conditional algorithmic
advantages. PQSC is the proposed stage after the quantum-formal design layer:
an exact, deterministic, structurally optimized classical system that borrows
mathematical organization without pretending that a classical iGPU is a
quantum processor.

The phrase “what comes after quantum” is therefore retained as a project
architecture label, not as a scientific performance claim. The only licensed
speedup is the one the controlled benchmark measures.
