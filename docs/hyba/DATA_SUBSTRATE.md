# HYBA data substrate — elevation pass evidence (Pass 2)

Base: `52de55f` (final commit of the TOE intelligence elevation pass).
Report: `reports/hyba_data_substrate_elevation.json` (all sections measured
by `scripts/probe_data_substrate.py` in one run — SYNTHETIC workloads).
Archaeology: `reports/hyba_storage_archaeology.json`;
ontology map: `reports/hyba_representation_ontology.json`.

## What the substrate actually is

`aethel` is the core mathematical substrate: Binet+Zeckendorf fold/unfold
(exact, byte-identical, domain-bounded, fail-closed), a Fibonacci-indexed
`AddressSpace` whose every transition is Cassini-attested in an append-only
ledger, Galois prime-substrate composite keys, a pv-lattice manifold with
digest-pinned self-heal, and a seqlock shared-memory ABI. `mla1517.prime_db`
is the reference object-store semantics (content-addressed, verified on
write AND read, append-only lineage). `hyba.substrate.HybaSubstrate` is the
§12 facade — PUT/GET/FOLD/UNFOLD/ADDRESS/QUERY/NAVIGATE/TRANSFORM/VERSION/
ATTEST/DELETE designed from the state model, not SQL. `toe.receipts` is the
evidence chain. SQLite (`mla1517.store`), file snapshots, and
`fold_pipeline` are compatibility adapters — they carry no authority.

## Measured truths (not claims)

- **Fold is representation, not compression.** ZeckendorfVector physical
  bytes are ~2.7x raw on every dataset class; zlib beats it wherever the
  data compresses. The substrate does not reduce storage.
- **Canonical addressing is the Fibonacci INDEX.** F_1 == F_2 == 1 collides
  at the value level — index (injective for n>=3, monotonic, attested) is
  identity; value and mod-90 anchors are navigation-grade only.
- **Near-state compute exists and is measured.** Mask equality, byte
  length, and fold integrity are FOLD-NATIVE (zero payload bytes
  materialized). Prefix/suffix reads are PARTIAL-RECONSTRUCTION (only the
  needed 8-byte blocks are decoded). Content digests/searches require FULL
  reconstruction. Mask-distance is UNSUPPORTED — recorded as such.
- **Identity != location.** content_id (sha256), fold_id, logical Fibonacci
  address, and physical location are four separate layers; persist + attach
  moves the bytes without changing any identity.
- **Integrity gates precede every read.** Payload mutation, ledger
  quadruple forgery, stream reorder, missing segment, wrong address,
  truncated-journal — all detected fail-closed. Consistent-prefix
  truncation is the designed recovery path.
- **Concurrency**: 4 tenant-scoped writers x 20 puts on one ledger —
  consistent, isolated, attested. Tenant bands keep index ranges disjoint
  (declared bound: 10^4 writes per tenant band).
- **TOE integration**: stored bytes -> rows -> IntelligenceState conversion
  measured (~1.5ms for 512 floats); identical stored content reuses the
  identical observation digest — reprocessing avoided is real and measured.
- **Memory honesty**: 200 objects -> 20,490 logical bytes vs 149,190
  resident bytes. No "20x/90%" claims — the capability is content-addressed
  recall + versioning + integrity, not expansion.

## Negative results (kept, per §25)

- fold ~2.7x expansion on every dataset
- F_1=F_2 value collision; anchors many-to-one
- mask Hamming distance unsupported for content similarity
- manifold keeps up to 3 payload copies (integrity redundancy)
- serialized 11D unfold drifts ~1e-12 without the carried preimage
- total corruption of all copies -> quarantine, not recovery

## Unavailable (declared)

- native `libprimedb_storage` (absent — reference semantics only)
- GPU-persistence/zero-copy path (no HYBA device on this VM)
- embedding-vector navigation (no embedding store in the substrate)
- physical compression (does not exist — fold is representation)
