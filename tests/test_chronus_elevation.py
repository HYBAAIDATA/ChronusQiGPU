"""Regression tests for execution-route and evidence honesty.

The legacy Mode B path has no kernel for its deterministic workload. Tests
therefore require CPU-reference execution and NOT_RUN device evidence whether
or not an OpenCL probe finds hardware. The similarly legacy quantum-walk API is
a classical deterministic walk, not a TURING quantum-semantics test.

These tests never write into the repository. The evidence writers are
redirected to a temporary directory, and the committed artefacts are read for
comparison only. A test that overwrote the tracked evidence would make the
release artefacts change whenever anyone ran the suite, and nobody could
tell a regeneration from a regression.
"""

import csv
import json
from unittest.mock import patch

import pytest

from chronus.execution import elevation
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


@pytest.fixture()
def evidence_dir(tmp_path, monkeypatch):
    """Redirect the evidence writers to a temporary directory.

    The writers read EVIDENCE_DIR at call time, so patching the module
    attribute is enough to keep the repository untouched.
    """
    target = tmp_path / "evidence" / "chronus"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(elevation, "EVIDENCE_DIR", target)
    return target


# Measured wall-clock fields. Their values differ on every run, so a golden
# comparison excludes them. The artefacts name them in their own
# timing_basis field.
TIMING_FIELDS = frozenset({"elapsed_ms", "t_ms"})


