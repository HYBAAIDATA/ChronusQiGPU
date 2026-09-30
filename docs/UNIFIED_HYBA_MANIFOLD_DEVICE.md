# Unified HYBA Manifold Hashing Device

**Status:** historical design, not a production authority.

The previously cited `Intelligence/unified_manifold_device.py` and
`tests/test_unified_manifold_device.py` do not exist in the production tree;
their implementations remain under `legacy/`. Several paths later in this
document are therefore descriptive mappings, not deployable entry points.

Production authority is split across:

- `aethel.manifold` for integrity-checked storage, geodesic navigation and
  self-healing;
- `gpu.manifold` for the canonical lazy package facade;
- `gpu.reference` and `igpu` for SHA-256d reference and OpenCL execution;
- `turing_universal_quantum_computer` for the exact virtual-quantum substrate;
- `gpu.readiness` for fail-closed software and physical-evidence gates.

The 32-face `UnifiedManifoldHashingDevice` must not be advertised as a
production feature until it is promoted from `legacy/`, its imports are
rewired to canonical modules, and its tests run in the normal CI suite.

---

## 0. Claim boundary (read first)

> The 32-face compass and 11D Poincaré-golden manifold are a probe-ordering /
> sharding front-end only. `sha256d(header80) <= negotiated target` is the sole
> accept authority; no nonce prediction, nonce-probability shift, or
> proof-of-work advantage is asserted.

This was `CLAIM_BOUNDARY` in the legacy unified-device implementation. It
restates boundaries the production repository enforces elsewhere:

* `Intelligence/search_crystal.py` (module docstring):
  > The 32 face normals define deterministic work shards and traversal order. A
  > Cassini-certified affine permutation visits every nonce in a shard exactly
  > once. Geometry changes ordering only; it never replaces the consensus oracle
  > and never permits an unsearched shard to be pruned.
* `Intelligence/poincare_cassini_search.py` (`DodecaIcosahedron32` boundary string):
  > Geodesic state-space traversal only; no nonce-probability or proof-of-work
  > advantage is asserted.
* `Intelligence/four_layer_stack.py` (module docstring):
  > Consensus: sha256d(header[:76] + LE(nonce))[::-1] < target. Nothing in these
  > four layers can accept a share without it.

Consequences that the code enforces, not merely states:

1. Geometry may change **which nonce is hashed next**. It may not skip a nonce,
   prune a shard, or declare a nonce valid. `ManifoldShardOrder.faces_pruned`
   is always `0`, and `iter_nonces()` is a complete permutation of the interval.
2. `accepted is True` requires all of: a winning nonce from the real grind, the
   four-layer bit-exact recheck, and `mla1517.mining.pow.check_pow(header80,
   target)` — i.e. `int.from_bytes(sha256d(header80), "little") <= target`.
3. Hashrate is only ever the value measured by the hasher that actually ran.
   When no hasher runs the result carries `hashes_computed = 0`,
   `measured_hashrate = 0.0`, `truth_class = "unavailable"`,
   `hardware.status = "NOT_RUN"`.
4. `theorem_proven` is `False`. Nothing here is a theorem about SHA-256.

---

## 1. Concept → real module map

Every concept from the three drafts, mapped to what actually exists in this
repository. Paths of the form `HYBA_Phi-main/...` used in the drafts **do not
exist** here and must not be cited.

