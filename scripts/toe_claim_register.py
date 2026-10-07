"""Build the TOE claim register (JSON shipped in the package + rendered Markdown).

Each claim records: scope, status, evidence, counterevidence, limitations,
reproduction command and the source SHA at which its evidence report was
produced (read from the report itself, never invented).

Usage: python scripts/toe_claim_register.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def _sha(report: str) -> str:
    path = REPORTS / report
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("source_sha", "UNAVAILABLE")
    except (OSError, json.JSONDecodeError):
        return "UNAVAILABLE"


ABL = "toe_ablation_heldout.json"
UPE = "toe_universal_principle_evidence.json"

CLAIMS: List[Dict[str, Any]] = [
    {
        "id": "toe-one-backend-many-domains",
        "claim": "Multiple substantially different problem classes are handled by the same TOE backend; only the domain adapter changes.",
        "scope": "8 problem classes (tabular, explicit causal system, graph, temporal, Python AST, integer recurrence, precision-critical linear system, legacy HR) plus PYTHIA mining telemetry",
        "status": "MEASURED",
        "evidence": "toe.voyage.cross_domain_voyage: one TOEMachine; adapter code in no backend trace; core imports no adapter",
        "counterevidence": None,
        "limitations": "backend stages that a problem's structure does not support are skipped (reported), not emulated",
        "reproduction": "python -m pytest tests/test_toe_cross_domain.py -q",
        "evidence_report": None,
    },
    {
        "id": "toe-every-possible-problem",
        "claim": "One backend can solve every possible problem / 10,000 frontend problem forms.",
        "scope": "as stated",
        "status": "UNSUPPORTED",
        "evidence": None,
        "counterevidence": "problems without numeric structure, a declared action vocabulary or a transition relation are described, not solved",
        "limitations": "the measured claim is toe-one-backend-many-domains",
        "reproduction": None,
        "evidence_report": None,
    },
    {
        "id": "toe-causal-ladder-live",
        "claim": "P(Y|X) can differ from P(Y|do X), and TOE reports both; a counterfactual requires an abducted unit.",
        "scope": "linear SCMs, supplied or estimated weights",
        "status": "MEASURED",
        "evidence": "confounded fixture: association slope > 0, interventional effect < 0; rung 3 refused without a factual unit",
        "counterevidence": None,
        "limitations": "linear structural equations; estimates are model-dependent on the supplied graph",
        "reproduction": "python -m pytest tests/test_toe_machine.py -q -k 'association or counterfactual'",
        "evidence_report": None,
    },
    {
        "id": "toe-identifiability-refusal",
        "claim": "An effect that is not identified from observed variables is refused, not estimated.",
        "scope": "supplied DAGs with latent nodes",
        "status": "MEASURED",
        "evidence": "latent-confounder problems return EFFECT_NOT_IDENTIFIED with effect_released=False",
        "counterevidence": None,
        "limitations": "backdoor/frontdoor/instrument strategies only",
        "reproduction": "python -m pytest tests/test_toe_machine.py -q -k identifiability",
        "evidence_report": None,
    },
    {
        "id": "toe-wrong-graph-detection",
        "claim": "A supplied graph whose testable implications fail in the data is reported STRUCTURE_CONTRADICTED and its effects withheld.",
        "scope": "local Markov implications, Gaussian partial correlation, Bonferroni",
        "status": "MEASURED",
        "evidence": "machine_battery 'false causal graph (testable)': detected",
        "counterevidence": "a wrong graph in the true graph's Markov-equivalence class passes every implication test",
        "limitations": "one-sided test; latent confounding can mimic implications",
        "reproduction": "python -c \"from toe.self_governance import machine_battery; print(machine_battery()['counts'])\"",
        "evidence_report": None,
    },
    {
        "id": "toe-capability-ablations",
        "claim": "Causal structure, counterfactual abduction, value of information, multi-representation navigation, world-model revision and futures-backed planning each change outcomes when their precondition holds.",
        "scope": "held-out randomized task families with negative controls",
        "status": "MEASURED",
        "evidence": "relevant families: benefit with non-overlapping 95% CIs; negative controls: parity",
        "counterevidence": "families are constructed so the precondition holds; frequency in real workloads is not measured",
        "limitations": "synthetic ground-truth worlds",
        "reproduction": "python scripts/toe_ablation_study.py --n 60",
        "evidence_report": ABL,
    },
    {
        "id": "toe-adaptive-precision-benefit",
        "claim": "Exact Q(phi) escalation changes decisions versus float64.",
        "scope": "cancellation near-ties",
        "status": "NEGATIVE (CPython 3.12)",
        "evidence": "escalation fires (exact-required) and decides correctly",
        "counterevidence": "on CPython 3.12 the futures engine's compensated float summation already decides these near-ties correctly: no measured benefit",
        "limitations": "the exact path remains the authority inside the declared float error bound; re-measure per interpreter",
        "reproduction": "python scripts/toe_ablation_study.py --n 60",
        "evidence_report": ABL,
    },
    {
        "id": "toe-learning-changes-behaviour",
        "claim": "Observed consequences revise the world model and change a later related decision; learning in one namespace does not revise another.",
        "scope": "linear SCM namespaces; OLS revision on post-intervention observations",
        "status": "MEASURED",
        "evidence": "canonical voyage: ACQUIRE_EVIDENCE -> contradiction -> revision -> different, VOI-invariant decision; other domain untouched",
        "counterevidence": None,
        "limitations": "revision requires a non-singular design; otherwise uncertainty is widened instead",
        "reproduction": "python -m pytest tests/test_toe_learning_persistence.py -q",
        "evidence_report": None,
    },
    {
        "id": "toe-durable-restart",
        "claim": "TOE learning state survives a process restart through THESEUS custody and the recorded decisions replay bit-identically.",
        "scope": "THESEUS EnterpriseCustody; hash-chained producer='toe' snapshots",
        "status": "MEASURED",
        "evidence": "fresh-process recovery test; tampered chain raises SnapshotIntegrityError",
        "counterevidence": None,
        "limitations": "without THESEUS installed, persistence is UNAVAILABLE (no private store)",
        "reproduction": "python -m pytest tests/test_toe_learning_persistence.py -q",
        "evidence_report": None,
    },
    {
        "id": "toe-geometric-reasoning",
        "claim": "TOE's geometric layer (Poincare ball on the 11D metric, Sarkar tree embedding, greedy routing, spectral geometry) is verified and changes navigation solvability on walled graphs.",
        "scope": "declared operations; float64 within MAX_EMBED_RADIUS",
        "status": "MEASURED",
        "evidence": "metric axioms, geodesics, isometry tests; delivery 1.00 vs 0.61 (Euclidean) on walled grids",
        "counterevidence": "on open grids the hyperbolic route is longer than Euclidean (no advantage)",
        "limitations": "embedding depth bounded by float64 resolution; learning embeddings from data is not implemented",
        "reproduction": "python -m pytest tests/test_toe_geometry.py -q",
        "evidence_report": ABL,
    },
    {
        "id": "toe-mining-boundary",
        "claim": "In mining, TOE advises an operational setting; PYTHIA authorizes; SHA256d + target comparison alone decide validity.",
        "scope": "CPU-reference window decision on a regtest-difficulty template",
        "status": "MEASURED",
        "evidence": "all check_pow candidates independently rechecked; consensus-named variables refused in mining mode; toe/ never references check_pow",
        "counterevidence": None,
        "limitations": "no live pool job (no worker credentials on this host); throughput ratio vs baseline is run-to-run noise, not an advantage",
        "reproduction": "python scripts/toe_mining_voyage.py",
        "evidence_report": None,
    },
    {
        "id": "phi-ordering-sha256d",
        "claim": "phi-structured nonce ordering improves the probability of finding a valid SHA256d result.",
        "scope": "visit order of candidate nonces",
        "status": "NEGATIVE",
        "evidence": None,
        "counterevidence": "golden-stride vs linear order: hit counts within sampling noise",
        "limitations": "ordering can change which nonces are visited first, never the validity probability",
        "reproduction": "python scripts/toe_universal_principle_evidence.py",
        "evidence_report": UPE,
    },
    {
        "id": "universal-principle-structural-unity",
        "claim": "The golden family (Z[phi], Lucas, Binet, Cassini, Zeckendorf, Pisot) underlies TOE's exact arithmetic, geometry and ordering structures.",
        "scope": "mathematical identities and their implementations",
        "status": "PROVED + COMPUTATIONALLY_VERIFIED",
        "evidence": "identities verified exactly to n <= 2000; implementations reused across layers",
        "counterevidence": "Zeckendorf gives no compression; Lucas ladder is a trade-off, not an advantage",
        "limitations": "structural unity is not evidence of a shared physical phenomenon",
        "reproduction": "python scripts/toe_universal_principle_evidence.py",
        "evidence_report": UPE,
    },
    {
        "id": "same-phi-same-phenomenon",
        "claim": "Because phi appears in two places, they are the same physical phenomenon.",
        "scope": "as stated",
        "status": "UNSUPPORTED",
        "evidence": None,
        "counterevidence": None,
        "limitations": "physical interpretation requires separate proof",
        "reproduction": None,
        "evidence_report": None,
    },
    {
        "id": "yang-mills-finite",
        "claim": "The finite construction golden icosians -> 2I -> 600-cell -> Laplacian has a positive spectral gap (3-sqrt5)/4.",
        "scope": "finite group of order 120",
        "status": "COMPUTATIONALLY_VERIFIED",
        "evidence": "|2I|=120, closure, 9 classes, V/E/F/C=120/720/1200/600, sum d^2=120, gap 0.190983",
        "counterevidence": "UNIVERSAL_PRINCIPLE_MAP previously printed 0.381966 for this gap (corrected)",
        "limitations": "finite volume; lives in millennium/, read by toe.poincare_yangmills",
        "reproduction": "python scripts/toe_universal_principle_evidence.py",
        "evidence_report": UPE,
    },
    {
        "id": "yang-mills-continuum",
        "claim": "Continuum Yang-Mills existence and mass gap (Clay problem).",
        "scope": "R^4 continuum theory",
        "status": "OPEN",
        "evidence": None,
        "counterevidence": None,
        "limitations": "continuum limit, infinite volume, OS reconstruction and Wightman axioms not established",
        "reproduction": None,
        "evidence_report": None,
    },
    {
        "id": "software-quantum-computation",
        "claim": "TOE executes quantum-mathematical formalism (Hilbert states, unitary evolution, Born rule) in software.",
        "scope": "classical execution via kellogg.quantum_tensor",
        "status": "COMPUTATIONALLY_VERIFIED",
        "evidence": "unit-norm states; Born probabilities sum to 1",
        "counterevidence": None,
        "limitations": "software execution of the mathematics; TURING owns VQC execution",
        "reproduction": "python scripts/toe_universal_principle_evidence.py",
        "evidence_report": UPE,
    },
    {
        "id": "physical-quantum-execution",
        "claim": "TOE runs on, or obtains advantage from, a physical QPU.",
        "scope": "as stated",
        "status": "UNSUPPORTED",
        "evidence": None,
        "counterevidence": None,
        "limitations": "no physical-QPU evidence exists",
        "reproduction": None,
        "evidence_report": None,
    },
    {
        "id": "lucas-rungs-optimal-intelligence",
        "claim": "Lucas rungs 15, 18, 20 are optimal for intelligence.",
        "scope": "as stated in UNIVERSAL_PRINCIPLE_MAP 17.5",
        "status": "UNSUPPORTED",
        "evidence": None,
        "counterevidence": None,
        "limitations": "no TOE capability is parameterised by a rung; no comparative measurement exists",
        "reproduction": None,
        "evidence_report": None,
    },
]


def build() -> Dict[str, Any]:
    claims = []
    for c in CLAIMS:
        c = dict(c)
        c["source_sha"] = _sha(c["evidence_report"]) if c.get("evidence_report") else "see reproduction (test-backed at release SHA)"
        claims.append(c)
    return {"schema": "toe.claim_register/v1", "claims": claims}


def render(reg: Dict[str, Any]) -> str:
    lines = [
        "# TOE claim register",
        "",
        "Generated by `scripts/toe_claim_register.py` from the same data as `toe/CLAIM_REGISTER.json`.",
        "Statuses are never collapsed: PROVED, COMPUTATIONALLY_VERIFIED, MEASURED, NEGATIVE,",
        "MODEL_DEPENDENT, OPEN, UNSUPPORTED.",
        "",
        "| Claim | Status | Evidence | Counterevidence / limits | Reproduce |",
        "|---|---|---|---|---|",
    ]

    def cell(text: Any) -> str:
        return str(text).replace("|", "\\|") if text else "—"

    for c in reg["claims"]:
        lim = "; ".join(x for x in (c.get("counterevidence"), c.get("limitations")) if x)
        repro = ("`" + c["reproduction"] + "`") if c.get("reproduction") else None
        lines.append(
            f"| **{c['id']}** — {cell(c['claim'])} | {c['status']} | {cell(c.get('evidence'))} | "
            f"{cell(lim)} | {cell(repro)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    reg = build()
    (ROOT / "toe" / "CLAIM_REGISTER.json").write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ROOT / "docs" / "toe" / "CLAIM_REGISTER.md").write_text(render(reg), encoding="utf-8")
    print(f"{len(reg['claims'])} claims written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
