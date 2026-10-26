"""HYBA vs David Silver / Ineffable Intelligence — honest DD benchmark.

Public facts (cite):
  - Ineffable Intelligence founded by David Silver (ex-DeepMind, AlphaGo/AlphaZero).
  - Reported ~$1.1B seed at ~$5.1B valuation (Apr 2026) — Sequoia, Nvidia, Google class backers.
  - Mission: "superlearner" discovering knowledge from own experience; era of experience vs human data.
  - As of public materials: research/lab posture; product code and production benchmarks not released.

HYBA posture (this freeze):
  - $0 invent capital for local production-demonstrable data plane + autonomic substrate.
  - Implemented fold/quantum-for-data/Salamander/complexity harnesses with tests and artifacts.
  - NOT claiming AGI product or that Silver's science is worthless — claiming capital is funding an
    *aspiration timeline* while HYBA ships *instrumented emergence enhancement* on infrastructure today.

Claim lanes:
  - Competitive capital comparison: EXTERNAL with citations
  - "More capable AGI than Ineffable": RESTRICTED until sealed eval suite vs public benchmarks
  - Architecture + local production readiness: EXTERNAL/BOUNDED with evidence
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

INEFFABLE_PUBLIC = {
    "entity": "Ineffable Intelligence",
    "founder": "David Silver",
    "background": "ex-DeepMind RL lead; AlphaGo / AlphaZero lineage",
    "reported_seed_usd": 1_100_000_000,
    "reported_valuation_usd": 5_100_000_000,
    "reported_round_date": "2026-04",
    "citations": [
        "https://www.cnbc.com/2026/04/27/deepmind-ineffable-intelligence-record-seed-funding-nvidia-google.html",
        "https://techcrunch.com/2026/04/27/deepminds-david-silver-just-raised-1-1b-to-build-an-ai-that-learns-without-human-data/",
        "https://www.ineffable.ai/",
        "https://sequoiacap.com/article/partnering-with-ineffable-intelligence-a-superlearner-for-the-era-of-experience/",
    ],
    "mission_public": "superlearner discovering knowledge from own experience; first contact with superintelligence",
    "product_public": "research lab / aspiration — no public production product suite comparable to HYBA Data freeze",
    "capital_character": "record seed funding for timeline + thesis credibility",
}

HYBA_PUBLIC = {
    "entity": "HYBA Data (HYBA Software Ltd)",
    "invent_capital_usd": 0,
    "posture": "local production-ready software freeze; CIaaS data plane + emergence substrate",
    "founder_context": "built under extreme personal constraint — hungry/homeless chapter; $0 invent capital",
    "what_is_shipped_in_freeze": [
        "PHI-1 runtime fold/unfold/verify",
        "PULVINI / Φ-UFE engine path",
        "Salamander autonomic cycle",
        "complexity gradient + instantiation evidence modules",
        "honest quantum-for-data batteries",
        "CIaaS savings metering",
        "claims gates + CI doctrine",
    ],
    "not_claimed": [
        "Public AGI leaderboard victory over Ineffable",
        "Customer T3 seals for M3",
        "Multi-cloud PROVEN production",
        "That Silver's research is without scientific value",
    ],
}


def capability_rows() -> List[Dict[str, Any]]:
    return [
        {
            "domain": "Learning from experience",
            "ineffable": "Superlearner thesis — experience without human data (claimed direction)",
            "hyba": "Measured adaptive loops: Salamander heal/optimize, dream/proposal gates, evidence-based regeneration modules",
            "hyba_status": "IMPLEMENTED_BOUNDED",
            "ineffable_status": "ASPIRATIONAL_PUBLIC",
        },
        {
            "domain": "Emergence philosophy",
            "ineffable": "Intelligence via large-scale RL experience engines (capital-intensive)",
            "hyba": "Emergence instantiated from complexity; cannot be engineered as a feature; enhanced once present",
            "hyba_status": "DOCTRINE_EXTERNAL + HARNESS_BOUNDED",
            "ineffable_status": "IMPLICIT_IN_THESIS",
        },
        {
            "domain": "Production software today",
            "ineffable": "No public product codebase / pilot suite comparable",
            "hyba": "Local production freeze, elevation runner, fold/GPU/storage/SDK surfaces",
            "hyba_status": "PRODUCTION_LOCAL_READY",
            "ineffable_status": "NOT_PUBLICLY_SHIPPED",
        },
        {
            "domain": "Infrastructure / data plane",
            "ineffable": "RL infrastructure partnership narrative (e.g. NVIDIA collab messaging)",
            "hyba": "CIaaS memory/data plane — fold never truncate; gain-share measured savings",
            "hyba_status": "IMPLEMENTED_BOUNDED",
            "ineffable_status": "INFRA_FOR_FUTURE_SUPERLEARNER",
        },
        {
            "domain": "Capital efficiency",
            "ineffable": "~$1.1B seed to pursue superintelligence timeline",
            "hyba": "$0 invent capital for demonstrable core; capital would scale GTM not invent v0",
            "hyba_status": "EXTERNAL_FACT_OF_BUILD",
            "ineffable_status": "EXTERNAL_REPORTED_FUNDING",
        },
        {
            "domain": "Self-healing / autonomic ops",
            "ineffable": "Not a published production autonomic product surface",
            "hyba": "Salamander circuit + optimising engine + regenerator proposals",
            "hyba_status": "IMPLEMENTED_BOUNDED",
            "ineffable_status": "NOT_DEMONSTRATED_PUBLIC",
        },
        {
            "domain": "Quantum-for-data / substrate maths",
            "ineffable": "Not the public product framing",
            "hyba": "Quantum from maths; serves data plane; honest batteries",
            "hyba_status": "IMPLEMENTED_EXTERNAL_LANGUAGE",
            "ineffable_status": "N_A",
        },
        {
            "domain": "Open-ended superintelligence product",
            "ineffable": "Core mission — first contact with superintelligence",
            "hyba": "RESTRICTED as market claim; emergence enhanced on infrastructure substrate",
            "hyba_status": "RESTRICTED_PRODUCT_CLAIM",
            "ineffable_status": "MISSION_ASPIRATION",
        },
    ]


def build_benchmark_report(
    artifact_dir: str | Path = "artifacts/hyba_data/elevation",
) -> Dict[str, Any]:
    from hyba_data.emergence import build_emergence_report

    emerg = build_emergence_report(artifact_dir=artifact_dir)
    report = {
        "title": "HYBA vs Ineffable — Aspiration Capital vs Instantiated Substrate",
        "bluf": (
            "David Silver's Ineffable is a capitalised *dream of superlearning* (~$1.1B seed). "
            "HYBA ships an *instantiated emergence-enhancement substrate* on the data plane at $0 invent capital. "
            "We do not claim public AGI victory; we claim production-demonstrable architecture and capital efficiency."
        ),
        "ineffable": INEFFABLE_PUBLIC,
        "hyba": HYBA_PUBLIC,
        "rows": capability_rows(),
        "emergence": {
            "status": emerg.get("status"),
            "doctrine": emerg.get("doctrine"),
            "passed": emerg.get("passed"),
            "artifact": emerg.get("artifact"),
        },
        "investor_line": (
            "Paying $1.1B for a timeline is optional. Demonstrating a wired substrate at $0 invent capital is not optional — we already did."
        ),
        "restricted": [
            "Do not say Ineffable science is worthless",
            "Do not say HYBA is proven AGI superior without sealed eval",
            "Do not invent Meta revenue / fake test counts",
        ],
        "status": "BENCHMARK_OK",
    }
    art = Path(artifact_dir)
    art.mkdir(parents=True, exist_ok=True)
    path = art / "HYBA_VS_INEFFABLE_BENCHMARK.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    report["artifact"] = str(path)
    return report