| Draft concept | Draft path (wrong) | Real implementation |
|---|---|---|
| 32-face compass (12 dodecahedron + 20 icosahedron faces) | "Dodecahedron/Icosahedron compatibility" doc | `Intelligence/poincare_cassini_search.py` → `DodecaIcosahedron32` (each face Cassini-certified at construction, `cassini_determinant ∈ {−1, +1}`) |
| Face → work shard / traversal order | "lane ordering" | `Intelligence/search_crystal.py` → `partition_interval`, `cassini_permutation`, `PoincareCassiniSearchEngine._candidate_stream`; entrypoint `Intelligence/orchestrator.py` → `agentic_search` |
| 11D Poincaré ball, fold / unfold, geodesic, Zeckendorf certificate | `HYBA_Phi-main/native_kernels/...` | `Intelligence/poincare_golden_11d.py` → `compute_poincare_norm_sq`, `poincare_golden_distance`, `fold_poincare_11d_vector`, `unfold_poincare_11d_vector`, `compute_zeckendorf_certificate` (**read-only substrate**, see `docs/ASI_INTERFACE_MAP.md`) |
| Golden metric weights | `g_ii = φ^(i/11)` (wrong) | `φ^{-(i+1)}`, i = 0..10 — `PHI_POWERS` in `poincare_golden_11d.py`, `GOLDEN_WEIGHTS` in `poincare_cassini_search.py` (§2) |
| Storage + fold + Turing schedule + score/reorder/grind pipeline | "kernel specification" | `Intelligence/four_layer_stack.py` → `FourLayerMiningStack`, `NearStateIGpu.mine` (calls the real hasher and rechecks the winner with sha256d) |
| "Device" / iGPU hashrate | `HYBA_Phi-main/solutions_api`, "Metal shader" | `mla1517_platform_v3.4/python/mla1517/mining/opencl_driver.py` → `OpenCLDriver.execute_kernel` (fails closed without pyopencl / device); standalone `mining/bitcoin_hasher.py` |
| Bespoke HYBA iGPU identity / selection | — | `hyba/device.py` (`DEFAULT_HYBA_ALIASES`, `HYBA_DEVICE_ALIAS`, `HYBA_REQUIRE_HYBA`), `hyba/select.py`, `mining/bitcoin_hasher.py::_select_opencl_device` |
| Accept authority | "solutions API" | `mla1517_platform_v3.4/python/mla1517/mining/pow.py` → `sha256d`, `check_pow` |
| Native kernels | `HYBA_Phi-main/native_kernels` | OpenCL sources under `mla1517_platform_v3.4/kernels/*.cl` (`exact_quantum_kernel.cl`, `mla1517_lucas_pisot_scale.cl`); `Intelligence/mining_native.py` documents which "native targets" exist |
| Salamander | `HYBA_Phi-main/salamander` | `Intelligence/salamander.py`, `salamander_agentic.py`, `salamander_transaction.py` — self-healing / self-optimising substrate; **not part of the hashing path** |
| Metal shaders | `HYBA_Phi-main/metal/*.metal` | **None.** There are no `.metal` files in this repository. The only GPU language is OpenCL C. |
| Solutions / control API | `HYBA_Phi-main/solutions_api` | `mla1517_platform_v3.4/python/control_api.py` (`/api/health`, `/api/v1/readyz`, `/api/v1/mla1517/status`, `/api/v1/telemetry/summary`) served by `main.py` |

Note: `kernels/bitcoin_sha256d.cl` is checked in, with packaged copies under
`igpu/kernels/` and the Turing VQC package. Availability still requires a
working OpenCL runtime and target device.

---

## 2. Geometry

### 2.1 Metric (corrected)

The drafts wrote `g_ii = φ^(i/11)` (increasing). That is wrong and would break
the existing roundtrip and geodesic tests. The metric used throughout the
repository is the **decreasing** golden weighting

    w_i = φ^{-(i+1)},   i = 0 … 10

`Intelligence/poincare_golden_11d.py`:
`PHI_POWERS = np.array([PHI ** (-i) for i in range(1, 12)])`, and
`Intelligence/poincare_cassini_search.py`:
`GOLDEN_WEIGHTS = np.array([PHI ** -(i + 1) for i in range(DIM)])`.
Both are the same vector.

The weighted Poincaré norm is `compute_poincare_norm_sq(v) = Σ w_i v_i²`, the
ball is `norm_sq < 1`, and `poincare_golden_distance` is the hyperbolic distance
in that weighted ball.

### 2.2 Fold / unfold

`fold_poincare_11d_vector(v) -> (folded, reflections)` reflects `v` into the
open ball; `unfold_poincare_11d_vector(folded)` inverts it. The folded array
carries its preimage payload (`PoincareFoldedArray`) so the roundtrip is exact
to `< 1e-14` max-abs error — the contract stated in `docs/ASI_INTERFACE_MAP.md`
and asserted by `tests/test_unified_manifold_device.py`.
`compute_zeckendorf_certificate(folded, context_id=...)` yields a stable token
used only as a provenance label.

