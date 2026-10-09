"""Domain / semantic adapters — the only domain-specific layer of TOE.

An adapter translates its world into the domain-neutral
:class:`toe.problem.Problem` (``to_problem``) and maps an episode back into
its own vocabulary (``interpret``). It never reasons: no adapter fits a
model, evaluates a future, scores an action or chooses one. The reasoning
core (:class:`toe.machine.TOEMachine`) never imports this package, and the
machine's ``trace`` lists every backend callable a run executed — so a
domain change can be shown to change only the adapter.

Layers::

    TOE CORE            toe.machine + the reasoning modules it composes
    DOMAIN ADAPTERS     toe.adapters.{tabular, causal_system, graph,
                        temporal, code, scientific}
    LEGACY HR ADAPTER   toe.adapters.legacy_hr (the discovery surface)
    PYTHIA ADAPTER      lives with PYTHIA, outside this package: the
                        workload's semantics never enter the TOE distribution
    ENTERPRISE          toe.unified (analytics platform over the same backend)
"""

from .base import ProblemAdapter, OptionalDependencyUnavailable
from .causal_system import CausalSystemAdapter
from .code import CodeStructureAdapter
from .graph import GraphAdapter
from .legacy_hr import LegacyHRAdapter
from .scientific import RecurrenceAdapter, LinearSystemAdapter
from .tabular import TabularAdapter
from .temporal import TimeSeriesAdapter

__all__ = [
    "CausalSystemAdapter",
    "CodeStructureAdapter",
    "GraphAdapter",
    "LegacyHRAdapter",
    "LinearSystemAdapter",
    "OptionalDependencyUnavailable",
    "ProblemAdapter",
    "RecurrenceAdapter",
    "TabularAdapter",
    "TimeSeriesAdapter",
]
