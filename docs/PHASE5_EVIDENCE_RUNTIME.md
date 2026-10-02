# Phase 5 — evidence-closed heterogeneous runtime

Phase 5 converts the Phase 4 accounting boundary into replayable production evidence.

## Completed software gates

- Tensor advice is an exact permutation of certified windows.
- The complete mining job is content-addressed before and after advice; mutation fails closed.
- Advice records contain input order, output order, model identity, latency, and a replay ID.
- Physical hashes remain attributed to the device and layer that executed them.
- Fleet H/s uses one concurrent wall-clock observation window.
- The `10^19 H/s` threshold has an explicit fail-closed promotion API: `enforce_floor`.
- ASIC policy is explicit: default GPU-only degradation or `require_asic=True` refusal.
- ASIC extensions are capability-negotiated. Hash, midstate, Merkle, fold-certificate, and attestation kernels are never inferred from a product name.
- Hardware result packaging rejects modeled values and empty runs.

## Boundary for the supplied L-HRAS/ASIC pseudocode

The mathematical, control, fold, intelligence, and mode implementations already present in `l_hras`, `chronus.v33`, Aethel, PULVINI, and the geodesic engine remain host-side software unless a responsive physical endpoint explicitly advertises a matching kernel and returns verifiable evidence. The runtime does **not** claim that an ASIC performs quantum computation, compresses arbitrary `2^n` amplitudes exactly, or reaches a nameplate rate without measurement.

The ASIC protocol may advertise these optional kernels:

- `sha256d_midstate`
- `sha256d_merkle`
- `fold_certificate`
- `attest_result`

Only `sha256d_scan` authorizes mining dispatch. Optional kernels are recorded but do not enter H/s.

## Reproducible commands

```bash
python -m pytest -q tests/test_three_layer_runtime.py tests/test_gpu_feedback_closure.py
python -m ruff check --select E9,F chronus aethel hyba l_hras bench experiments tests
python -m compileall -q chronus aethel hyba l_hras bench experiments tests
python bench/hardware_evidence.py job-result.json bench/results/hardware-measured.json
```

## Remaining physical gate

Run `.github/workflows/hardware-acceptance.yml` on each named target device. Attach its job-result JSON, the content-addressed hardware evidence, device/firmware identity, commit SHA, and CI run URL. No generated software fixture can close this physical gate.