The unified device derives the 11-vector from `sha256(header80[:76])` (first 11
bytes, affine-mapped into `[-1, 1]`), folds it, and records
`ManifoldFoldRecord` with `truth_class = "mathematical"`.

### 2.3 32-face compass

`DodecaIcosahedron32` builds 12 dodecahedron and 20 icosahedron face normals
in 11D. Each face carries a Cassini order and determinant which must be ±1;
construction raises otherwise. The device exposes the counts and the
certification flag in `result["compass"]`.

### 2.4 Complete-coverage sharding

`shard_order(header80)`:

1. `partition_interval(nonce_start, nonce_space, 32)` → 32 contiguous shards
   covering the interval exactly (some may be empty for tiny intervals).
2. Face order = faces sorted by descending affinity
   `compass.directions @ (GOLDEN_WEIGHTS * folded)` (ties by index). This is the
   *only* header-dependent geometric choice, and it changes order alone.
3. Per face, `cassini_permutation(width, face_id, seed)` — an affine permutation
   with stride coprime to the width, hence a bijection on the shard.
4. `iter_nonces()` interleaves the 32 per-face schedules round-robin exactly as
   `PoincareCassiniSearchEngine._candidate_stream` does, so every nonce in the
   interval is yielded exactly once. `faces_pruned == 0` always.

Test guarantees: for a 4096-nonce interval the emitted sequence is a permutation
of `range(nonce_start, nonce_start + 4096)` (no duplicates, nothing missing);
identical headers give identical `schedule_digest`; different headers give a
different order over the **same** nonce set.

---

## 3. Grind and acceptance

`run(header80, target_be, n_candidates=256, max_hashes=None, allow_cpu_reference=False)`:

1. Validates `len(header80) == 80`, `len(target_be) == 32`.
2. Computes the fold record and the full shard order; takes the first
   `n_candidates` nonces as the probe list.
3. Stores the header via `FourLayerMiningStack.aethel.store(...)` (layer 1).
4. Hardware gate (§4). If closed and `allow_cpu_reference` is `False`: **no
   hashing happens**; the result is `unavailable` / `NOT_RUN`.
5. Otherwise `NearStateIGpu.mine(header80, target_be, probe, max_hashes=...)`
   runs the real double-SHA256 grind and returns the measured
   `hashes_computed`, `elapsed_seconds`, `measured_hps`, `hasher_backend`,
   `winning_nonce`, `winning_hash`, `recheck_bit_exact`.
6. `accepted = winning_nonce is not None and recheck_bit_exact and
   sha256d(header76 + LE(nonce)) == winning_hash and check_pow(full_header,
   int.from_bytes(target_be, "big"))`. Anything short of this yields
   `accepted = False, winning_nonce = None`.

`truth_class` follows `OpenCLExecutionResult.TRUTH_CLASSES`:

| Situation | `truth_class` | `hardware.status` |
|---|---|---|
| No pyopencl / no device / no HYBA device under strict mode, CPU not allowed | `unavailable` | `NOT_RUN` |
| OpenCL hasher ran | `measured_hardware` | `RUN` |
| `allow_cpu_reference=True` and CPU hasher ran | `measured_cpu_reference` | `RUN` |

`measured_hardware` is only reported when `hasher_backend` starts with
`opencl`; a CPU grind is never relabelled as hardware.

---

## 4. Hardware boundary and the bespoke HYBA iGPU

`OpenCLDriver` (`mla1517/mining/opencl_driver.py`) enumerates devices via
pyopencl; missing pyopencl or zero devices gives `available = False`, and
`execute_kernel` raises rather than falling back to CPU. The unified device
adds the HYBA identity contract from `hyba/device.py` on top:

* `hyba_devices` = enumerated devices whose OpenCL name contains one of the
  aliases (`HYBA_DEVICE_ALIAS`, default `hyba-mla1517, hyba_mla1517, mla1517,
  hyba`).
