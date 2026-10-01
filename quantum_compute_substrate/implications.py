"""Programmatic manifest of substrate-agnostic quantum implications.

Committed alongside docs/IMPLICATIONS.md so downstream tooling (grant apps,
investor decks, policy briefs) can render the taxonomy from a single source
of truth.
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
                "Hardware Independence: Quantum algorithms run on any substrate (GPU, CPU, FPGA, ASIC, cloud, edge).",
                "Immediate Deployment: No waiting for physical quantum computers to mature.",
                "Universal Access: Same quantum-mathematical operations on a $50 Raspberry Pi or $100M supercomputer.",
                "Moore's Law Continuation: Classical hardware advances directly benefit quantum computation.",
            ),
        ),
        Implication(
            key="memory_revolution",
            title="Memory Revolution",
            bullets=(
                "Exponential Compression: phi-fold reduces 2^4096 -> 4096*128^2*2 (~54M x compression factor).",
                "Quantum State Storage: Previously intractable quantum states become tractable.",
                "Scalability Barrier Broken: Memory no longer the bottleneck for quantum representation.",
                "New Complexity Class: Efficient quantum representation becomes polynomial rather than exponential.",
            ),
        ),
        Implication(
            key="algorithm_renaissance",
            title="Algorithm Renaissance",
            bullets=(
                "Quantum Speedup Today: Grover sqrt(N), Shor exponential, quantum ML advantages available now.",
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
                "Drug Discovery: Quantum chemistry VQE on classical hardware accelerates molecular simulation.",
                "Climate Modeling: Exascale quantum-enhanced climate models on existing supercomputers.",
                "Materials Science: Quantum simulation for battery, semiconductor, superconductor design.",
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
                "AI Safety: Quantum ML advantages accelerate AI development, requiring enhanced safety measures.",
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
                "No CapEx Investment: Quantum advantages without $10M+ quantum computer purchases.",
                "Existing Infrastructure: Quantum algorithms run on current GPU/CPU clusters.",
                "Rapid Deployment: Quantum advantages in weeks, not years.",
                "Risk Reduction: No quantum hardware obsolescence risk.",
            ),
        ),
        Implication(
            key="competitive_advantages",
            title="Competitive Advantages",
            bullets=(
                "Financial Services: Quantum portfolio optimization, Monte Carlo acceleration, fraud detection.",
                "Pharmaceuticals: Quantum molecular simulation for drug discovery on existing HPC.",
                "Logistics: Quantum optimization for routing, scheduling, supply chain.",
                "Energy: Quantum-enhanced grid optimization, battery materials discovery.",
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
                "From Niche to Mainstream: Quantum advantages available to all computing workloads.",
                "From Future to Present: Quantum computing is now, not decades away.",
                "From Laboratory to Production: Quantum algorithms move from research to deployment.",
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
    "turns quantum's exponential memory requirement into a manageable "
    "compression problem. This is a categorical redefinition of what "
    "quantum computing means and who can access it."
)


def all_implications() -> List[Implication]:
    return [imp for cat in IMPLICATIONS for imp in cat.subcategories]


def category_names() -> List[str]:
    return [cat.title for cat in IMPLICATIONS]


def implication_count() -> Dict[str, int]:
    return {cat.key: len(cat.subcategories) for cat in IMPLICATIONS}
