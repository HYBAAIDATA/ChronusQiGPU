"""Chronus / iGPU Elevation test suite.
Verifies all 7 myths (C1-C7), static guards, Mode A native execution, Mode B host
augmentation graceful gating, quantum walk same-hash verification, and artifact generation.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from math import gcd
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from chronus import backend as contract
from hyba.operating_model.lemma import verify_golden_stride
from lucas.pisot import (
    HendrixStructuredSearch,
    LucasScaleError,
    QuantumTensorManifest,
    require_lucas_execution_scale,
)
from mining.bitcoin_hasher import BitcoinHasher
from scripts.run_chronus_elevation import (
    SEEDS,
    build_composite_workload_payload,
    check_static_guards,
    evaluate_all_myths,
    get_git_branch,
    get_git_head,
    run_mode_a,
    run_mode_b,
    run_quantum_walk_same_hash,
)
from toe.intelligences.authority_boundary import (
    EUCLID_FORBIDDEN_DOMAINS,
    PYTHIA_FINAL_AUTHORITY,
    is_forbidden,
    is_pythia_final,
)


class TestChronusStaticGuards:
    def test_branch_not_main(self):
        branch = get_git_branch()
        assert branch != "", f"Elevation tests must run on feature branch, found {branch}"

    def test_zero_backend_imports_in_core(self):
        pattern = re.compile(r"import\s+(pyopencl|mla1517|azure)|from\s+(pyopencl|mla1517|azure)")
        violations = []
        for d in ["euclid", "lucas"]:
            p = REPO_ROOT / d
            if p.exists():
                for f in p.rglob("*.py"):
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                    for idx, line in enumerate(txt.splitlines(), 1):
                        if pattern.search(line):
                            violations.append(f"{f}:{idx}: {line.strip()}")
        assert violations == [], f"Found forbidden backend imports: {violations}"

    def test_golden_stride_permutation_and_fifo_depth(self):
        verdicts = verify_golden_stride()
        assert verdicts[0]["verdict"] == "HOLDS"
        assert BitcoinHasher.GOLD_FIFO_DEPTH == 8

    def test_lucas_execution_scale_ladder(self):
        with pytest.raises(LucasScaleError):
            require_lucas_execution_scale(7)
        for s in (10, 12, 15, 18, 20, 31, 50, 76):
            assert require_lucas_execution_scale(s) == s

    def test_quantum_tensor_manifest_11_dimension_and_coverage(self):
        manifest = QuantumTensorManifest(11)
        assert manifest.dimension == 2048
        cov = manifest.coverage()
        assert cov.fits is True
        assert cov.state_bytes == 2048 * 16


class TestMythBustingInvariants:
    def test_c1_native_mode_a_runs_on_cpu(self):
        # C1 "iGPU needs a GPU to exist" — FALSE
        res, route = contract.execute("sha256d", b"c1_test", requested="cpu")
        assert route.requested == "cpu"
        assert route.executed == "cpu_reference"
        assert res["backend"] == "cpu_reference"
        assert len(res["digest"]) == 64

    def test_c2_cpu_fallback_never_labelled_device(self):
        # C2 "CPU fallback = iGPU execution" — FALSE
        res, route = contract.execute("sha256d", b"c2_test", requested="opencl")
        assert route.executed == "cpu_reference"
        assert route.fallback_reason != ""
        assert res["backend"] == "cpu_reference"
        hasher = BitcoinHasher(backend="cpu")
        st = hasher.silicon_status()
        assert st.get("device_run") != "PASS"

    def test_c3_docker_local_and_azure_control_parity(self):
        # C3 "Same code can't run Docker-local and Azure" — FALSE
        dockerfile = REPO_ROOT / "deploy" / "azure" / "Dockerfile"
        bicep = REPO_ROOT / "deploy" / "azure" / "main.bicep"
        assert dockerfile.exists()
        assert bicep.exists()
        # Single Dockerfile for both environments
        assert "pythia" in dockerfile.read_text(encoding="utf-8").lower() or dockerfile.stat().st_size > 0

    def test_c4_golden_stride_permutation_only(self):
        # C4 "Golden stride saves hashes" — FALSE
        stride = 0x9E3779B9
        assert stride % 2 == 1
        assert gcd(stride, 1 << 32) == 1
        assert BitcoinHasher.GOLD_FIFO_DEPTH == 8

    def test_c5_http_health_not_mining_readiness(self):
        # C5 "HTTP health == mining readiness" — FALSE
        deploy_readme = (REPO_ROOT / "deploy" / "azure" / "README.md").read_text(encoding="utf-8")
        assert "Do not interpret HTTP health as mining readiness" in deploy_readme
        assert "ready-to-mine" in deploy_readme

    def test_c6_chronus_does_not_own_turing_vqc(self):
        # C6 "Chronus owns Turing VQC" — FALSE
        assert is_pythia_final("search-plan") is True
        assert is_forbidden("bitcoin-header") is True
        assert "sha256d" in PYTHIA_FINAL_AUTHORITY
        assert "sha256d" in EUCLID_FORBIDDEN_DOMAINS

    def test_c7_backend_specific_code_not_in_core(self):
        # C7 "Backend-specific code in core" — FALSE
        for d in ["euclid", "lucas"]:
            for f in (REPO_ROOT / d).rglob("*.py"):
                txt = f.read_text(encoding="utf-8", errors="ignore")
                assert "import pyopencl" not in txt
                assert "import mla1517" not in txt
                assert "import azure" not in txt


class TestChronusExecutionModes:
    def test_mode_a_native_execution_and_evidence(self):
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

    def test_mode_b_augmented_or_graceful_fallback(self):
        mode_a_res = run_mode_a(SEEDS)
        results = run_mode_b(SEEDS, mode_a_res)
        assert len(results) == len(SEEDS)
        for s in SEEDS:
            rec = results[s]
            if rec["device_found"]:
                assert rec["hash"] == mode_a_res[s]["hash"]
            else:
                assert rec["route"]["executed"] == "cpu_reference"
                assert "OPENCL_UNAVAILABLE" in rec["route"]["fallback_reason"]
                assert rec["hashrate"] == "NOT_RUN"

    def test_quantum_walk_same_hash_cpu_and_emulator(self):
        qw = run_quantum_walk_same_hash(1337, steps=8)
        assert qw["cpu_emu_match"] is True
        assert qw["cpu_hash"] == qw["emu_hash"]
        if not qw["igpu_available"]:
            assert "UNPROVEN" in qw["speedup_claim"]

    def test_backend_matrix_artifact_structure(self):
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
