"""Phi-rotation substrate: (Z[φ], R) and its invariants."""

from phi_rotation.cassini import cassini, cassini_identity
from phi_rotation.functor import F_morphism, kernel_to_invariant
from phi_rotation.korobov import fibonacci_lattice, three_distance_gaps
from phi_rotation.lucas import fibonacci, lucas, lucas_is_trace, lucas_wind
from phi_rotation.morton import morton_step, phi_expansion
from phi_rotation.pisot import PHI, PSI, fibonacci_word, is_pisot_phi
from phi_rotation.ring import ONE, PHI as PHI_RING, PSI as PSI_RING, ZPhi, check_phi1
from phi_rotation.rotation import R, rotate_n
