"""Test Suite for Chronus / iGPU Execution Modes & Elevation Substrate.

Verifies:
1. Mode A: native_chronus_gpu (standalone software on CPU reference, zero host GPU required,
   never labelled as device, emits evidence/chronus/modeA_{seed}.json).
2. Mode B: host_gpu_augmentation (preferred accelerator when present with same-hash guarantee;
   graceful gate to cpu_reference with OPENCL_UNAVAILABLE when missing).
3. Quantum walk same-hash verification between CPU reference and software emulator.
4. Backend matrix evidence artifact structure in evidence/chronus/backend_matrix.csv.
5. Golden stride permutation invariant (coprime to 2^32, FIFO depth == 8).
6. Non-conflation and boundary checks: core modules do not import backend-specific SDKs.
"""

import csv
import json


from chronus.execution.elevation import (
    GOLD_FIFO_DEPTH,
    GOLDEN_STRIDE,
    REPO_ROOT,
    SEEDS,
    generate_backend_matrix,
    run_mode_a,
    run_mode_b,
    run_quantum_walk_same_hash,
    verify_golden_stride,
)


class TestChronusExecutionModes:
    def test_mode_a_native_execution_and_evidence(self):
        """Mode A runs standalone on CPU reference, produces valid evidence, and never labels CPU as device."""
        results = run_mode_a(SEEDS)
        assert len(results) == len(SEEDS)
        for s in SEEDS:
            rec = results[s]
            assert rec["route"]["executed"] == "cpu_reference"
            assert rec["device_run"] == "NOT_RUN"
            assert rec["hashrate"] == "NOT_RUN"
            assert len(rec["hash"]) == 64
            # Verify file exists
            f = REPO_ROOT / "evidence" / "chronus" / f"modeA_{s}.json"
            assert f.exists()
            loaded = json.loads(f.read_text(encoding="utf-8"))
            assert loaded["hash"] == rec["hash"]
            assert loaded["route"]["executed"] == "cpu_reference"

    def test_mode_b_augmented_or_graceful_fallback(self):
        """Mode B executes on accelerator if present (with same hash) or falls back with OPENCL_UNAVAILABLE."""
        mode_a_res = run_mode_a(SEEDS)
        results = run_mode_b(SEEDS, mode_a_res)
        assert len(results) == len(SEEDS)
        for s in SEEDS:
            rec = results[s]
            if rec["device_found"]:
                assert rec["hash"] == mode_a_res[s]["hash"]
                assert rec["device_run"] == "PASS"
            else:
                assert rec["route"]["executed"] == "cpu_reference"
                assert "OPENCL_UNAVAILABLE" in rec["route"]["fallback_reason"]
                assert rec["device_run"] == "NOT_RUN"
                assert rec["hashrate"] == "NOT_RUN"

    def test_quantum_walk_same_hash_cpu_and_emulator(self):
        """Asserts bit-exact hash equivalence between CPU reference and emulator."""
        qw = run_quantum_walk_same_hash(1337, steps=8)
        assert qw["cpu_emu_match"] is True
        assert qw["cpu_hash"] == qw["emu_hash"]
        if not qw["igpu_available"]:
            assert "UNPROVEN" in qw["speedup_claim"]

    def test_backend_matrix_artifact_structure(self):
        """Verifies evidence/chronus/backend_matrix.csv structure, headers, and rows."""
        generate_backend_matrix()
        matrix_path = REPO_ROOT / "evidence" / "chronus" / "backend_matrix.csv"
        assert matrix_path.exists()
        with open(matrix_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["env", "requested", "executed", "fallback", "hash", "t_p50/p95", "device_run"]
            rows = list(reader)
            assert len(rows) >= 5
            for row in rows:
                assert len(row) == 7

    def test_golden_stride_permutation_invariant(self):
        """Verifies that GOLDEN_STRIDE is odd and coprime to 2^32, generating a complete permutation."""
        assert verify_golden_stride() is True
        assert GOLD_FIFO_DEPTH == 8
        assert (GOLDEN_STRIDE & 1) == 1

    def test_core_clean_boundary(self):
        """Core modules (such as core/ and math/) must not import physical backends or cloud SDKs."""
        core_dirs = [REPO_ROOT / "src" / "chronus" / "core"]
        for d in core_dirs:
            if d.exists():
                for f in d.rglob("*.py"):
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                    assert "import pyopencl" not in txt, f"Forbidden import pyopencl in {f}"
                    assert "import mla1517" not in txt, f"Forbidden import mla1517 in {f}"
                    assert "import azure" not in txt, f"Forbidden import azure in {f}"
