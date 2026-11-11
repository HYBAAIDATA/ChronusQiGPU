"""Hendrix facade over the existing structured-search routines.

This module re-exports, as the identical objects, the public routines of

* ``chronus.math.f257_search``: closed-form F_257 parameter formulas;
* ``chronus.quantum.grover``, ``chronus.quantum.metallic_search``,
  ``chronus.quantum.extension_search`` and ``chronus.quantum.subspace``:
  the legacy finite-field search iterates, plus the ``StateVector`` type
  they operate on (``chronus.quantum.statevector``).

``CATALOG`` maps every exported name to its source module and a one-line
description of what it computes. Nothing is wrapped, renamed or modified.

Classification. The ``chronus.quantum`` routines are legacy finite-field and
algebraic research code (see ``src/chronus/quantum/README.md`` and
``docs/system-update/quantum-package-taxonomy.md``). They are not TURING and
not conventional complex-Hilbert-space quantum mechanics: amplitudes are
elements of F_257, of its quadratic extension F_257[phi], or exact numbers in
Q(sqrt(2)); the finite-field iterates are not unitary; there is no Born rule
and no measurement. Listing them here is a catalogue, not a validation.

Reading the descriptions. n is a routine's ``num_qubits`` argument, N = 2**n
is the vector length and r is the marked count. "One-shot" means closed-form
parameters followed by one algebraic iterate. Every routine that involves
marked items receives the marked index, the marked set or the marked count
as an input; none of them locates an unknown marked item. Where an existing
docstring says that a routine searches or identifies the marked set, its
CATALOG description states what is actually computed. Obtaining the marked
set from a Boolean oracle (``chronus.hendrix.oracles``) takes one query per
input of its domain.
"""

from types import MappingProxyType

from chronus.math.f257_search import f257_phases, f257_phases_multi, mod_inv
from chronus.quantum.extension_search import (
    ExtensionSubspaceState,
    exact_extension_search,
    extension_norm,
    extension_one_shot_phases,
    phi_element_power,
)
from chronus.quantum.grover import diffusion, grover_iterate, grover_trajectory, oracle_flip
from chronus.quantum.metallic_search import (
    METALLIC_COEFFICIENTS,
    QSqrt2,
    SearchResult,
    algebraic_search,
    exact_search,
    exact_search_multi,
    generalized_iterate,
    jform_iterate,
    jform_one_shot_phases,
    one_shot_phases,
    one_shot_phases_multi,
    phase_iterate,
    phase_iterate_multi,
    phase_matched_sweep,
    run_search,
    scaling_sweep,
)
from chronus.quantum.statevector import StateVector
from chronus.quantum.subspace import (
    SubspaceState,
    exact_jform_subspace_search,
    exact_subspace_search,
    jform_subspace_iterate,
    subspace_iterate,
    uniform_subspace,
)

_F257 = "chronus.math.f257_search"
_STATEVECTOR = "chronus.quantum.statevector"
_GROVER = "chronus.quantum.grover"
_METALLIC = "chronus.quantum.metallic_search"
_EXTENSION = "chronus.quantum.extension_search"
_SUBSPACE = "chronus.quantum.subspace"

