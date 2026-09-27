"""
tests/test_drift_sentry.py — Rigorous validation of Anti-Drift Sentry and Substrate Agnosticism
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.drift_sentry import DriftSentry


def test_drift_sentry_reminder_content():
    """Verify that the reminder message contains the foundational axioms."""
    payload = DriftSentry.format_pre_invocation_hook()
    assert "injectSteps" in payload
    assert len(payload["injectSteps"]) == 1
    msg = payload["injectSteps"][0]["ephemeralMessage"]
    assert "Foundational Thesis" in msg
    assert "linear algebra over C" in msg
    assert "pocket calculator" in msg
    assert "double-SHA256" in msg


def test_drift_sentry_detects_substrate_fetishism():
    """Verify detection of statements claiming quantum cannot run on classical hardware."""
    text = "We cannot run quantum on classical silicon because of coherence limits."
    violations = DriftSentry.inspect_text(text)
    assert len(violations) >= 1
    assert any("DRIFT-01" in v["drift_id"] for v in violations)


def test_drift_sentry_detects_algorithmic_defeatism():
    """Verify detection of defeatist claims about classical computation."""
    text = "Classical computers can only do brute force search without physical lasers."
    violations = DriftSentry.inspect_text(text)
    assert len(violations) >= 1
    assert any("DRIFT-02" in v["drift_id"] for v in violations)


def test_drift_sentry_detects_consensus_bypass():
    """Verify detection of attempts to bypass double-SHA256 consensus."""
    text = "Let's speed up mining by bypassing double_sha256 target checks."
    violations = DriftSentry.inspect_text(text)
    assert len(violations) >= 1
    assert any("DRIFT-03" in v["drift_id"] for v in violations)


def test_drift_sentry_clean_text_passes():
    """Verify that mathematically sound substrate-agnostic code passes clean."""
    clean_text = (
        "def grover_step(amplitudes):\n"
        "    # Unitary rotation in C^4 via fixed-point matrix multiplication\n"
        "    return diffusion_matrix @ (oracle_matrix @ amplitudes)\n"
    )
    violations = DriftSentry.inspect_text(clean_text)
    assert len(violations) == 0


def test_drift_sentry_scans_clean_repository(tmp_path):
    """Verify scan_path correctly skips clean files and alerts on violations."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("x = 42\n# Pure algebraic mapping\n", encoding="utf-8")

    violating_file = tmp_path / "bad.py"
    violating_file.write_text("# This requires physical qubits to work\n", encoding="utf-8")

    results = DriftSentry.scan_path(tmp_path)
    assert len(results) == 1
    assert results[0]["file"] == str(violating_file)
