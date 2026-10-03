"""The VQC's published capability matrix and its enforced claim boundary.

A virtual quantum computer has to be precise about one thing above all: the
difference between *how wide a register the algebra admits* and *what the
package can actually compute exactly at that width*.  Those are different
numbers, and conflating them is the single defect that turns an honest exact
substrate into "classical dressed as quantum".

This module states both, publishes the per-backend matrix, and — the part that
makes it a boundary rather than a slogan — **audits claim text** for
unqualified universality or hardware assertions.  :func:`audit_claims` is a
fail-closed lint over any claim string the product renders, so a regression in
wording is a test failure rather than a quiet overclaim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .backends import DEFAULT_MAX_AMPLITUDES, backend_matrix

__all__ = [
    "CAPACITY_STATEMENT",
    "LOGICAL_REGISTER_STATEMENT",
    "EXACTNESS_STATEMENT",
    "HARDWARE_STATEMENT",
    "UNAVAILABLE",
    "FORBIDDEN_CLAIM_PATTERNS",
    "ClaimViolation",
    "audit_claims",
    "capability_matrix",
    "render_matrix",
    "capability_report",
]

#: What the register is.  A parameter of the algebra, not a hardware ceiling.
LOGICAL_REGISTER_STATEMENT = (
    "The register width is a parameter of the algebra, not a hardware ceiling: "
    "the engine accepts any n >= 1, and the documented default is n = 10,000. "
    "Wide registers are exact because they are represented in an efficient "
    "state class, not because a dense state vector exists."
)

#: What "exact" means, and for which state classes.
EXACTNESS_STATEMENT = (
    "Every backend is an exact classical evaluation of a restricted, "
    "efficiently-simulable quantum state class: stabilizer/Clifford, "
    "free-fermion closed form, closed-form walk, and a universal Clifford+T "
    "algebra over Q(sqrt(2)) + i*Q(sqrt(2)) within an explicit "
    "materialisation budget. Amplitudes, norms and Born probabilities are "
    "mathematically exact for those classes, with no tolerance anywhere."
)

#: What exact simulation is not.
HARDWARE_STATEMENT = (
    "This is not quantum hardware and confers none of the runtime advantage of "
    "quantum hardware. Simulating a quantum circuit classically does not "
    "confer that circuit's complexity-class advantage. Any query-complexity "
    "figure the discovery engine reports is the textbook ratio of the "
    "algorithm under analysis, not a measured improvement from this package."
)

#: Explicitly not available.  Named so nobody has to infer it.
UNAVAILABLE: tuple[dict[str, str], ...] = (
    {
        "item": "arbitrary universal circuit evaluation at large width",
        "why": (
            "Exact classical evaluation of a general n-qubit circuit needs a "
            "dense 2^n state. Beyond the materialisation budget it is refused, "
            "not approximated."
        ),
    },
    {
        "item": "physical QPU execution",
        "why": (
            "No provider adapter is bundled. QPUBackend refuses every program "
            "until a provider is registered and configured, and measured_qpu "
            "stays False."
        ),
    },
    {
        "item": "hardware speedup claims",
        "why": "Simulating a circuit classically does not confer its speedup.",
    },
    {
        "item": "consensus authority of any kind",
        "why": (
            "The VQC orders and certifies search; SHA-256d target comparison "
            "remains the sole accept authority."
        ),
    },
    {
        "item": "theorem proofs",
        "why": "This package executes algebra. It proves no theorems.",
    },
)

#: Unqualified claim patterns the audit refuses.
FORBIDDEN_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"universal\s+10[,.]?000[-\s]?qubit\s+(computer|machine|system)\b",
        "states universal 10,000-qubit computation without naming the state class",
    ),
    (
        r"\bphysical\s+quantum\s+computer\b(?!\s*(refus|is\s+not|never|unavailab))",
        "asserts a physical quantum computer",
    ),
    (
        r"\bwe\s+(built|have)\s+a\s+(physical\s+)?(quantum|QPU)\b",
        "asserts a built quantum device",
    ),
    (
        r"\bmeasured\s+on\s+(a\s+)?(real\s+)?(quantum|QPU|hardware)\b(?!\s*(job|record))",
        "asserts a measured hardware run",
    ),
    (
        r"\bspeedup\s+(of|is|from)\b(?!.*\bquery\s+complex)",
        "asserts a speedup without qualifying it as query complexity",
    ),
    (
        r"\bbreak(s|ing)?\s+(RSA|ECDSA|AES|SHA-?256)\b",
        "asserts cryptanalytic capability",
    ),
)


@dataclass(frozen=True)
class ClaimViolation:
    """One unqualified claim found in rendered text."""

    pattern: str
    reason: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.reason}: …{self.excerpt}…"


def audit_claims(text: str) -> list[ClaimViolation]:
    """Fail-closed lint over claim text.

    Returns every violation found.  An empty list means the text asserts
    nothing this package cannot support.
    """
    violations: list[ClaimViolation] = []
    for pattern, reason in FORBIDDEN_CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            violations.append(
                ClaimViolation(pattern, reason, text[start:end].replace("\n", " "))
            )
    return violations


def capability_matrix(*, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES) -> list[dict[str, Any]]:
    """The per-backend matrix with live availability."""
    return backend_matrix(max_amplitudes=max_amplitudes)


def render_matrix(*, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES) -> str:
    """A plain-text rendering of the capability matrix."""
    rows = capability_matrix(max_amplitudes=max_amplitudes)
    headers = ("backend", "execution class", "materialises", "gate set", "max width", "available")
    table = [headers]
    for row in rows:
        width = row["max_qubits"]
        table.append(
            (
                row["backend"],
                row["execution_class"],
                "yes" if row["materialises_state"] else "no",
                row["gate_set"],
                "unbounded" if width is None else str(width),
                "yes" if row["available"] else "no",
            )
        )
    widths = [max(len(str(row[i])) for row in table) for i in range(len(headers))]
    lines = []
    for position, row in enumerate(table):
        line = "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        lines.append(line.rstrip())
        if position == 0:
            lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    return "\n".join(lines)


def capability_report(*, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES) -> dict[str, Any]:
    """The full published capability report, claim-audited."""
    statements = {
        "logical_register": LOGICAL_REGISTER_STATEMENT,
        "exactness": EXACTNESS_STATEMENT,
        "hardware": HARDWARE_STATEMENT,
    }
    violations: list[str] = []
    for name, text in statements.items():
        for violation in audit_claims(text):
            violations.append(f"{name}: {violation}")
    return {
        "schema": "turing.vqc.capability_report.v1",
        "statements": statements,
        "unavailable": [dict(entry) for entry in UNAVAILABLE],
        "matrix": capability_matrix(max_amplitudes=max_amplitudes),
        "claim_violations": violations,
        "claim_boundary_clean": not violations,
    }
