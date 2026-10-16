"""Guard the Agent 4 final acceptance matrix against unqualified overclaims."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX = REPO_ROOT / "docs" / "FINAL_ACCEPTANCE_MATRIX.md"

REQUIRED_AREAS = [
    "Architecture",
    "Backend",
    "Frontend",
    "Mining",
    "Quantum",
    "Salamander",
    "Agentic workflow",
    "Parallel execution",
    "Data provenance",
    "Mining dashboard",
    "CEO authorization",
    "Tests",
    "Documentation",
]

VALID_STATUSES = {
    "FULLY WIRED",
    "PARTIALLY WIRED",
    "SIMULATED",
    "DISCONNECTED",
    "UNIMPLEMENTED",
    "UNVERIFIABLE",
}


def test_final_acceptance_matrix_exists_and_uses_required_statuses():
    text = MATRIX.read_text(encoding="utf-8")
    assert "Overall:** `PARTIALLY WIRED`" in text
    for area in REQUIRED_AREAS:
        matching_rows = [line for line in text.splitlines() if line.startswith(f"| {area} |")]
        assert matching_rows, f"missing matrix row for {area}"
        status = matching_rows[0].split("|")[2].strip()
        assert status in VALID_STATUSES, f"invalid status for {area}: {status}"


def test_final_acceptance_matrix_does_not_claim_unverified_full_wiring():
    text = MATRIX.read_text(encoding="utf-8")
    forbidden_rows = [
        "| Mining | FULLY WIRED |",
        "| Quantum | FULLY WIRED |",
        "| Salamander | FULLY WIRED |",
        "| Parallel execution | FULLY WIRED |",
        "| CEO authorization | FULLY WIRED |",
    ]
    for row in forbidden_rows:
        assert row not in text
