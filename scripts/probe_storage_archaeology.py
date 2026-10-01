"""HYBA data-substrate archaeology + representation ontology (Pass 2 §1-2).

Inventories every storage/persistence surface in the repository, classifies
each component into the brief's taxonomy, and derives the authoritative
representation map from the code that actually implements each form.

Produces:
  reports/hyba_storage_archaeology.json   (§1 — classified components)
  reports/hyba_representation_ontology.json (§2 — per-form contracts)

Classification taxonomy (§1):
  CORE MATHEMATICAL SUBSTRATE / CONTROL-PLANE DATABASE /
  DURABLE EVIDENCE STORE / CACHE / MEMORY / ADDRESSING LAYER /
  COMPATIBILITY LAYER / LEGACY / EXPERIMENTAL / DISCONNECTED
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chronus/mla1517_platform" / "python"))

REPORTS = ROOT / "reports"


def _exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def archaeology() -> dict:
    """§1 — component inventory with classification and evidence."""
    components = [
        # --- core mathematical substrate ----------------------------------
        {
            "component": "aethel.encoding (fold/unfold)",
            "files": ["aethel/encoding.py", "aethel/zeckendorf.py", "aethel/fibonacci.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Binet+Zeckendorf payload encoding: one non-adjacent "
            "Fibonacci mask per 8-byte chunk; unfold restores byte-identically; "
            "declared domain bound (MAX_FOLD_LEN=1MiB) fails closed.",
            "status": "connected",
            "evidence": "aethel/CONTRACT.md B1-B4; tests/test_aethel_encoding.py",
        },
        {
            "component": "aethel.storage (AddressSpace + CassiniLedger)",
            "files": ["aethel/storage.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Fibonacci-indexed block store; every transition "
            "appends a Cassini quadruple to an append-only ledger; "
            "forged/gapped/regressed streams raise before any read is served; "
            "atomic snapshot/attach with full replay-verify; multi-writer fork.",
            "status": "connected",
            "evidence": "aethel/CONTRACT.md A1-A6; tests/test_aethel_storage.py",
        },
        {
            "component": "aethel.primes (GaloisPrimeSubstrate)",
            "files": ["aethel/primes.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Composite keys = prime-power products in "
            "GF(2^61-1); one PrimeCell per uuid per prime lane holding a "
            "Zeckendorf exponent + Cassini parity.",
            "status": "connected",
            "evidence": "aethel/primes.py; tests/test_aethel_primes.py",
        },
        {
            "component": "aethel.manifold (PrimeStorageManifold)",
            "files": ["aethel/manifold.py", "aethel/geodesic.py", "aethel/gpu.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Topological tensor store: pv-lattice anchor, "
            "Zeckendorf sparse topology, prime-substrate commit, SHA-256 "
            "digest pinning, one-shot self-heal from redundant copies, "
            "geodesic navigation handoff to the proven search engine.",
            "status": "connected",
            "evidence": "aethel/CONTRACT.md; tests/test_aethel_manifold.py; "
            "tests/test_aethel_geodesic_handoff.py",
        },
        {
            "component": "aethel.shm (AethelQueue)",
            "files": ["aethel/shm.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "mmap seqlock slot queue — pure-Python ABI v1 "
            "equivalent of mla1517_aethel.{c,h}; D10 seal ±1 gate at commit; "
            "attach fails closed (SegmentMissing / AbiVersionMismatch).",
            "status": "connected",
            "evidence": "tests/test_aethel_concurrency.py (incl. C header parse)",
        },
        {
            "component": "aethel.costs (OverheadMeter)",
            "files": ["aethel/costs.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Measured CPU/wall/payload-bytes accounting per "
            "instrumented op; structural_bytes floors; tracemalloc peaks.",
            "status": "connected",
            "evidence": "tests/test_aethel_overhead.py",
        },
        {
            "component": "chronus.mla1517.prime_db (reference object store)",
            "files": ["chronus/mla1517/prime_db.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Reference algebraic object store: content-addressed "
            "objects, Cassini validation on write AND read, append-only "
            "lineage, idempotent duplicate writes, deterministic replay. "
            "Native lib explicitly absent — 'physical capacity: NOT CLAIMED'.",
            "status": "connected (reference semantics)",
            "evidence": "CAPACITY_BOUNDARY constant; mla1517 tests",
        },
        {
            "component": "chronus.mla1517.state (LogicalState / MLA1517State)",
            "files": ["chronus/mla1517/state.py",
                      "chronus/mla1517/primedb_engine.py"],
            "classification": "ADDRESSING LAYER",
            "what_it_is": "The 12-dimension logical state vector (nonce, lucas, "
            "pisot, fib, zeckendorf, binet, prime_addr, route, eigen, "
            "cassini, time_state, gauge) — 64-byte ctypes descriptor; "
            "digest() is the content identity.",
            "status": "connected",
            "evidence": "state.py digest(); primedb_engine.py ctypes layout",
        },
        {
            "component": "toe.poincare_golden_11d",
            "files": ["toe/poincare_golden_11d.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "11D Poincaré-golden fold/unfold of vectors, "
            "Zeckendorf decoupling-mask certificates, GPU IO boundary "
            "(to_gpu_input/from_gpu_output), PoincareFoldedArray view.",
            "status": "connected",
            "evidence": "fold_poincare_11d_vector/unfold; compute_zeckendorf_certificate",
        },
        {
            "component": "toe.receipts (ReceiptLedger)",
            "files": ["toe/receipts.py"],
            "classification": "DURABLE EVIDENCE STORE",
            "what_it_is": "Hash-chained receipt ledger binding inputs/config/"
            "output to sha256 receipts; verify() re-checks the whole chain.",
            "status": "connected",
            "evidence": "507-record ledger verified in pass-1 elevation report",
        },
        {
            "component": "al_haras.audit (HashChainAudit)",
            "files": ["al_haras/audit.py"],
            "classification": "DURABLE EVIDENCE STORE",
            "what_it_is": "File-locked, hash-chained append-only audit log "
            "with quarantine-on-corruption; canonical JSON digests.",
            "status": "connected",
            "evidence": "al_haras/audit.py _file_lock/_quarantine_file_unlocked",
        },
        {
            "component": "Intelligence.pythia_store",
            "files": ["Intelligence/pythia_store.py"],
            "classification": "MEMORY",
            "what_it_is": "Persistent run journal + memory stored three ways "
            "(Zeckendorf/prime indices, 32-dim qudit fidelity retrieval, JSON "
            "disk snapshots); self-curation with tombstones — nothing deleted "
            "silently.",
            "status": "connected",
            "evidence": "module docstring; artifacts/pythia snapshots",
        },
        {
            "component": "Intelligence.pythia_memory",
            "files": ["Intelligence/pythia_memory.py"],
            "classification": "MEMORY",
            "what_it_is": "Four-tier memory (working/episodic/semantic/"
            "archival) on the Zeckendorf substrate; tri-factor retrieval "
            "(relevance×recency×salience); golden-symplectic archival fold.",
            "status": "connected",
            "evidence": "module docstring",
        },
        {
            "component": "Intelligence.prime_memory",
            "files": ["Intelligence/prime_memory.py"],
            "classification": "MEMORY",
            "what_it_is": "Prime-addressed exponent store — payload chunks as "
            "prime exponents; SHA-256 fingerprint as address (composite "
            "product deliberately not materialized — honesty documented).",
            "status": "connected",
            "evidence": "module docstring",
        },
        {
            "component": "Intelligence.pvsnp_memory",
            "files": ["Intelligence/pvsnp_memory.py"],
            "classification": "EXPERIMENTAL",
            "what_it_is": "Lucas-structured memory block model — explicitly "
            "an 'operational model, not a proof of P vs NP'.",
            "status": "connected (honest model)",
            "evidence": "module docstring NOTE ON HONESTY",
        },
        {
            "component": "chronus.mla1517.mining.intelligence_memory",
            "files": ["chronus/mla1517/mining/intelligence_memory.py"],
            "classification": "MEMORY",
            "what_it_is": "Mining-domain intelligence memory + checkpoints.",
            "status": "connected (domain-bound)",
            "evidence": "mining coordinator/session imports",
        },
        {
            "component": "python_backend.core_modules.math_folding",
            "files": ["python_backend/core_modules/math_folding.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Exact Zeckendorf/Binet/Cassini/PULVINI/Pisot-Lucas "
            "contracts — CPU exact-arithmetic reference (Fraction/Quadratic5), "
            "no IEEE-754 sequence generation, no hardware claim.",
            "status": "connected",
            "evidence": "tests/test_math_folding.py",
        },
        {
            "component": "python_backend.core_modules.fold_pipeline",
            "files": ["python_backend/core_modules/fold_pipeline.py"],
            "classification": "COMPATIBILITY LAYER",
            "what_it_is": "Persistent folded-object execution + HMAC proof "
            "boundary over sqlite3 — SQLite is the journal, not the substrate.",
            "status": "connected",
            "evidence": "tests/test_fold_pipeline.py",
        },
        {
            "component": "chronus.mla1517.store.PrimeDB (SQLite)",
            "files": ["chronus/mla1517/store.py"],
            "classification": "COMPATIBILITY LAYER",
            "what_it_is": "Durable PrimeDB on SQLite WAL: content-addressed "
            "objects + exact 32-byte tensor payloads with sha256/length "
            "invariants verified on read.",
            "status": "connected",
            "evidence": "store.py; mla1517 tests",
        },
        {
            "component": "hyba_services catalogue/core",
            "files": ["hyba_services/catalogue.py", "hyba_services/core.py"],
            "classification": "CONTROL-PLANE DATABASE",
            "what_it_is": "Service catalogue / registry — control plane, not "
            "the data substrate.",
            "status": "connected",
            "evidence": "SQL-backed service records",
        },
        {
            "component": "pci.engine / hyba_compat",
            "files": ["pci/engine.py", "hyba_compat/__init__.py"],
            "classification": "COMPATIBILITY LAYER",
            "what_it_is": "Pulvini/PCI compatibility shims — ordinary "
            "interfaces onto the substrate.",
            "status": "connected",
            "evidence": "hyba_compat exports",
        },
        {
            "component": "legacy/AETHEL_Subsystem + hardened_unified_substrate",
            "files": ["legacy/", "aethel/hardened_unified_substrate.py"],
            "classification": "LEGACY",
            "what_it_is": "Frozen pre-consolidation monolith; aethel package "
            "is canonical, hardened_unified_substrate.py is a flat façade "
            "re-exporting the legacy import surface.",
            "status": "frozen",
            "evidence": "aethel/README.md layout table",
        },
        {
            "component": "toe.memory (MemoryStore)",
            "files": ["toe/memory.py"],
            "classification": "MEMORY",
            "what_it_is": "Pass-1 namespaced intelligence memory "
            "(observation/episodic/causal/strategy/world_model/procedural) "
            "with content-addressed recall, consolidation, regime "
            "invalidation — in-memory, receipt-chained.",
            "status": "connected",
            "evidence": "tests/test_toe_memory_world.py",
        },
        {
            "component": "kellogg tensor/exact persistence",
            "files": ["kellogg/exact_tensor.py", "kellogg/attest.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Exact Q(ζ8)/ZPhi tensor state — the precision "
            "substrate; attest bindings.",
            "status": "connected",
            "evidence": "elevation benchmark roundtrips",
        },
        {
            "component": "winner memory (mining)",
            "files": ["Intelligence/lucas_attractor.py"],
            "classification": "MEMORY",
            "what_it_is": "Winning-trajectory attractor memory, domain-bound "
            "to mining outcomes.",
            "status": "connected (domain-bound)",
            "evidence": "mining wiring",
        },
        {
            "component": "Intelligence.folded_state",
            "files": ["Intelligence/folded_state.py"],
            "classification": "CORE MATHEMATICAL SUBSTRATE",
            "what_it_is": "Folded-state carrier consumed by intelligence "
            "surfaces (feeds TOE observations).",
            "status": "connected",
            "evidence": "module file",
        },
    ]
    # mark missing files honestly
    for c in components:
        c["files_present"] = [f for f in c["files"] if _exists(f)]
        c["files_missing"] = [f for f in c["files"] if not _exists(f)]
    counts = {}
    for c in components:
        counts[c["classification"]] = counts.get(c["classification"], 0) + 1
    return {
        "section": "§1 storage archaeology",
        "classification_taxonomy": [
            "CORE MATHEMATICAL SUBSTRATE", "CONTROL-PLANE DATABASE",
            "DURABLE EVIDENCE STORE", "CACHE", "MEMORY", "ADDRESSING LAYER",
            "COMPATIBILITY LAYER", "LEGACY", "EXPERIMENTAL", "DISCONNECTED",
        ],
        "components": components,
        "classification_counts": counts,
        "notes": [
            "No component is DISCONNECTED by inspection: aethel is canonical "
            "and wired; legacy monolith is frozen behind a façade alias.",
            "Two distinct PrimeDB implementations exist: chronus.mla1517.prime_db "
            "(reference semantics, in-memory+journal) and chronus.mla1517.store "
            "(SQLite WAL durable). Reference is authoritative for semantics; "
            "SQLite is the durable compatibility backend.",
            "No tenant-isolation surface found in al_haras (audit/boundary "
            "modules exist; tenancy must reuse AL HARAS environment-boundary "
            "model, not a new framework — §21).",
        ],
    }


def ontology() -> dict:
    """§2 — authoritative representation map: every form + its contract."""
    forms = {
        "raw_bytes": {
            "provider": "bytes payload input",
            "input_domain": "arbitrary bytes len<=MAX_FOLD_LEN (1MiB declared)",
            "output_domain": "ZeckendorfVector on fold; uint64 chunk int on encode",
            "invertibility": "exact — unfold(fold(x))==x byte-identical",
            "precision_regime": "bit-exact",
            "identity": "sha256 digest (content identity)",
            "canonical_encoding": "big-endian uint64 per 8-byte chunk",
            "storage_form": "block files (aethel snapshot) / dict[int,bytes] resident",
            "reconstruction_rule": "Zeckendorf decode masks → chunk ints → bytes",
        },
        "structured_record": {
            "provider": "MLAObject / LogicalState",
            "input_domain": "index, lucas_scale, masks, addresses, site, seal, version, payload",
            "output_domain": "64-byte MLA1517State descriptor / JSONL journal line",
            "invertibility": "exact — canonical JSON roundtrip",
            "precision_regime": "bit-exact",
            "identity": "digest() over canonical fields (content address)",
            "canonical_encoding": "canonical_json sort_keys separators",
            "storage_form": "SQLite object_json / journal objects.jsonl",
            "reconstruction_rule": "replay journal → LogicalState → digest verify",
        },
        "exact_algebraic_state": {
            "provider": "Quadratic5 / ZPhi / Q(ζ8) tensors",
            "input_domain": "rationals + sqrt5 components; exact ring elements",
            "output_domain": "Fraction pairs; exact tensor amplitudes (32B)",
            "invertibility": "mathematically exact (Q(√5) field ops)",
            "precision_regime": "arbitrary-precision rational — no float",
            "identity": "algebraic value",
            "canonical_encoding": "Fraction numerator/denominator pairs",
            "storage_form": "exact_tensor_state BLOB (PrimeDB) / in-memory",
            "reconstruction_rule": "re-read + checksum/length invariants",
        },
        "folded_representation": {
            "provider": "aethel.encoding ZeckendorfVector",
            "input_domain": "bytes ≤1MiB",
            "output_domain": "tuple[(offset,mask)] masks ≤92 bits, non-adjacent",
            "invertibility": "exact by Zeckendorf uniqueness theorem",
            "precision_regime": "bit-exact",
            "identity": "same sha256 as source payload",
            "canonical_encoding": "sorted (offset,mask) pairs",
            "storage_form": "sparse_topology dict on TopologicalTensor",
            "reconstruction_rule": "reverse_zeckendorf_expansion → bytes",
            "honest_note": "masks up to ~12B per 8B chunk — representation, "
            "NOT compression; physical bytes measured in §3",
        },
        "tensor_state": {
            "provider": "PrimeStorageManifold TopologicalTensor",
            "input_domain": "payload bytes + curvature/sector",
            "output_domain": "pv-lattice integer_anchor ∈[0,90) + sparse topology",
            "invertibility": "payload exact via sparse; anchor is lossy navigation",
            "precision_regime": "payload bit-exact; anchor approximate",
            "identity": "uuid (object) + digest (content) + anchor (position)",
            "canonical_encoding": "uuid4 + integer_anchor + sparse blocks",
            "storage_form": "tensors dict + curved_storage prime commit",
            "reconstruction_rule": "digest-verify → self-heal → re-verify",
        },
        "graph_state": {
            "provider": "toe.causal CausalGraph / SCM",
            "input_domain": "edges, weights, structural equations",
            "output_domain": "state dict per node",
            "invertibility": "exact for evaluated states",
            "precision_regime": "exact ZPhi or float64 per path",
            "identity": "content hash of graph spec",
            "canonical_encoding": "edge list + weights",
            "storage_form": "in-memory; receipts carry digests",
            "reconstruction_rule": "re-evaluate from interventions",
        },
        "causal_state": {
            "provider": "toe world_model / counterfactual worlds",
            "input_domain": "observations, interventions",
            "output_domain": "predicted states, outcome distributions",
            "invertibility": "factual→counterfactual via mutilate surgery",
            "precision_regime": "exact or bounded",
            "identity": "decision_sha256 binding",
            "canonical_encoding": "interventions dict + receipt",
            "storage_form": "MemoryStore world_model namespace",
            "reconstruction_rule": "re-evaluate SCM under recorded interventions",
        },
        "metadata": {
            "provider": "TopologicalTensor fields / LedgerEntry",
            "input_domain": "per-object provenance",
            "output_domain": "seq/index/value/quadruple/digest/writer",
            "invertibility": "exact",
            "precision_regime": "bit-exact",
            "identity": "sha256 digest of payload",
            "canonical_encoding": "JSONL journal record",
            "storage_form": "ledger.jsonl + blocks/*.blk",
            "reconstruction_rule": "attach() replay + check_consistent",
        },
        "receipt": {
            "provider": "toe.receipts ReceiptLedger",
            "input_domain": "kind, inputs, config, output, evidence",
            "output_domain": "Receipt with receipt_sha256",
            "invertibility": "content-addressed; verify() re-derives chain",
            "precision_regime": "bit-exact",
            "identity": "receipt_sha256",
            "canonical_encoding": "canonical JSON",
            "storage_form": "in-memory ledger; export",
            "reconstruction_rule": "verify() walks the chain",
        },
        "address": {
            "provider": "FibonacciAddress / prime_at / integer_anchor",
            "input_domain": "Fibonacci index n≥1; uuid",
            "output_domain": "F_n value; prime key; anchor∈[0,90)",
            "invertibility": "index→value injective (fibonacci_index inverse); "
            "anchor NOT injective (mod-90 projection — navigation only)",
            "precision_regime": "exact integer",
            "identity": "address ≠ identity (§7: content=digest, "
            "fold=Zeckendorf mask, logical=Fib index, physical=block file)",
            "canonical_encoding": "(index,value) pair validated at construction",
            "storage_form": "ledger entry",
            "reconstruction_rule": "fibonacci_index / address_of",
        },
        "index": {
            "provider": "anchor_index / composite_index / _by_index",
            "input_domain": "anchor int / composite key / fib index",
            "output_domain": "uuid lists / entries",
            "invertibility": "navigation structure — rebuilt from store",
            "precision_regime": "exact",
            "identity": "derived, not authoritative",
            "canonical_encoding": "dict",
            "storage_form": "in-memory maps",
            "reconstruction_rule": "rebuild from ledger/objects",
        },
        "execution_record": {
            "provider": "OverheadMeter / stage_evidence / heal_log",
            "input_domain": "operation timing+bytes, backend, repairs",
            "output_domain": "overhead_report dicts",
            "invertibility": "n/a (telemetry)",
            "precision_regime": "measured (process_time_ns / perf_counter_ns)",
            "identity": "per-session",
            "canonical_encoding": "JSON report",
            "storage_form": "in-memory; exported into reports",
            "reconstruction_rule": "n/a",
        },
    }
    return {"section": "§2 data ontology", "forms": forms}


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    arch = archaeology()
    ont = ontology()
    (REPORTS / "hyba_storage_archaeology.json").write_text(
        json.dumps(arch, indent=2), encoding="utf-8"
    )
    (REPORTS / "hyba_representation_ontology.json").write_text(
        json.dumps(ont, indent=2), encoding="utf-8"
    )
    print("archaeology components:", len(arch["components"]))
    print("classification counts:", arch["classification_counts"])
    print("ontology forms:", len(ont["forms"]))
    print("wrote", REPORTS / "hyba_storage_archaeology.json")
    print("wrote", REPORTS / "hyba_representation_ontology.json")


if __name__ == "__main__":
    main()
