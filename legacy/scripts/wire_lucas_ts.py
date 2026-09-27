"""One-shot Lucas wiring pass for TypeScript algorithm files.

Adds the LUCAS WIRING header comment to every TS algorithm file.
Idempotent: skips files that already contain the wiring marker.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WIRING_HEADER = (
    "// LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel\n"
    "// inline below. MUST NOT import from any sibling algorithm.\n"
    "// Substrate route: {route}\n"
)

# (file, route)
TS_ALGORITHM_FILES = [
    ("src/lib/first_principles_quantum.ts", "trace"),
    ("src/lib/quantum_engine.ts", "trace"),
    ("src/lib/quantum_walker_aqo.ts", "path"),
    ("src/lib/m3_igpu_scaler.ts", "mining"),
    ("src/lib/kellogg_operator.ts", "path"),
    ("src/lib/kellogg_full_stack.ts", "gap"),
    ("src/lib/grand_unified_tensor.ts", "amplitude"),
    ("src/lib/lucas_quantum_algorithms.ts", "trace"),
    ("src/lib/exact_math.ts", "trace"),
    ("src/lib/q5_reference.ts", "trace"),
    ("src/lib/q5_coprocessor.ts", "amplitude"),
    ("src/lib/q5_rtl_specs.ts", "amplitude"),
    ("src/lib/cortex_intelligence.ts", "amplitude"),
    ("src/lib/blockchain_consciousness.ts", "amplitude"),
    ("src/lib/bitcoin_header.ts", "mining"),
    ("src/lib/mining_service.ts", "mining"),
    ("src/lib/mempool_service.ts", "mining"),
    ("src/lib/mempool_nonce_analyzer.ts", "mining"),
    ("src/lib/difficulty_retargeting.ts", "mining"),
    ("src/lib/stratum_protocol.ts", "step"),
    ("src/lib/simple_event_emitter.ts", "step"),
    ("src/lib/mclaren_homeostasis.ts", "gap"),
    ("src/lib/hodge_bridge.ts", "gap"),
    ("src/lib/adversarial_checks.ts", "gap"),
    ("src/lib/audit_matrix.ts", "gap"),
    ("src/lib/verification_suite.ts", "trace"),
]


def wire_ts_file(rel_path: str, route: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return f"SKIP (missing): {rel_path}"
    text = path.read_text(encoding="utf-8")
    if "LUCAS WIRING:" in text:
        return f"SKIP (already wired): {rel_path}"
    header = WIRING_HEADER.format(route=route)
    # Insert at the very top of the file
    new_text = header + "\n" + text
    path.write_text(new_text, encoding="utf-8")
    return f"WIRED: {rel_path} ({route})"


def main() -> None:
    for rel, route in TS_ALGORITHM_FILES:
        print(wire_ts_file(rel, route))


if __name__ == "__main__":
    main()
