"""Expected Fibonacci data entry points; currently a failing qualification check."""
from chronus.quantum.geometric_polychoron import CyclotomicBraidCompiler

compiler = CyclotomicBraidCompiler()
required = ('F_matrix', 'R_matrix', 'verify_pentagon')
missing = [name for name in required if not hasattr(compiler, name)]
assert not missing, f'F/R/pentagon API absent: {missing}'
