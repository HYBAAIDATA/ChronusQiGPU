# Kellogg tensor capability — production readiness

Kellogg is the repository's **tensor capability** boundary (canonical
subsystem map: KELLOGG = tensor, THESEUS = custody, TURING = independent
VQC, AL HARAS = security/governance). This document is the operator-facing
production-readiness statement for the tensor execution route — what runs,
what is verified at execution time, what custody guarantees exist, and what
is explicitly **not** claimed.

## Production route

```text
POST /api/v1/tensor/execute            (control_api.py::_tensor_execute)
  → AL HARAS boundary                  (400 TENANT_AND_ACTOR_REQUIRED if unauthenticated)
  → guardian evidence evaluation       (TOE provider; ALLOWED/denied receipt)
  → tensor.api.TensorRuntime.execute   (default_runtime())
      ├─ folded path   — lifted / materializing / committed ops on resident fold states
      └─ backend path  — BackendRegistry-resolved engines (e.g. numpy-cpu)
  → tensor.verification                (independent re-check, before custody)
  → aethel.fold_store custody          (content-hashed, atomic-commit blocks)
  → tensor.execute/1 record            (verification block + tensor.receipt/1 receipt)
```

The `implementation_path` is registered in `governance/api_registry.yaml`
under `kellogg.tensor.execute` (`HTTP_PRIVILEGED`, `AL_HARAS_SUBSCRIPTION`,
truth_class `VERDICT`, reliability `R2`).

## Execution-time verification

`tensor/verification.py` re-derives every executed output on a codepath
that shares no code with the path under test, **before** the result reaches
custody or a receipt:

| Executed path | Independent re-check |
|---|---|
| folded (lifted / materializing / committed) | `verify_folded_output` — unfolds resident states and recomputes through the catalogue's `np_reference` (NumPy) |
| backend | `verify_backend_output` — refolds operands and recomputes through `folded_execute` |

- **Divergence is refused, not reported.** A failing re-check raises
  `tensor.errors.TensorVerificationError` before any custody write — a
  wrong computation cannot produce a passing record.
- **`correctness` on the receipt** is `verified` only when the re-check
  passed; operations with no independent path honestly report
  `unverified`. Nothing fabricates a pass.
- **Tolerances follow the declaration.** `bit_identical` ops (kron, the
  lifted elementwise family) require exact equality; reassociating ops
  (matmul) verify within `REASSOCIATION_RTOL = 1e-12`.

Each `tensor.execute/1` record and its `tensor.receipt/1` receipt carry a
`verification` block: `recomputed`, `method`, `verdict`, `max_residual`,
`output_digest`, `reference_digest`, `tolerance`, `elapsed_ns`, `detail`.

## Custody

Resident tensors live in `aethel.fold_store.PersistentFoldStore` — the
THESEUS-domain custody substrate:

- every block version is content-hashed (SHA-256 over dtype/shape/segment
  bytes) and verified on read/restore — tampered blocks fail closed;
- `commit_region` is atomic and exactly-once (`expected_version` +
  unique `commit_id`);
- `checkpoint()` persists the whole fold graph to one `.npz` artifact;
  `restore()` rebuilds it, re-verifying every content hash.

## Attestation

`kellogg.attest()` binds a record into an integrity attestation (digest +
version lock + Zeckendorf/Cassini tokens). It is an **integrity
certificate, not a correctness proof** — `theorem_proven` is always
`False`. Correctness evidence is receipt-level verification above.

## First workload

`kellogg.first-workload/1` — contract in
[`FIRST_WORKLOAD.md`](FIRST_WORKLOAD.md), executor
[`scripts/kellogg_first_workload.py`](../../scripts/kellogg_first_workload.py).
Status: **PROPOSED — `owner_approval: pending`**.

Stages: custody of deterministic float64 inputs → committed `kron` →
independent re-check → attestation → checkpoint → restore into a fresh
store → re-execution replay asserting identical output `content_hash`.
Emits a `kellogg.first-workload-verdict/1` JSON bound to the executing
commit's `git_head`.

```bash
python scripts/kellogg_first_workload.py --workdir <dir>
# exit 0 iff every stage passes
```

## Exact-substrate parity

`tests/test_exact_tensor_parity.py` applies shared gate fixtures to both
`Q(ζ_8)` exact state-vector implementations (kellogg and TUQC) and asserts
amplitude equality: gate inventory, per-gate basis states, a shared
Clifford+T program (amplitudes + Born probabilities), QFT in both
directions, all eight `z_eighths` powers, and canonical digest equality.
Fail-closed asymmetry is asserted, not smoothed (kellogg `NotInF4`
subclasses `NotImplementedError`; TUQC raises the bare class and has no
`rz`).

## Evidence

| Claim | Verification |
|---|---|
| Independent re-check on the real route | `tests/test_tensor_verification.py` — verified verdicts, divergence refusal (folded + backend), corrupted-block integrity+verdict failure, uncheckable-op honesty |
| Receipt binding | `receipt.verification` deep-equals the record block; `correctness` tracks verdict |
| Custody integrity | `tests/test_fold_store.py`; checkpoint→restore→replay in the first workload |
| HTTP surface | `test_production_api_contract.py`, `test_tensor_runtime.py`; live E2E on the Windows devinbox (guardian-denial ladder + both paths verified over real HTTP) |
| First workload executed | sealed engineering pack `evidence/devin/kellogg-first-workload-closure/` |

## Explicit boundaries (not claimed)

- **Owner approval** of `kellogg.first-workload/1` as *the* canonical first
  workload — the contract is PROPOSED and self-labeled.
- **Hardware execution.** No GPU/device path was exercised or claimed; the
  verified evidence is host CPU.
- **Formal proof.** `attest()` binds integrity; `theorem_proven` stays
  `False` by construction.
- **Exact-plane workload arm.** fw/1 exercises the float64 committed
  plane; exact-substrate evidence is the parity test suite above.
- **Lifted zero-copy accounting is measured, not estimated:**
  `bytes_decoded`/`bytes_transferred` are measured fields;
  `bytes_analytical` is the dense estimate — they never merge in a receipt.
