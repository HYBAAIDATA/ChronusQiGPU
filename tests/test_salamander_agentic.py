"""
tests/test_salamander_agentic.py — Rigorous verification of Salamander's Agentic Capabilities
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Intelligence.salamander import (
    SalamanderEngine,
    SalamanderCodebaseScanner,
    SalamanderAgenticOptimizer,
    SalamanderAgenticController,
    CodebaseDiagnostic,
    CodebaseIssueType,
)


def test_salamander_engine_has_agentic_capabilities():
    """Verify SalamanderEngine instantiates agentic scanner, optimizer, and SHI."""
    engine = SalamanderEngine()
    assert hasattr(engine, "codebase_scanner")
    assert hasattr(engine, "codebase_optimizer")
    assert hasattr(engine, "scan_codebase")
    assert hasattr(engine, "agentic_heal")
    assert hasattr(engine, "substrate_health_index")


def test_salamander_scanner_detects_discarded_operators(tmp_path):
    """Verify scanner flags standalone discarded operator expressions."""
    flawed_code = (
        "import numpy as np\n"
        "def fake_walk(steps):\n"
        "    for _ in range(steps):\n"
        "        np.array([[1, 1], [1, -1]]) / np.sqrt(2)\n"
        "        x = 1\n"
    )
    flawed_file = tmp_path / "flawed_walk.py"
    flawed_file.write_text(flawed_code, encoding="utf-8")

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    diags, res = scanner.scan_file(flawed_file)

    assert any(d.pattern == "discarded_operator" for d in diags)
    assert any(d.severity == "CRITICAL" for d in diags)


def test_salamander_scanner_detects_fake_quantum_comments(tmp_path):
    """Verify scanner flags comments claiming QFT is simulation requiring physical hardware."""
    code = "# Classical FFT as simulation (in production, would use actual quantum QFT)\n" "x = 1\n"
    test_file = tmp_path / "fake_qft.py"
    test_file.write_text(code, encoding="utf-8")

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    diags, _ = scanner.scan_file(test_file)

    assert any(d.pattern in ("fake_quantum", "cognitive_drift_fake_quantum") for d in diags)
    assert any("AGENTS.md" in d.proposed_repair for d in diags)


def test_salamander_scanner_detects_cosmetic_coherence(tmp_path):
    """Verify scanner flags pairwise difference scaled by PHI labeled as coherence."""
    code = "corr = abs(amplitude[i] - amplitude[i + 1] * PHI)\n"
    test_file = tmp_path / "cosmetic.py"
    test_file.write_text(code, encoding="utf-8")

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    diags, _ = scanner.scan_file(test_file)

    assert any(d.pattern == "cosmetic_coherence" for d in diags)
    assert any("density matrix" in d.proposed_repair for d in diags)


def test_salamander_scanner_detects_hardcoded_collapse(tmp_path):
    """Verify scanner flags static 1 - 1/e Orch-OR probability calculations."""
    code = "reduction_prob = 1.0 - math.exp(-state.coherence_time / self.coherence_time)\n"
    test_file = tmp_path / "collapse.py"
    test_file.write_text(code, encoding="utf-8")

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    diags, _ = scanner.scan_file(test_file)

    assert any(d.pattern == "hardcoded_collapse" for d in diags)
    assert any("spectral projection" in d.proposed_repair for d in diags)


def test_salamander_scanner_detects_magic_constants(tmp_path):
    """Verify scanner flags arbitrary physical magic constants."""
    code = "quantum_channel_capacity: float = 1e12  # bits per Planck time\n"
    test_file = tmp_path / "magic.py"
    test_file.write_text(code, encoding="utf-8")

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    diags, _ = scanner.scan_file(test_file)

    assert any(d.pattern == "magic_constant" for d in diags)
    assert any("Holevo" in d.proposed_repair or "entropy" in d.proposed_repair for d in diags)


def test_salamander_scanner_reports_shi_bounded(tmp_path):
    """Verify Substrate Health Index (SHI) is bounded in [0, 1] and reflects health."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("x = 1\n", encoding="utf-8")

    bad_file = tmp_path / "bad.py"
    bad_file.write_text(
        "quantum_channel_capacity: float = 1e12\n"
        "# Classical FFT as simulation (in production, would use actual quantum QFT)\n"
        "corr = abs(amplitude[i] - amplitude[i + 1] * PHI)\n",
        encoding="utf-8",
    )

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    report_clean = scanner.scan_directory(subdirs=None)
    assert 0.0 <= report_clean.substrate_health_index <= 1.0

    # With bad file included, SHI should degrade
    assert report_clean.drift_violations > 0
    assert report_clean.summary()["healthy"] is False


