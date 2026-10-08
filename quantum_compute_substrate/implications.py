"""Programmatic manifest of substrate-agnostic quantum implications.

Committed alongside docs/IMPLICATIONS.md so downstream tooling (grant apps,
investor decks, policy briefs) can render the taxonomy from a single source
of truth.

Claims discipline: this substrate executes quantum-mathematical algorithms as
software on classical hardware. Every statement below describes mathematical
capability (the algorithm runs, the state is represented) — none of it is a
measured quantum speedup or a hardware-backed result. Wall-clock advantage
over classical computation is not claimed anywhere in this manifest.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

__all__ = [
    "Implication",
    "ImplicationCategory",
    "IMPLICATIONS",
    "all_implications",
    "category_names",
    "implication_count",
]


@dataclass(frozen=True)
class Implication:
    key: str
    title: str
    bullets: Tuple[str, ...]


@dataclass(frozen=True)
class ImplicationCategory:
    key: str
    title: str
    subcategories: Tuple[Implication, ...]


_COMPUTATIONAL = ImplicationCategory(
    key="computational",
    title="Computational Implications",
    subcategories=(
        Implication(
            key="quantum_democratization",
            title="Quantum Democratization",
            bullets=(
                "Hardware Independence: Quantum-mathematical algorithms run as software on any substrate (GPU, CPU, FPGA, ASIC, cloud, edge).",
                "Immediate Deployment: No waiting for physical quantum computers to mature.",
                "Universal Access: Same quantum-mathematical operations on a $50 Raspberry Pi or $100M supercomputer.",
                "Moore's Law Continuation: Classical hardware advances directly benefit quantum-mathematical computation.",
            ),
        ),
        Implication(
            key="memory_revolution",
            title="Memory Revolution",
            bullets=(
                "Phi-Fold Compression: phi-fold maps a 2^4096-dim state space to 4096*128^2*2 parameters (~54M x) for the phi-structured state family it targets; arbitrary quantum states are not compressible this way.",
                "Quantum State Storage: Phi-structured states that were intractable to store directly become tractable in compressed form.",
                "Scalability Relief: Memory is no longer the bottleneck within the compressible state family.",
                "Reduced Complexity Footprint: Representation cost for the target state family becomes polynomial rather than exponential; general quantum simulation complexity is unchanged.",
            ),
        ),
        Implication(
            key="algorithm_renaissance",
            title="Algorithm Renaissance",
            bullets=(
                "Algorithm-Level Speedups Formalized: Grover O(sqrt(N)) and Shor polynomial-time factoring are demonstrated as mathematics; on classical substrates they execute as simulation that reproduces the algorithm, not its speedup.",
                "Hybrid Algorithms: Seamless quantum-classical integration without hardware constraints.",
                "Algorithm Portability: Quantum algorithms become substrate-independent software.",
                "Rapid Innovation: No hardware deployment cycle for algorithmic advances.",
            ),
        ),
    ),
)

_SOCIETAL = ImplicationCategory(
    key="societal",
    title="Societal Implications",
    subcategories=(
        Implication(
            key="scientific_acceleration",
            title="Scientific Acceleration",
            bullets=(
                "Drug Discovery: VQE runs on classical hardware as simulation, reproducing the variational procedure at classical cost.",
                "Climate Modeling: Quantum-mathematical kernels can run inside existing HPC workflows; exascale deployment is a target, not a demonstrated result.",
                "Materials Science: Classical quantum-system simulation for battery, semiconductor, superconductor design.",
                "Fundamental Physics: LHC data analysis with quantum pattern recognition.",
            ),
        ),
        Implication(
            key="education_workforce",
            title="Education and Workforce",
            bullets=(
                "Quantum Literacy: Remove hardware barrier to quantum education.",
                "Universal Curriculum: Quantum computing taught on standard university compute clusters.",
                "Skill Development: Large pool of quantum-trained developers without hardware access constraints.",
                "Democratized Research: Any institution can contribute to quantum algorithm development.",
            ),
        ),
        Implication(
            key="geopolitical_equity",
            title="Geopolitical Equity",
            bullets=(
                "Technology Access: Nations without quantum hardware programs can still develop quantum expertise.",
                "Reduced Arms Race: Less pressure to build physical quantum computers for strategic advantage.",
                "Global Collaboration: Shared mathematical substrate enables international quantum cooperation.",
                "Standardization: Mathematical quantum becomes universal standard vs fragmented hardware approaches.",
            ),
        ),
        Implication(
            key="ethical_considerations",
            title="Ethical Considerations",
            bullets=(
                "Cryptography Impact: Post-quantum cryptography urgency remains (Shor's algorithm works).",
                "AI Safety: Quantum-mathematical ML techniques may accelerate AI development; any advantage claim requires benchmark evidence.",
                "Resource Allocation: Compute resources become the constraint vs specialized quantum hardware.",
                "Transparency: Mathematical quantum is more auditable than black-box quantum hardware.",
            ),
        ),
    ),
)

_ENTERPRISE = ImplicationCategory(
    key="enterprise",
    title="Enterprise Implications",
    subcategories=(
        Implication(
            key="immediate_roi",
            title="Immediate ROI",
            bullets=(
                "No CapEx Investment: Quantum-mathematical capability on classical hardware without $10M+ quantum computer purchases.",
                "Existing Infrastructure: Quantum-mathematical algorithms run on current GPU/CPU clusters.",
                "Rapid Deployment: Quantum-mathematical workloads deploy in weeks, not years.",
                "Risk Reduction: No quantum hardware obsolescence risk.",
            ),
        ),
        Implication(
            key="competitive_advantages",
            title="Competitive Advantages",
            bullets=(
                "Financial Services: Quantum-mathematical portfolio optimization and Monte Carlo formulations, fraud detection.",
                "Pharmaceuticals: Quantum-system simulation for drug discovery on existing HPC at classical simulation cost.",
                "Logistics: Quantum-mathematical optimization formulations for routing, scheduling, supply chain.",
                "Energy: Quantum-mathematical grid optimization formulations; battery materials simulation.",
            ),
        ),
        Implication(
            key="new_business_models",
            title="New Business Models",
            bullets=(
                "Quantum-as-a-Service: Mathematical quantum APIs on cloud infrastructure.",
                "Quantum Software Market: Algorithm development becomes a pure software business.",
                "Consulting Services: Quantum optimization expertise without hardware dependency.",
                "Platform Economics: Winner-takes-all dynamics for quantum software platforms.",
            ),
        ),
        Implication(
            key="industry_transformation",
            title="Industry Transformation",
            bullets=(
                "Semiconductor Industry: Shift from quantum hardware to quantum-optimized classical hardware.",
                "Cloud Providers: Quantum capabilities become a standard feature, not a specialized service.",
                "Software Industry: New category of quantum algorithm developers.",
                "Traditional Computing: Quantum features integrated into standard computing stacks.",
            ),
        ),
    ),
)

_STRATEGIC = ImplicationCategory(
    key="strategic",
    title="Strategic Implications",
    subcategories=(
        Implication(
            key="redefinition_of_quantum",
            title="Redefinition of Quantum Computing",
            bullets=(
                "From Physical to Mathematical: Quantum becomes a computational paradigm, not a hardware category.",
                "From Niche to Mainstream: Quantum-mathematical methods become available to all computing workloads.",
                "From Future to Present: Quantum-mathematical computing runs today; hardware-backed quantum advantage remains ahead.",
                "From Laboratory to Production: Quantum-mathematical algorithms move from research to deployment.",
            ),
        ),
        Implication(
            key="new_research_directions",
            title="New Research Directions",
            bullets=(
                "Substrate Optimization: Hardware optimized for mathematical quantum operations.",
                "phi-Scaling Applications: Golden ratio compression applied beyond quantum states.",
                "Quantum-Classical Boundaries: Exploration of where mathematical quantum diverges from physical.",
                "Complexity Theory: New understanding of computational complexity classes.",
            ),
        ),
        Implication(
            key="investment_and_funding",
            title="Investment and Funding",
            bullets=(
                "Software Focus: Investment shifts from quantum hardware to quantum software.",
                "Infrastructure Investment: Classical infrastructure optimized for quantum workloads.",
                "Education Investment: Quantum training programs without hardware constraints.",
                "Research Investment: Mathematical quantum research vs experimental quantum physics.",
            ),
        ),
    ),
)

IMPLICATIONS: Tuple[ImplicationCategory, ...] = (
    _COMPUTATIONAL,
    _SOCIETAL,
    _ENTERPRISE,
    _STRATEGIC,
)

PARADIGM_ANALOGS: Tuple[Tuple[str, str], ...] = (
    ("AI", "From specialized neuromorphic chips to GPU-accelerated neural networks."),
    ("Graphics", "From dedicated graphics hardware to programmable shaders."),
    ("Cryptography", "From specialized devices to software algorithms."),
)

PARADIGM_SHIFT_STATEMENT = (
    "Quantum computing is redefined from 'requires exotic hardware' to "
    "'requires mathematical operations'. The phi-fold memory compression "
    "turns the exponential memory requirement for phi-structured states "
    "into a manageable compression problem. This is a categorical "
    "redefinition of what quantum computing means and who can access it."
)


def all_implications() -> List[Implication]:
    return [imp for cat in IMPLICATIONS for imp in cat.subcategories]


def category_names() -> List[str]:
    return [cat.title for cat in IMPLICATIONS]


def implication_count() -> Dict[str, int]:
    return {cat.key: len(cat.subcategories) for cat in IMPLICATIONS}
