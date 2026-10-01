# Lucas-15 operator ablation

This experiment asks a narrow, falsifiable question:

> Does applying the exact Lucas-15 operator to a non-Grover algorithm improve a measured outcome more consistently than applying Lucas-15 only to scheduling?

## Fixed constants

- Index: `n = 15`
- Lucas value: `L15 = 1364`
- Fibonacci companion matrix: `M = [[1, 1], [1, 0]]`
- Exact operator: `M^15 = [[987, 610], [610, 377]]`
- Pisot damping: `abs(psi)^15 = 0.0007331374358574045`

No arbitrary Lucas multiplier is accepted by the harness.

## Arms

Every algorithm receives the same seeds, dimensions and workload:

1. `baseline`
2. `lucas15_schedule` — permutation only; no operator claim
3. `phi_pisot`
4. `m15` — exact matrix-power operator, normalized by `phi^15`
5. `m15_golden_eigenbasis` — the same operator constructed in its eigenbasis

The algorithms are QAOA, VQE, quantum walk, QML kernel, time evolution,
QEC/syndrome separation and QFT structural comparison. Grover and mining are
excluded from the ablation.

## Run

```bash
python experiments/lucas15_operator_ablation.py \
  --repeats 20 \
  --dimension 64 \
  --seed 1517 \
  --output artifacts/lucas15_operator_ablation.json
```

The JSON retains every trial plus grouped medians. Measurements include wall
clock, operator applications, iterations, objective/error, spectral
concentration, numerical stability, peak memory and measured NumPy throughput.
The current backend is explicitly `numpy_cpu`; it does not fabricate iGPU
throughput. An accelerator result must name and attest the device that executed
it before it can be added.

## Mining boundary

`PYTHIA_NONCE_ORDER=lucas15` enables a coverage-complete nonce permutation
derived from the exact `M^15` coefficients. It is the schedule-only control arm.
It does **not** replace Bitcoin's double-SHA-256 work function and does not make
CPU/GPU mining physically quantum.

Live telemetry therefore reports these facts separately:

- `hash_execution_model = physical_sha256d`
- `hash_acceptance_authority = pool_target`
- `physical_quantum_hardware_active = false`
- `quantum_simulation_in_hash_path = false`
- `lucas_15_schedule_active = true|false`

A non-classical mining claim requires an actual quantum execution backend and
end-to-end evidence that it produced candidates accepted by the unchanged pool
target. Numerical simulation and QOps telemetry are not that evidence.