def test_salamander_optimizer_proposes_exact_repairs():
    """Verify optimizer provides first-principles repairs for each diagnostic category."""
    optimizer = SalamanderAgenticOptimizer()

    categories = [
        ("discarded_operator", "AGENTS.md §2.1"),
        ("fake_quantum", "AGENTS.md §2.2"),
        ("cosmetic_coherence", "AGENTS.md §1.2.1"),
        ("hardcoded_collapse", "AGENTS.md §1.2.2"),
        ("magic_constant", "Holevo bound"),
    ]

    for pat, expected_basis in categories:
        diag = CodebaseDiagnostic(
            file_path="mock.py",
            line_number=10,
            issue_type=CodebaseIssueType.DISCARDED_OPERATOR,
            snippet="dummy code",
            description="desc",
            remedy="remedy",
            pattern_name=pat,
        )
        proposal = optimizer.propose_repair(diag)
        assert proposal["pattern"] == pat
        assert expected_basis in proposal["mathematical_basis"]
        assert "exact_replacement" in proposal
        assert "verification_test" in proposal


def test_salamander_optimizer_rejects_callback_before_writing(tmp_path):
    """An in-process callback cannot authorize a live source write."""
    target_file = tmp_path / "module.py"
    original_text = "def compute():\n    return 42\n"
    target_file.write_text(original_text, encoding="utf-8")

    optimizer = SalamanderAgenticOptimizer(repo_root=tmp_path)

    # Broken replacement that causes test failure
    broken_replacement = "def compute():\n    return 0\n"

    def failing_test():
        return False

    success, msg = optimizer.apply_repair_sandboxed(
        target_file=target_file,
        replacement=broken_replacement,
        test_callable=failing_test,
    )

    assert success is False
    assert "cannot authorize" in msg
    # Production file must remain completely uncorrupted
    assert target_file.read_text(encoding="utf-8") == original_text
    # Backup file must be cleaned up
    assert not target_file.with_suffix(".py.bak").exists()


def test_salamander_optimizer_rejects_passing_callback(tmp_path):
    """A True callback is not independently isolated regression evidence."""
    target_file = tmp_path / "module.py"
    original_text = "def compute():\n    return 42\n"
    target_file.write_text(original_text, encoding="utf-8")

    optimizer = SalamanderAgenticOptimizer(repo_root=tmp_path)

    good_replacement = "def compute():\n    return 84\n"

    def passing_test():
        return True

    success, msg = optimizer.apply_repair_sandboxed(
        target_file=target_file,
        replacement=good_replacement,
        test_callable=passing_test,
    )

    assert success is False
    assert "cannot authorize" in msg
    assert target_file.read_text(encoding="utf-8") == original_text
    assert not target_file.with_suffix(".py.bak").exists()


def test_salamander_scanner_clean_file_passes(tmp_path):
    """Verify scanner passes cleanly on pure algebraic code."""
    clean_code = (
        "import cmath\n"
        "def exact_evolution(psi, U):\n"
        "    return [sum(u * p for u, p in zip(row, psi)) for row in U]\n"
    )
    clean_file = tmp_path / "clean_math.py"
    clean_file.write_text(clean_code, encoding="utf-8")

    scanner = SalamanderCodebaseScanner(repo_root=tmp_path)
    diags, res = scanner.scan_file(clean_file)

    assert len(diags) == 0
    assert res > 0.0


def test_salamander_agentic_controller_runs(tmp_path):
    """Verify SalamanderAgenticController executes an autonomic cycle."""
    dummy_file = tmp_path / "test_module.py"
    dummy_file.write_text("x = 42\n", encoding="utf-8")

    controller = SalamanderAgenticController(repo_root=tmp_path)
    result = controller.run_autonomic_cycle(auto_heal=False, subdirs=None)

    assert "audit_summary" in result
    assert "diagnostics" in result
    assert "substrate_health_index" in result["audit_summary"]


