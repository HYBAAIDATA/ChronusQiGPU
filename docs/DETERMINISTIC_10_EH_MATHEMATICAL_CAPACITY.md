# Deterministic 10 EH/s Mathematical Capacity

Every certificate declares the exact initiation mode, rational `I`, exact
bubble fraction, and justification:

- fully packed: `I = 1`
- serialized three-block datapath: `I = 3`
- pipelined with exact bubble fraction `e`: `I = 1 + e`

The fixed SHA-256d object is a datapath, not an ISA.

For heterogeneous fleets the exact capacity is
`H_total = sum_i(M_i * N_i * f_i / I_i)`. Each fleet class is reconstructed
independently and the sum retains the truth class
`exact_mathematical_capacity_not_executed_work`.

## Exact theorem

For a formal fleet with:

- `M` chips;
- `N` cores per chip;
- exact clock frequency `f`;
- pipeline initiation interval `I` cycles/hash;

the steady-state mathematical capacity is:

```text
H = M × N × f / I
```

`FleetDesign` represents every rate as `fractions.Fraction`. No floating point, sampling, averaging, or benchmark measurement enters the certificate.

## Truth class

The certificate truth class is:

```text
exact_mathematical_capacity_not_executed_work
```

This distinction is mandatory. The equation proves the capacity of the declared abstract machine. It does not prove that protocol hashes were physically executed. Measured production accounting in `hyba.hybrid.performance` remains separate and accepts only executed SHA-256d counters over observed wall time.

## Pipeline-fill correction

The equation above is a steady-state capacity. A finite cold-start window must include pipeline latency.

For pipeline depth `L` and initiation interval `I`, one core produces:

```text
0                                      when cycles < L
1 + floor((cycles - L) / I)            otherwise
```

For the declared 3 × 64 pipeline, `L = 192` cycles. Therefore:

- `1,000,000 × 10,000 × 1 GHz` equals exactly `10^19 H/s` in steady state;
- it is slightly below `10^19 H/s` over the first one-second cold-start window;
- `1,000,001 × 10,000 × 1 GHz` clears the floor over that complete cold-start window.

The canonical `PureQuantumMathASIC.deterministic_hashrate_system()` uses the over-provisioned value so both certificates pass.

## Certificate

`HashrateCertificate` binds:

- exact design parameters;
- pipeline structure;
- exact steady-state capacity;
- optional finite-window capacity;
- floor verdicts;
- formal theorem;
- non-overclaiming truth class;
- Merkle attestation root;
- canonical SHA-256 certificate digest.

`verify_hashrate_certificate()` reconstructs the complete design and certificate. Any altered field, digest, floor, rate, pipeline parameter, verdict, or truth class is rejected.

## Envelope

`DeterminismEnvelope` certifies the lower-bound product:

```text
H_min = M_min × N_min × f_min / I_max
```

The envelope floor is met exactly when `H_min >= 10^19`. This is a theorem about declared lower bounds. It is not evidence that a physical fleet satisfies those bounds.

## Machine-checked obligations

`DeterministicMiningSystem.proof_obligations()` reports:

1. deterministic capacity;
2. exact floor condition;
3. constant-size formula;
4. certificate soundness;
5. deterministic replay;
6. physical realization — deliberately `False` in the pure-math abstraction;
7. envelope guarantee;
8. attestation integrity;
9. reproducibility;
10. separation from executed-work evidence.

The physical-realization proposition cannot be proven from design arithmetic and is never silently promoted.

## Public interfaces

```python
from turing_universal_quantum_computer import (
    DeterministicMiningSystem,
    FleetDesign,
    PipelineSpec,
    design_lattice,
    minimum_chips,
    minimum_chips_for_window,
    verify_hashrate_certificate,
)

system = TenThousandQubitSystem().deterministic_10eh_system()
assert system.certificate.steady_state_floor_met
assert system.certificate.cold_start_floor_met
```
