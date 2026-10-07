# Fail-Closed Virtual Accelerators

**An ABI and Evidence Model that Separates Schedule, Substrate, and Consensus Truth**

Status: spine implemented in-tree (`chronus/paradigm`). Not a peer-reviewed publication.  
Claim ID: `c-paradigm-thesis-v1`  
ABI: `virtual_igpu_v1`

---

## Abstract

Heterogeneous runtimes silently substitute CPU paths for missing accelerators,
inflate trust from content hashes, and market search *order* as cryptographic
*advantage*. We specify a versioned virtual-accelerator ABI whose receipts bind
workload identity, executed backend, digests, and an explicit trust class;
algebraic schedules are typed as permutations of classical work and never
replace SHA256d or pool acknowledgement. A machine-checked triad — ordering
lemma, software conformance, honest bakeoff, honesty chaos — gates the spine.

## 1. Problem

1. Silent fallback (requested OpenCL → CPU reported as device success).  
2. Trust inflation (SHA-256 of a receipt sold as hardware root).  
3. Schedule mystique (φ/golden walks sold as PoW advantage).  
4. Unreproducible performance sentences in release text.

## 2. Thesis

Chronus provides a versioned, fail-closed virtual accelerator ABI whose receipts
bind workload, backend, digest, and trust class; algebraic schedules may reorder
classical work but never substitute for SHA256d or pool acknowledgement.

## 3. ABI and trust lattice

| Field | Role |
|-------|------|
| `delivery_mode` | embedded / sidecar / remote (where the client talks) |
| `execution_policy` | standalone_software / preferred_accelerator / required_* |
| `actual_adapter_id` | what ran |
| `trust_class` | runtime_signed · device_observed · hardware_rooted · unavailable |
| `hardware_rooted` | true only with a verified mechanism — never from a hash alone |

Code: `chronus/virtual_igpu/abi.py`, `runtime.py`, `evidence.py`.

## 4. Algebraic schedule as permutation

Lemma G (`golden_stride_bijection`): stride \(s=\lfloor 2^{32}/\varphi\rfloor\) is odd,
hence \(\gcd(s,2^{32})=1\), hence \(i\mapsto \mathrm{seed}+i\cdot s\pmod{2^{32}}\)
is a bijection of the nonce domain.

**Not a proof of:** SHA256d prediction, mining speedup, quantum advantage,
Millennium problems. (`theorem_proven: false` pinned.)

Code: `hyba/operating_model/lemma.py`, `chronus/paradigm/schedules.py`.

## 5. Mining case study

- Accept predicate: `sha256d(header || nonce) ≤ target` (little-endian u256).  
- Pool ack is a separate truth class (pending live gate).  
- Bakeoff: sequential vs golden_stride vs phi_tier on identical headers/targets.  
- Report always includes `negative_result` and `advantage_claimed: false`.

Code: `chronus/paradigm/bakeoff.py`.

## 6. Negative results (first-class)

| Claim | Status |
|-------|--------|
| Lucas/Pisot quantum speedup | REFUTED (`al_haras`) |
| Asymptotic speedup (`p-exponential-speed`) / throughput at the governed 1e19 H/s hashrate ceiling presented as achieved (`p-throughput-eh`) / 20k GPU equivalence (`p-gpu-equivalence`) | PROHIBITED |
| Content hash ⇒ hardware_rooted | Forbidden by trust model |
| Ordering ⇒ SHA256d advantage | Not claimed; bakeoff may show sample wins without generalization |

## 7. Conformance suite

`chronus.paradigm.conformance` / `python -m chronus.paradigm`:

- ABI identity, empty-adapter refuse, required-adapter refuse  
- Software path trust ≤ runtime_signed / device_observed  
- Evidence chain linkage, attestation tamper detection  
- Honesty chaos: quota, missing device, liar hardware adapter  

Pending (listed, not silent): physical OpenCL, hardware-rooted keys, live pool,
third-party repro.

## 8. Reproducibility

```bash
python -m chronus.paradigm --json
python -m pytest tests/test_paradigm_spine.py -q
```

Artifact: triad JSON with `artifact_digest` (SHA-256 of report body).

## 9. What would make this field-defining

1. Independent lab runs the conformance suite on their GPU.  
2. One external systems venue artifact evaluation.  
3. `virtual_igpu_v1` adopted as a conformance target by a second implementation.  
4. Every public performance sentence cites a `claims.yaml` ID.

Until then: **spine**, not medal.
