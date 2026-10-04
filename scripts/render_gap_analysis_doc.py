"""Render docs/JULY_2026_CAPABILITY_GAP_ANALYSIS.md from the machine manifest."""

import json
from collections import Counter

MANIFEST = "manifests/july_2026_capability_gap_analysis.json"
DOC = "docs/JULY_2026_CAPABILITY_GAP_ANALYSIS.md"


def main() -> None:
    with open(MANIFEST, encoding="utf-8") as handle:
        doc = json.load(handle)
    entries = doc["entries"]
    counts = Counter(e["status"] for e in entries)

    lines = [
        "# July 2026 Capability Gap Analysis",
        "",
        f"Reference date: {doc['reference_date']}. Machine-readable source of truth:",
        f"`{MANIFEST}` (schema `{doc['schema']}`). This document is rendered from",
        "that manifest by `scripts/render_gap_analysis_doc.py` — do not edit it by",
        "hand; regenerate instead.",
        "",
        "## Verdict",
        "",
        f"All {len(entries)} inventoried July 2026 surfaces are accounted for:",
        *[f"- **{status}**: {count}" for status, count in sorted(counts.items())],
        "",
        "- `present`/`elevated`/`adapter-added` rows name a live importable symbol",
        "  and exactly three evidence tests (unit, invariant, integration) that",
        "  exist and pass in this checkout.",
        "- `superseded`/`retired-with-reason` rows name an executable redirect",
        "  resolved by `HISTORICAL_REDIRECTS` in",
        "  `turing_universal_quantum_computer/july_compat.py`, plus a retirement",
        "  reason.",
        "- The aggregate gate is `tests/test_july_capability_gap_analysis.py` and",
        "  `tests/test_july_chronos_mapping.py`: any row whose evidence test is",
        "  renamed or deleted fails CI.",
        "",
        "Nothing in this table claims production readiness without a named,",
        "passing test. Historical totals (61/61, 110/110, 144/144) are provenance",
        "only — fresh evidence is the cited tests.",
        "",
        "## Status definitions",
        "",
        "| Status | Meaning |",
        "|---|---|",
        "| present | Capability exists in the rebuilt tree under its canonical name. |",
        "| elevated | Capability exists and was strengthened relative to July (real implementation + measured audit fields). |",
        "| adapter-added | July surface kept as a thin adapter into a canonical owner; the adapter is bounded and fails closed. |",
        "| superseded | Replaced by a canonical owner; `redirect` resolves to it. |",
        "| retired-with-reason | No modern equivalent; `redirect` fails closed with a named reason. |",
        "",
        "## Inventory",
        "",
    ]

    for e in entries:
        lines.append(f"### `{e['id']}` — {e['status']}")
        lines.append("")
        lines.append(f"- **Historical surface**: `{e['public_surface']}` ({e['source_module']})")
        lines.append(f"- **Capability**: {e['historical_capability']}")
        lines.append(f"- **Current owner**: `{e['current_owner']}` ({e['current_path']})")
        if e["symbol"]:
            lines.append(f"- **Symbol**: `{e['symbol']}`")
        if e["evidence_tests"]:
            tests = "; ".join(f"`{t['kind']}: {t['nodeid']}`" for t in e["evidence_tests"])
            lines.append(f"- **Evidence**: {tests}")
        lines.append(f"- **Claim boundary**: {e['claim_boundary']}")
        if e["redirect"]:
            lines.append(f"- **Redirect**: `{e['redirect']}`")
        if e["retirement_reason"]:
            lines.append(f"- **Retirement reason**: {e['retirement_reason']}")
        lines.append("")

    lines += [
        "## Defects found and fixed during this analysis",
        "",
        "1. `chronus/v33/academic/caltech.py::_build_stabilizers` emitted boundary",
        "   checks that anti-commuted with the bulk plaquettes (weight-1 checks",
        "   inside opposite-type plaquettes). Replaced with the diagonal-corner",
        "   weight-2 boundary set X{(1,2),(6,7)} / Z{(0,3),(5,8)}: all 8",
        "   stabilizers commute, the code space has dimension 2 (one logical",
        "   qubit), and `verify_stabilizer_algebra` passes end-to-end.",
        "   `test_surface_code_decodes_single_error` was updated to assert the",
        "   real decoder contract (correction cancels the syndrome), because",
        "   boundary-degenerate single errors legitimately share syndromes and a",
        "   distance-3 code cannot return the identical error for every qubit.",
        "2. `turing_universal_quantum_computer/backends::_selection_order`",
        "   leaked non-Clifford programs to approximate backends at wide width",
        "   instead of refusing. Selection now fails closed when no declared",
        "   backend supports the program.",
        "3. `july_compat` was missing the `qaoa_optimize`, `CompositionStrategy`,",
        "   and several redirect surfaces the July inventory references; they are",
        "   now implemented as bounded adapters with measured result records",
        "   (no speedup, hardware, or consensus-authority claims).",
        "4. `salamander/control_plane.py::execute` degraded structural contract",
        "   violations (`FailClosed` for unregistered handlers, missing",
        "   idempotency keys) into a FAILED ActionResult instead of propagating.",
        "   FailClosed now propagates after an `action-rejected` ledger record.",
        "5. `euclid/runtime.py::restore` re-opened the state-dir sqlite a second",
        "   time and discarded the first handle; `Intelligence/pythia_store.py`",
        "   wrote its snapshot into a directory it never created. Both leaked",
        "   handles / broke close() and tempdir cleanup on Windows.",
        "6. `euclid` cognition never consumed `problem[\"strategy\"]` or",
        "   `problem[\"representation_evidence\"]`, `AblationConfig` had no",
        "   `mathematical_structure` switch for the v16 search skills, and the",
        "   reachability matrix had no rule that promoted `toe.world_model` to",
        "   FEEDBACK_CLOSED or `euclid.memory_database` to TRANSFER_VERIFIED.",
        "   `hyba_substrate` task contracts hard-failed on any new measured",
        "   action; `ExperienceSuperlearner.extend_task_actions` now grows the",
        "   declared action set through an audited checkpointed path.",
        "7. `StabilizerState.measure` forced outcome 0 on deterministic",
        "   qubits and then raised; the canonical 0 convention now applies only",
        "   to degenerate measurements, deterministic ones return the actual",
        "   outcome.",
        "8. `tests/test_backend_decision_evidence.py` left a bare ModuleType in",
        "   `sys.modules[\"chronus.mla1517.mining.coordinator\"]`, breaking every",
        "   later import from that module; tearDown now restores the real",
        "   module.",
        "9. `scripts/import_audit.py` resolved distribution directories after",
        "   the repo root, so `turing_universal_quantum_computer/` (which has a",
        "   pyproject and stray .py files) shadowed its inner package. `_dist_base`",
        "   now prefers dist dirs that actually resolve to a package.",
        "",
    ]

    text = "\n".join(lines)
    with open(DOC, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(DOC, len(entries), "rows")


if __name__ == "__main__":
    main()