def test_salamander_engine_substrate_health_index():
    """Verify SalamanderEngine.substrate_health_index() computes SHI in [0, 1]."""
    engine = SalamanderEngine()
    shi = engine.substrate_health_index()
    assert isinstance(shi, float)
    assert 0.0 <= shi <= 1.0
    assert shi > 0.5


def test_salamander_scans_production_directories_clean():
    """Production-matrix row: the AST sentry runs over the real tree —
    Intelligence, mining, pythagoras, core_engine — and reports zero
    drift violations. A regression that reintroduces a discarded
    operator, a fake-quantum claim, or a magic constant fails here."""
    scanner = SalamanderCodebaseScanner()
    report = scanner.scan_directory(("Intelligence", "mining", "pythagoras", "core_engine"))
    assert report.scanned_files > 50
    assert report.drift_violations == 0, (
        f"drift violations: "
        f"{[(str(d.file_path), d.line_number, d.issue_type.value) for d in report.diagnostics]}"
    )
    assert report.substrate_health_index > 0.5


# ── healing never outruns its evidence ───────────────────────────────── #


def test_a_repair_without_verification_is_never_applied(tmp_path):
    target_file = tmp_path / "module.py"
    original_text = "def compute():\n    return 42\n"
    target_file.write_text(original_text, encoding="utf-8")
    optimizer = SalamanderAgenticOptimizer(repo_root=tmp_path)

    success, msg = optimizer.apply_repair_sandboxed(
        target_file=target_file, replacement="def compute():\n    return 0\n"
    )

    assert success is False
    assert "never applied unverified" in msg
    assert target_file.read_text(encoding="utf-8") == original_text
    assert not target_file.with_suffix(".py.bak").exists()


def test_legacy_verification_commands_cannot_authorize_repairs(tmp_path):
    target_file = tmp_path / "module.py"
    original_text = "def compute():\n    return 42\n"
    target_file.write_text(original_text, encoding="utf-8")
    failing = SalamanderAgenticOptimizer(
        repo_root=tmp_path, verify_cmd=f'"{sys.executable}" -c "raise SystemExit(1)"'
    )
    replacement = "def compute():\n    return 84\n"

    success, _ = failing.apply_repair_sandboxed(
        target_file=target_file, replacement=replacement, test_cmd=failing.verify_cmd
    )
    assert success is False
    assert target_file.read_text(encoding="utf-8") == original_text

    passing = SalamanderAgenticOptimizer(
        repo_root=tmp_path, verify_cmd=f'"{sys.executable}" -c "import module"'
    )
    success, _ = passing.apply_repair_sandboxed(
        target_file=target_file, replacement=replacement, test_cmd=passing.verify_cmd
    )
    assert success is False
    assert target_file.read_text(encoding="utf-8") == original_text


def test_the_codebase_healing_skill_is_opt_in(monkeypatch):
    seen = {}

    def record(self, auto_heal=False, subdirs=None):
        seen["auto_heal"] = auto_heal
        return {}

    monkeypatch.setattr(SalamanderAgenticController, "run_autonomic_cycle", record)
    SalamanderEngine().execute_skill("codebase-healing")
    assert seen == {"auto_heal": False}


def test_self_repair_never_auto_applies_a_change_to_a_test(tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import RepairProposal, apply_and_verify

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")
    test_file = tmp_path / "tests" / "test_physics.py"
    test_file.parent.mkdir()
    original = "def test_energy():\n    assert abs(1.0 - 1.001) < 1e-6\n"
    test_file.write_text(original, encoding="utf-8")
    widened = original.replace("1e-6", "0.01")  # what tolerance "repair" proposes
    proposal = RepairProposal(
        id="repair_test",
        session_id="s",
        suite_label="tests",
        test_node_id="tests/test_physics.py::test_energy",
        category="numeric_tolerance_drift",
        confidence="high",
        diagnosis="numeric drift",
        evidence={"abs_delta": 0.001},
        source="llm",
        target_file="tests/test_physics.py",
        proposed_content=widened,
    )

    result = apply_and_verify(proposal, tmp_path, tmp_path)

    assert result.applied is False
    assert "a test" in result.message
    assert test_file.read_text(encoding="utf-8") == original
