# Kellogg First Workload — `kellogg.first-workload/1`

Status: **PROPOSED — pending owner approval** (`owner_approval: pending`).
This is the concrete workload contract the first-workload readiness audit
(`QuantumPhi2/PhiMiner` @ `1fde89ec`) found missing. It names one workload,
its planes, its certificate binding, and its success criteria; the executor
is `scripts/kellogg_first_workload.py`, which emits a JSON verdict bound to
the executing commit.

## Workload definition

Kellogg's workload shape is
`operation request → field/plane selection → tensor computation →
receipt/attestation → custody → replay/verify`.

| Field | Value |
|---|---|
| `workload_id` | `kellogg.first-workload/1` |
| Operation | `kron` (Kronecker product), committed folded path |
| Inputs | `a`: 4×4 float64 (seed 11, `np.random.default_rng`), `b`: 4×4 float64 (seed 13) |
| Output | 16×16 float64 resident block + `tensor.execute/1` record |
| Plane selection | float64 committed; `bit_identical=True` (element-exact vs `np.kron`) |
| Certificate binding | `receipt.verification` (independent re-check) + `kellogg.attest()` over the published record |
| Custody | `aethel.fold_store.PersistentFoldStore` checkpoint (`.npz`) → `restore` in a fresh store → content-hash verification on every version |
| Replay/verify | re-execute `kron` on the restored store; output `content_hash` must equal the original run's |

## Success criteria

1. `record.verification.verdict == "pass"` and
   `record.receipt.correctness == "verified"` — the committed output was
   re-derived on the unfolded reference path element-exactly.
2. Custody round-trip: `PersistentFoldStore.checkpoint()` →
   `PersistentFoldStore.restore()` preserves every block's
   `content_hash` (integrity-verified restore, fail-closed on tamper).
3. Replay: a second `execute("kron", ["a","b"])` against the restored
   store produces an `output_hash` identical to the first run's.
4. Attestation: `kellogg.attest()` binds the record digest + version
   lock + Zeckendorf/Cassini tokens — an integrity certificate,
   explicitly *not* a correctness proof (`theorem_proven=False`,
   correctly).

## Custody-contract resolution (audit P1 #5)

`docs/SERVICE_CONSTITUTION.yaml` lists `theseus.custody` as a dependency
of `kellogg.tensor.execute`. `PersistentFoldStore` is Aethel's fold
custody — the triad's THESEUS-domain substrate — and satisfies the
declared contract surface: content-addressed records (SHA-256 over
dtype/shape/segment bytes per version), integrity (verified on restore,
fail-closed), and provenance (version lineage + commit ids). The
workload's stage-3 assertions exercise exactly those three properties;
a contract check that cannot run on restored custody has no standing.

## HTTP route trace (audit P1 #4)

`POST /api/v1/tensor/execute` → `control_api._tensor_execute` →
`_tensor_runtime()` → `tensor.api.default_runtime()` →
`TensorRuntime.execute` (`chronus/mla1517_platform/python/control_api.py`,
handler table `"_POST_TABLE"`). The constitution's
`kellogg.tensor.execute` declaration maps to this handler; linkage is
concrete and tested in `tests/test_tensor_runtime.py
::test_control_api_tensor_endpoints`.

## Reproduction

```
python scripts/kellogg_first_workload.py --workdir <dir>
```

Exit 0 and `verdict: "pass"` in the emitted JSON. The verdict binds
`git_head`, per-stage digests, and both `output_hash` values (original +
replayed).

## Explicitly not claimed

- Owner approval of this workload as *the* first workload (contract
  status is PROPOSED).
- Exact-plane (F4) coverage: this workload exercises the float64
  committed plane. Exact-substrate parity evidence lives in
  `tests/test_exact_tensor_parity.py`.
- Hardware execution: no GPU/device claim anywhere in this contract.
