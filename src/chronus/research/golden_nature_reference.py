"""Research-only adapter to the standalone numerical reference package.

Exact Chronus mathematics emits descriptors; this adapter evaluates them
outside the mathematical execution namespace. No customer or production route.
"""
from fractions import Fraction
from golden_ontology.numeric_reference import (
    evolve_blocks, golden_section_minimize, numeric_frequency,
    project_kronecker, project_phyllotaxis,
)
from chronus.math.golden_nature import (
    kronecker_golden_exact, phyllotaxis_exact, anti_resonant_frequencies_exact,
)

__all__=["kronecker_golden_1d","phyllotaxis_disk","golden_section_minimize",
         "anti_resonant_frequencies","evolve_anti_resonant"]

def kronecker_golden_1d(n,seed=0.5):
    return project_kronecker(kronecker_golden_exact(n,Fraction(str(seed))))

def phyllotaxis_disk(n):
    return project_phyllotaxis(phyllotaxis_exact(n))

def anti_resonant_frequencies(n_blocks,base_omega=0.15):
    return [numeric_frequency(f) for f in anti_resonant_frequencies_exact(
        n_blocks,Fraction(str(base_omega)))]

def evolve_anti_resonant(state,time_step=0.5,base_omega=0.15):
    frequencies=anti_resonant_frequencies_exact(len(state)//2,Fraction(str(base_omega)))
    return evolve_blocks(state,frequencies,time_step)