#: Exported name -> (source module, one-line description of what it computes).
CATALOG = MappingProxyType({
    "mod_inv": (
        _F257,
        "x**(p - 2) mod p, the inverse of a nonzero residue by Fermat's little "
        "theorem (p defaults to 257); ValueError for 0.",
    ),
    "f257_phases": (
        _F257,
        "Closed-form (alpha, mu, beta) in F_257 from a given seed u, size N and "
        "M = 1, in a constant number of field operations; it does not locate an "
        "unknown marked item.",
    ),
    "f257_phases_multi": (
        _F257,
        "Closed-form (alpha, mu, beta) in F_257 from a given seed u, size N and "
        "marked count 1 <= M <= N; a parameter computation that does not locate "
        "marked items.",
    ),
    "StateVector": (
        _STATEVECTOR,
        "Dense vector of 2**n amplitudes in F_257 (1 <= n <= 12) with exact gate "
        "application; there is no Born rule and no measurement.",
    ),
    "oracle_flip": (
        _GROVER,
        "Negates modulo 257, in place, the amplitude at a caller-supplied index "
        "of a StateVector.",
    ),
    "diffusion": (
        _GROVER,
        "Replaces every amplitude a of a StateVector by 2*mean - a over F_257, "
        "in place.",
    ),
    "grover_iterate": (
        _GROVER,
        "oracle_flip at a caller-supplied index followed by diffusion; O(N) field "
        "operations.",
    ),
    "grover_trajectory": (
        _GROVER,
        "Builds the F_257 Hadamard state (every amplitude 30**n mod 257) and "
        "records the amplitude vector after each of a given number of "
        "grover_iterate steps at a caller-supplied index.",
    ),
    "phase_iterate": (
        _METALLIC,
        "One dense iterate: multiplies the amplitude at a caller-supplied index "
        "by alpha, then maps a -> (1 + beta)*mean - beta*a over F_257.",
    ),
    "phase_iterate_multi": (
        _METALLIC,
        "phase_iterate with alpha applied at every index of a caller-supplied "
        "marked set.",
    ),
    "one_shot_phases": (
        _METALLIC,
        "Closed-form (alpha, beta) pairs for which one phase_iterate takes the "
        "F_257 Hadamard state to +/-1 at the chosen index and 0 elsewhere.",
    ),
    "one_shot_phases_multi": (
        _METALLIC,
        "Closed-form (alpha, beta) pairs for one phase_iterate_multi with r "
        "marked indices; they depend only on n and r, not on which indices are "
        "marked.",
    ),
    "exact_search": (
        _METALLIC,
        "Applies one phase_iterate at a caller-supplied index to the F_257 "
        "Hadamard state and checks the result is +/-1 there and 0 elsewhere; "
        "the index is an input, not an output.",
    ),
    "exact_search_multi": (
        _METALLIC,
        "As exact_search for a caller-supplied marked set; recovering the set "
        "from the returned vector means reading all N amplitudes.",
    ),
    "jform_one_shot_phases": (
        _METALLIC,
        "Closed-form (alpha, beta) pairs for the alternative iterate "
        "a -> a + beta*mean (the D = I + beta*J parameterisation).",
    ),
    "jform_iterate": (
        _METALLIC,
        "One dense D = I + beta*J iterate with oracle phase alpha at a "
        "caller-supplied index.",
    ),
    "generalized_iterate": (
        _METALLIC,
        "Negates the amplitude at a caller-supplied index, then maps "
        "a -> c*mean - a over F_257 (c = 2 is the Grover diffusion).",
    ),
    "run_search": (
        _METALLIC,
        "Repeats generalized_iterate with one family's c at a caller-supplied "
        "index until min(a, 257 - a) of that amplitude drops below its running "
        "maximum (at most max_iterations steps); returns a SearchResult.",
    ),
    "scaling_sweep": (
        _METALLIC,
        "run_search for every family in METALLIC_COEFFICIENTS and every n in a "
        "range, with index 2**n - 1 as the marked index.",
    ),
    "algebraic_search": (
        _METALLIC,
        "Tracks the marked and unmarked amplitudes of the c-family iterate "
        "exactly in Q(sqrt(2)) from amplitude 2**(-n/2) until the marked "
        "magnitude stops increasing (at most max_iterations steps); returns the "
        "peak iteration and an integer trace.",
    ),
    "phase_matched_sweep": (
        _METALLIC,
        "Exhaustive scan of all 256 x 256 nonzero (alpha, beta) pairs for the "
        "fewest phase_iterate steps (at most max_iterations) that reach +/-1 at "
        "a given index and 0 elsewhere.",
    ),
    "METALLIC_COEFFICIENTS": (
        _METALLIC,
        "Dictionary from family name to the reflection coefficient c used by "
        "generalized_iterate, run_search and algebraic_search.",
    ),
    "QSqrt2": (
        _METALLIC,
        "Exact number (a + b*sqrt(2)) / 2**e in Q(sqrt(2)) with exact sign "
        "comparison; the amplitude type of algebraic_search.",
    ),
    "SearchResult": (
        _METALLIC,
        "Frozen record returned by run_search: family, c, n, peak iteration, "
        "peak magnitude and the magnitude trajectory.",
    ),
    "phi_element_power": (
        _EXTENSION,
        "phi**s in F_257[phi] = F_257[x]/(x**2 - x - 1) as the pair "
        "(F(s - 1), F(s)) of Fibonacci numbers mod 257.",
    ),
    "extension_norm": (
        _EXTENSION,
        "The norm a**2 + a*b - b**2 mod 257 of a + b*phi in F_257[phi].",
    ),
    "extension_one_shot_phases": (
        _EXTENSION,
        "Closed-form (alpha, beta) in F_257[phi] for which one rank-2 iterate "
        "gives unmarked amplitude 0 and marked amplitude phi**s, from n, r and s.",
    ),
    "exact_extension_search": (
        _EXTENSION,
        "Applies that iterate to the (marked, unmarked) amplitude pair over "
        "F_257[phi] and checks both targets; it uses only the count r and does "
        "not identify which indices are marked.",
    ),
    "ExtensionSubspaceState": (
        _EXTENSION,
        "Frozen rank-2 result of exact_extension_search: F_257[phi] amplitudes "
        "and the norm-parity check.",
    ),
    "SubspaceState": (
        _SUBSPACE,
        "Frozen pair (marked amplitude, unmarked amplitude) in F_257 for r "
        "marked indices among N; no N-element vector is stored.",
    ),
    "uniform_subspace": (
        _SUBSPACE,
        "The F_257 Hadamard state with r marked indices as a SubspaceState "
        "(both amplitudes 30**n mod 257).",
    ),
    "subspace_iterate": (
        _SUBSPACE,
        "phase_iterate restricted to the rank-2 pair: a fixed number of integer "
        "operations per step and no N-element vector.",
    ),
    "jform_subspace_iterate": (
        _SUBSPACE,
        "The D = I + beta*J iterate restricted to the rank-2 pair.",
    ),
    "exact_subspace_search": (
        _SUBSPACE,
        "One subspace_iterate with the closed-form phases for (n, r), checked to "
        "give (+/-1, 0); it uses only the count r and does not identify which "
        "indices are marked.",
    ),
    "exact_jform_subspace_search": (
        _SUBSPACE,
        "As exact_subspace_search for the D = I + beta*J iterate; it does not "
        "identify which indices are marked.",
    ),
})

__all__ = [
    "CATALOG",
    "ExtensionSubspaceState",
    "METALLIC_COEFFICIENTS",
    "QSqrt2",
    "SearchResult",
    "StateVector",
    "SubspaceState",
    "algebraic_search",
    "diffusion",
    "exact_extension_search",
    "exact_jform_subspace_search",
    "exact_search",
    "exact_search_multi",
    "exact_subspace_search",
    "extension_norm",
    "extension_one_shot_phases",
    "f257_phases",
    "f257_phases_multi",
    "generalized_iterate",
    "grover_iterate",
    "grover_trajectory",
    "jform_iterate",
    "jform_one_shot_phases",
    "jform_subspace_iterate",
    "mod_inv",
    "one_shot_phases",
    "one_shot_phases_multi",
    "oracle_flip",
    "phase_iterate",
    "phase_iterate_multi",
    "phase_matched_sweep",
    "phi_element_power",
    "run_search",
    "scaling_sweep",
    "subspace_iterate",
    "uniform_subspace",
]
