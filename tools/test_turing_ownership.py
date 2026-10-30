from pathlib import Path

from tools.audit_chronus_dependency import chronus_imports


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "turing_universal_quantum_computer"
    / "turing_universal_quantum_computer"
)


def test_turing_owns_its_quantum_mathematics():
    violations = []

    for path in sorted(PACKAGE.rglob("*.py")):
        for line, module in chronus_imports(path):
            violations.append(
                f"{path.relative_to(ROOT)}:{line}: {module}"
            )

    assert not violations, (
        "TURING must own its quantum mathematics; "
        "Chronus is substrate-only:\n"
        + "\n".join(violations)
    )