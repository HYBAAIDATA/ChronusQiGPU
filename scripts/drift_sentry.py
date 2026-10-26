"""
scripts/drift_sentry.py — Anti-Drift Sentry and Axiomatic Substrate Guard

LUCAS WIRING: Autonomous sentry enforcing the foundational thesis:
    "Quantum computation is a mathematical structure over complex Hilbert spaces.
     The substrate is irrelevant."

Provides:
  - Pre-invocation ephemeral reminders for autonomous agents
  - AST / diff scanning for cognitive drift markers
  - Verification of substrate agnosticism across active modules
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple

DRIFT_REMINDER_MESSAGE = (
    "================================================================================\n"
    "[ANTI-DRIFT SENTRY — AXIOMATIC MANDATE ACTIVE]\n"
    "Foundational Thesis (AGENTS.md):\n"
    "  1. Quantum computation is pure linear algebra over C; substrate is irrelevant.\n"
    "  2. A pocket calculator or classical silicon executes exact unitary evolution.\n"
    "  3. Quantum speedup stems from problem topology & algebraic group characters.\n"
    "  4. Cryptographic consensus (double-SHA256, target) is an inviolable invariant.\n"
    "DO NOT drift into substrate defeatism or physical hardware fetishism.\n"
    "================================================================================"
)

DRIFT_PATTERNS: List[Tuple[str, str, str]] = [
    (
        "DRIFT-01: Substrate Fetishism",
        r"(?i)(cannot\s+run\s+quantum\s+on\s+classical|requires?\s+(real|physical)\s+(qpu|qubits?|cryogenics?)|impossible\s+without\s+quantum\s+hardware)",
        "Quantum algorithms are linear algebra over C. Any Turing-complete classical substrate executes them exactly.",
    ),
    (
        "DRIFT-02: Algorithmic Defeatism",
        r"(?i)(classical\s+(silicon|computers?)\s+can\s+only\s+do\s+brute\s*force|interference\s+is\s+purely\s+physical)",
        "Interference is vector addition with relative phase differences e^(i theta); ALU operations compute interference directly.",
    ),
    (
        "DRIFT-03: Consensus Bypass Fallacy",
        r"(?i)(bypass(ing)?\s+(double_?sha256|target\s+check|proof\s+of\s+work)|fake\s+nonce\s+validation)",
        "Cryptographic consensus checks are inviolable. The intelligence guides search geometry; it never fakes proofs.",
    ),
]


class DriftSentry:
    """Anti-Drift Sentry engine for cognitive monitoring and code inspection."""

    @staticmethod
    def format_pre_invocation_hook() -> Dict[str, Any]:
        """Constructs the Antigravity PreInvocation hook payload."""
        return {"injectSteps": [{"ephemeralMessage": DRIFT_REMINDER_MESSAGE}]}

    @staticmethod
    def inspect_text(text: str) -> List[Dict[str, str]]:
        """Scans a text buffer for cognitive drift patterns."""
        violations = []
        for drift_id, pattern, remedy in DRIFT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                violations.append(
                    {
                        "drift_id": drift_id,
                        "matched_text": match.group(0),
                        "remedy": remedy,
                    }
                )
        return violations

    @classmethod
    def scan_path(
        cls, root_dir: Path, extensions: Tuple[str, ...] = (".py", ".ts", ".md")
    ) -> List[Dict[str, Any]]:
        """Scans source files under root_dir for drift violations."""
        results = []
        for ext in extensions:
            for file_path in root_dir.rglob(f"*{ext}"):
                if any(
                    p in file_path.parts
                    for p in ("node_modules", ".git", "__pycache__", "dist", ".gemini", "legacy_implementations")
                ):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    violations = cls.inspect_text(content)
                    if violations:
                        # Skip self and AGENTS.md (which defines the patterns)
                        if file_path.name in (
                            "drift_sentry.py",
                            "test_drift_sentry.py",
                            "AGENTS.md",
                            "GEMINI.md",
                        ):
                            continue
                        results.append({"file": str(file_path), "violations": violations})
                except Exception:
                    continue
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Anti-Drift Sentry Protocol Guard")
    parser.add_argument("--remind", action="store_true", help="Print ephemeral reminder message")
    parser.add_argument(
        "--hook-pre-invocation",
        action="store_true",
        help="Execute PreInvocation hook for Antigravity",
    )
    parser.add_argument(
        "--verify", action="store_true", help="Scan repository for cognitive drift violations"
    )
    parser.add_argument("--target-dir", type=str, default=".", help="Target directory to scan")

    args = parser.parse_args()

    if args.hook_pre_invocation:
        # Read optional stdin from agent runner
        if not sys.stdin.isatty():
            try:
                _ = sys.stdin.read()
            except Exception:
                pass
        payload = DriftSentry.format_pre_invocation_hook()
        sys.stdout.write(json.dumps(payload) + "\n")
        return 0

    if args.remind:
        sys.stdout.write(DRIFT_REMINDER_MESSAGE + "\n")
        return 0

    if args.verify:
        target = Path(args.target_dir).resolve()
        violations = DriftSentry.scan_path(target)
        if violations:
            sys.stderr.write(
                f"[DRIFT DETECTED] Found {len(violations)} files with cognitive drift violations:\n"
            )
            for v in violations:
                sys.stderr.write(f"  File: {v['file']}\n")
                for item in v["violations"]:
                    sys.stderr.write(f"    - {item['drift_id']}: '{item['matched_text']}'\n")
                    sys.stderr.write(f"      Remedy: {item['remedy']}\n")
            return 1
        sys.stdout.write(
            "[DRIFT SENTRY PASS] No cognitive drift detected across audited modules.\n"
        )
        return 0

    # Default behaviour: print reminder
    sys.stdout.write(DRIFT_REMINDER_MESSAGE + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