class TestChronusExecutionModes:
    def test_mode_a_native_execution_and_evidence(self, evidence_dir):
        """Mode A runs standalone on CPU reference, produces valid evidence, and never labels CPU as device."""
        results = run_mode_a(SEEDS)
        assert len(results) == len(SEEDS)
        for s in SEEDS:
            rec = results[s]
            assert rec["route"]["executed"] == "cpu_reference"
            assert rec["device_run"] == "NOT_RUN"
            assert rec["hashrate"] == "NOT_RUN"
            assert len(rec["hash"]) == 64
            # Verify file exists in the redirected directory
            f = evidence_dir / f"modeA_{s}.json"
            assert f.exists()
            loaded = json.loads(f.read_text(encoding="utf-8"))
            assert loaded["hash"] == rec["hash"]
            assert loaded["route"]["executed"] == "cpu_reference"

    def test_mode_b_never_promotes_a_probe_to_device_execution(self, evidence_dir):
        mode_a_res = run_mode_a(SEEDS)
        for present, reason in (
            (False, "OPENCL_UNAVAILABLE"),
            (True, "OPENCL_EXECUTION_NOT_IMPLEMENTED"),
        ):
            with patch("chronus.execution.elevation.is_opencl_hardware_present", return_value=present):
                results = run_mode_b(SEEDS, mode_a_res)
            assert len(results) == len(SEEDS)
            for seed in SEEDS:
                rec = results[seed]
                assert rec["device_found"] is present
                assert rec["route"]["executed"] == "cpu_reference"
                assert rec["route"]["fallback_reason"] == reason
                assert rec["device_run"] == "NOT_RUN"
                assert rec["hashrate"] == "NOT_RUN"
                assert rec["reference_match"] is True
                assert rec["hash"] == mode_a_res[seed]["hash"]
                assert rec["t_ms"] >= 0

    def test_classical_walk_cannot_claim_quantum_semantics_or_speedup(self):
        with patch("chronus.execution.elevation.is_opencl_hardware_present", return_value=True):
            walk = run_quantum_walk_same_hash(1337, steps=8)
        assert walk["cpu_emu_match"] is True
        assert walk["cpu_hash"] == walk["emu_hash"]
        assert walk["model"] == "classical_deterministic_walk"
        assert walk["quantum_semantics"] is False
        assert walk["igpu_available"] is True
        assert walk["accelerator_executed"] is False
        assert "UNPROVEN" in walk["speedup_claim"]

    def test_backend_matrix_contains_only_local_single_run_evidence(self, evidence_dir):
        generate_backend_matrix()
        matrix_path = evidence_dir / "backend_matrix.csv"
        assert matrix_path.exists()
        with open(matrix_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == [
                "env", "requested", "executed", "fallback", "hash", "t_p50/p95", "device_run",
                "elapsed_ms", "timing_basis", "device_found",
            ]
            rows = list(reader)
        assert len(rows) == 2 * len(SEEDS) + 2
        local = [row for row in rows if row["env"].startswith("local-")]
        assert {row["timing_basis"] for row in local} == {
            "single_run_perf_counter_wall_time_not_a_percentile"
        }
        assert all(float(row["elapsed_ms"]) >= 0 for row in local)
        assert all(row["t_p50/p95"] == "NOT_MEASURED" for row in rows)
        assert all(row["device_run"] == "NOT_RUN" for row in local)
        assert all(row["executed"] == "cpu_reference" for row in local)
        controls = {row["env"]: row for row in rows if "control" in row["env"]}
        assert set(controls) == {"docker-local-control", "azure-container-control"}
        for row in controls.values():
            assert row["executed"] == "NOT_RUN"
            assert row["hash"] == "NOT_RUN"
            assert row["elapsed_ms"] == "NOT_RUN"
            assert row["timing_basis"] == "NOT_MEASURED"
            assert row["device_run"] == "NOT_RUN"

    def test_generated_evidence_matches_the_committed_artefacts(self, evidence_dir):
        """A regenerated artefact must match the committed one.

        The evidence writers are redirected to a temporary directory, so this
        compares what the code produces now against what is committed, without
        writing into the repository. A genuine change to the evidence becomes
        a deliberate diff instead of an invisible rewrite whenever the suite
        runs.

        The measured timings are excluded: t_ms and elapsed_ms are wall-clock
        readings that differ on every run, and the artefact says so in its
        own timing_basis field. Everything that carries a claim is compared
        byte for byte.
        """
        generate_backend_matrix()
        self._assert_same_except_timing(
            evidence_dir / "backend_matrix.csv",
            REPO_ROOT / "evidence" / "chronus" / "backend_matrix.csv",
        )
        for seed in SEEDS:
            self._assert_same_except_timing(
                evidence_dir / f"modeA_{seed}.json",
                REPO_ROOT / "evidence" / "chronus" / f"modeA_{seed}.json",
            )

    @staticmethod
    def _assert_same_except_timing(produced_path, committed_path):
        """Compare two artefacts, ignoring the measured timing fields."""
        assert committed_path.exists(), f"committed artefact missing: {committed_path}"
        produced = produced_path.read_text(encoding="utf-8")
        committed = committed_path.read_text(encoding="utf-8")
        if produced_path.suffix == ".json":
            produced_data = json.loads(produced)
            committed_data = json.loads(committed)
            for data in (produced_data, committed_data):
                for field in TIMING_FIELDS:
                    data.pop(field, None)
            assert produced_data == committed_data, (
                f"{produced_path.name} differs from the committed artefact; "
                "regenerate it deliberately and commit the change"
            )
            return
        # The CSV names its columns in the header row, so the measured timing
        # column is found by name rather than by position.
        produced_rows = list(csv.reader(produced.strip().splitlines()))
        committed_rows = list(csv.reader(committed.strip().splitlines()))
        assert len(produced_rows) == len(committed_rows), (
            f"{produced_path.name} has a different number of rows"
        )
        header = produced_rows[0]
        timing_columns = {
            index for index, name in enumerate(header) if name in TIMING_FIELDS
        }
        assert timing_columns, "the backend matrix must name its timing column"
        for produced_row, committed_row in zip(produced_rows, committed_rows):
            assert len(produced_row) == len(committed_row)
            for index, (produced_cell, committed_cell) in enumerate(
                zip(produced_row, committed_row)
            ):
                if index in timing_columns:
                    continue
                assert produced_cell == committed_cell, (
                    f"{produced_path.name} differs from the committed artefact "
                    f"in a non-timing field: {produced_cell!r} != {committed_cell!r}"
                )

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
