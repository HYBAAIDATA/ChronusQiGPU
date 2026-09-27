"""
PYTHAGORAS — CLI
Command-line interface for the Meta-Evolutionary Engine.

The engine is domain-agnostic: --domain selects the pluggable domain
(code, circuit, molecule, market, network). Code is the default and was
the first domain; it is not the only one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

from .domain import Domain, resolve_domain
from .domains import available_domains
from .phi_resonance import PHI
from .orchestrator import Pythagoras, read_source_utf8, write_source_utf8


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PYTHAGORAS — Meta-Evolutionary Engine (φ-Resonance Platform)"
    )
    parser.add_argument("path", type=str, help="Artifact file or directory to evolve/analyze")
    parser.add_argument(
        "--domain",
        type=str,
        default="code",
        choices=available_domains(),
        help="Pluggable domain: %(choices)s (default: code)",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=20,
        help="Number of evolutionary generations (default: 20)",
    )
    parser.add_argument(
        "--analyze-only", action="store_true", help="Analyze structural coherence without evolving"
    )
    parser.add_argument(
        "--diagnose-manifold",
        action="store_true",
        help="Run ENH-02 φ-sensitivity manifold diagnostic",
    )
    parser.add_argument(
        "--condition",
        type=str,
        default="B",
        choices=["A", "B", "C"],
        help="Experimental condition: A (meta=OFF), B (meta=ON), C (isolated measurement)",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Directory to save evolved artifacts"
    )
    parser.add_argument(
        "--memory-file",
        type=str,
        default=None,
        help="Path to multi-session memory JSON file (ENH-13)",
    )
    parser.add_argument(
        "--kellogg-reflect",
        action="store_true",
        help="Output Kellogg v7.0 quantum reflection tensors",
    )
    parser.add_argument("--lucas-multiplier", action="store_true", help="Enable Lucas multiplier")
    parser.add_argument("--pisot-collapse", action="store_true", help="Enable Pisot collapse")
    parser.add_argument("--atomic-memory", action="store_true", help="Enable atomic memory")
    parser.add_argument("extra", nargs="*", help="Additional trailing arguments (e.g. state.json)")

    args = parser.parse_args()
    domain: Domain = resolve_domain(args.domain)
    target_path = Path(args.path)

    if not target_path.exists():
        print(f"Error: Path not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    files: Dict[str, str] = {}
    if target_path.is_file():
        files[target_path.name] = read_source_utf8(target_path)
    elif target_path.is_dir():
        for ext in domain.file_extensions:
            for artifact in sorted(target_path.glob(f"*{ext}")):
                files[artifact.name] = read_source_utf8(artifact)

    if not files:
        exts = ", ".join(domain.file_extensions)
        print(
            f"Error: No '{domain.name}' artifacts ({exts}) found in {target_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    pythagoras = Pythagoras(condition=args.condition, domain=domain)

    # Load multi-session memory if provided
    if args.memory_file and Path(args.memory_file).exists():
        pythagoras.load_session(args.memory_file)
        print(f"[*] Loaded multi-session memory from {args.memory_file}")

    # ENH-02: Manifold Diagnostic (domain-agnostic: primitives probe the manifold)
    if args.diagnose_manifold:
        print(f"\n=== PYTHAGORAS — MANIFOLD DIAGNOSTIC (ENH-02) [{domain.name}] ===")
        for fname, src in files.items():
            diag = domain.diagnose_manifold(src)
            print(f"\nFile: {fname}")
            print(f"  Base φ:            {diag['base_phi']:.4f}")
            for comp_name, comp_val in diag["components"].items():
                if comp_name != "composite":
                    print(f"  {comp_name:<18} {comp_val:.4f}")
            print(f"  Max Gradient:      {diag['max_abs_gradient']:.6f}")
            print(
                f"  Degenerate Basin:  {'YES (Flat Hamiltonian)' if diag['is_degenerate_manifold'] else 'NO'}"
            )
            print(f"  Recommended Mode:  {diag['recommended_escape']}")
        return

    # Analyze-Only Mode
    if args.analyze_only:
        print(f"\n=== PYTHAGORAS — STRUCTURAL COHERENCE AUDIT [{domain.name}] ===")
        for fname, src in files.items():
            comps = domain.compute_components(src)
            composite = comps["composite"]
            status = "RESONANT (≥ φ)" if composite >= PHI else "DEGENERATE (< φ)"
            breakdown = " | ".join(
                f"{name}: {val:.3f}" for name, val in comps.items() if name != "composite"
            )
            print(f"{fname:<30} φ = {composite:.4f}  " f"[{breakdown}]  " f"[{status}]")
        return

    # Evolutionary Run
    print(
        f"\n=== PYTHAGORAS — EVOLUTIONARY RUN [Domain {domain.name} | Condition {args.condition}] ==="
    )

    active_flags = []
    if args.kellogg_reflect:
        active_flags.append("Kellogg Reflection")
    if args.lucas_multiplier:
        active_flags.append("Lucas Multiplier")
    if args.pisot_collapse:
        active_flags.append("Pisot Collapse")
    if args.atomic_memory:
        active_flags.append("Atomic Memory")

    if active_flags:
        print(f"[*] Active Subsystems: {', '.join(active_flags)}")

    corpus_results = pythagoras.evolve_corpus(files, generations=args.generations)

    for fname, res in corpus_results["files"].items():
        delta_str = f"{res['delta_phi']:+.4f}"
        pt_marker = (
            f" [Phase Transitions: {len(res['phase_transitions'])}]"
            if res["phase_transitions"]
            else ""
        )
        print(
            f"{fname:<30} {res['initial_phi']:.4f} → {res['final_phi']:.4f} (Δ = {delta_str}){pt_marker}"
        )

        if args.kellogg_reflect:
            kellogg_data = pythagoras.kellogg_quantum_reflection(
                res["final_source"], marked_solutions=[fname]
            )
            print(
                f"  └─ Kellogg Metric g_xx: {kellogg_data['metric_tensor_diagonal']:.4f} | "
                f"Curvature: {kellogg_data['curvature']:.4f} | "
                f"Phase: {kellogg_data['reflection_phase']:.4f} rad"
            )

    print(f"\nCorpus Total Δφ: {corpus_results['total_delta_phi']:+.4f}")
    print(f"Corpus Average Final φ: {corpus_results['avg_final_phi']:.4f}")
    print(f"Consensus Substrate: {corpus_results['consensus_geometry']}")

    # Save outputs
    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fname, res in corpus_results["files"].items():
            write_source_utf8(out_dir / fname, res["final_source"])
        print(f"[*] Saved evolved files to {out_dir}")

    # Save multi-session memory
    if args.memory_file:
        pythagoras.save_session(args.memory_file)
        print(f"[*] Saved multi-session memory state to {args.memory_file}")


if __name__ == "__main__":
    main()