* `hardware_available = driver.available and (hyba_devices or not
  require_hyba())`.
* With `HYBA_REQUIRE_HYBA=1` (the Docker default) a machine that only exposes a
  non-HYBA GPU is treated as **no hardware**: nothing is substituted, the result
  is `unavailable`. This is the "bespoke iGPU is always the default" rule; it is
  the same strictness `mining/bitcoin_hasher.py::_select_opencl_device` and
  `hyba/select.py` already apply.

`result["hardware"]` carries `device_name`, `hyba_alias` (the alias that
matched, or `None`), `require_hyba`, `hardware_execution`, `fallback_used`,
`degraded`, plus the measured counters.

### 4.1 Docker

* `Dockerfile` installs `ocl-icd-libopencl1`, `intel-opencl-icd`, `clinfo` and
  sets `HYBA_REQUIRE_HYBA=1`.
* `docker-compose.yml` forwards `HYBA_REQUIRE_HYBA` (default `1`) and
  `HYBA_DEVICE_ALIAS` from the host environment.
* `docker-compose.override.yml` (auto-loaded by plain `docker compose up`) keeps
  the container device-less → fail-closed `unavailable`.
* `docker-compose.igpu-linux.yml` binds `/dev/dri` (+ `video`/`render` groups)
  on a Linux host.
* `docker-compose.igpu-wsl2.yml` binds `/dev/dxg` and mounts `/usr/lib/wsl`
  for Docker Desktop on Windows (WSL2 backend).
* Probe: `docker compose -f docker-compose.yml -f docker-compose.override.yml
  -f docker-compose.igpu-wsl2.yml --profile probe run --rm igpu-probe` runs
  `clinfo` inside the container.

What is **not** verified by this repository: that Intel's Linux OpenCL runtime
(`intel-opencl-icd`) enumerates a Gen9.5 part such as UHD 620 through the WSL2
`/dev/dxg` paravirtual device. If `clinfo` in the probe container shows no
device, the miner stays `unavailable` — by design it will not hash on anything
else. In that case the honest options are a host-native run or a Linux host
with `/dev/dri`.

If the bespoke device enumerates under a name that does not contain a default
alias, set `HYBA_DEVICE_ALIAS` to a comma-separated list containing a
substring of its OpenCL name; the strict rule still applies to that list.

---

## 5. Result schema

```
{
  "device": "unified_hyba_manifold_device",
  "accepted": bool,                       # only via check_pow
  "winning_nonce": int | None,
  "winning_hash": hex | None,
  "compass": {faces: 32, dodecahedron_faces: 12, icosahedron_faces: 20, cassini_certified: True},
  "manifold_fold": ManifoldFoldRecord.to_dict(),   # truth_class "mathematical"
  "shard_order":   ManifoldShardOrder.to_dict(),   # faces_pruned 0, coverage_complete True
  "probe_candidates": int,
  "hardware": {...OpenCLExecutionResult fields, "status": "RUN"|"NOT_RUN",
               "hyba_alias": str|None, "require_hyba": bool},
  "truth_class": "unavailable" | "measured_hardware" | "measured_cpu_reference",
  "measured_hashrate": float,             # 0.0 when NOT_RUN
  "hashes_computed": int,                 # 0 when NOT_RUN
  "igpu": NearStateIGpu.mine(...) dict | None,
  "header_store": ...,
  "consensus_rule": "sha256d(header80[:76] + LE(nonce)) <= target (mla1517.mining.pow.check_pow)",
  "claim_boundary": CLAIM_BOUNDARY,
  "theorem_proven": False
}
```

---

## 6. Things this design deliberately does not do

* Modify `Intelligence/poincare_golden_11d.py` (DO NOT MODIFY per
  `docs/ASI_INTERFACE_MAP.md`); the device composes against it.
* Reimplement the compass, fold, permutation, hasher, or PoW check.
* Fall back to CPU when OpenCL was requested (`OpenCLDriver` semantics).
* Substitute a non-HYBA device when `HYBA_REQUIRE_HYBA=1`.
* Report any hashrate that was not measured by a hasher that ran.
* Accept a share on geometric grounds.
