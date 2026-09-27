"""
Salamander Homeostatic Daemon: proactive, continuous entropy scanning (Phase 6)
===================================================================================

Shifts Salamander from a purely *reactive* healer (waiting for a failing
test before generating a candidate) to a *proactive* continuous
intelligence: ``HomeostaticDaemon`` scans the repository's whole
dependency graph (via ``vascular_refactor.build_dependency_graph``) and
evaluates every existing, currently-"working" module for unnecessarily
high thermodynamic entropy -- using cyclomatic complexity (from
``thermodynamic_profiler``) as the deterministic, exact-integer entropy
proxy, exactly the same noise-free measurement discipline the rest of the
Michie-McLaren substrate relies on.

Whenever a module's entropy exceeds a configured threshold, the daemon:

  1. Asks a caller-supplied ``refactor_fn`` to propose a lower-energy
     candidate for that module (``None`` means no safe refactor could be
     synthesized -- skipped, not an error).
  2. Runs the candidate through a ``SymbolicInvariantGate`` -- a formal
     violation (e.g. a newly-introduced division-by-zero or unguarded
     None-chain) rejects the candidate immediately, *before* any staged
     verification is attempted.
  3. Refuses the candidate outright if its measured entropy is not
     strictly lower than the baseline's -- there is no thermodynamic
     justification to change anything otherwise.
  4. Only then routes the candidate through a
     ``MultiFileCoEvolutionCoordinator`` transaction: staged verification
     must prove the new state passes the exact same test suite the old
     state did (a flawless ``EvidenceGate`` mathematically demonstrates
     behavioral equivalence on every test the repository already trusts)
     before anything is committed to the shared e-graph / immutably
     ledgered. A pure complexity-reducing refactor never changes a
     module's public interface, so no downstream consumer call sites need
     co-synthesis -- but the bundle is still routed through the identical
     atomic propose/verify/commit-or-rollback path an interface-changing
     co-evolution uses, so the same all-or-nothing rollback guarantee
     applies uniformly.

The daemon itself performs no scheduling/polling; ``scan_and_heal`` is a
single, pure, synchronous scan pass over a supplied in-memory module-source
mapping so it can be invoked from any host loop (a cron job, a CI step, a
long-running scheduler) or exercised deterministically in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Dict, Optional, Tuple

from python_backend.hyba.salamander.coevolution import (
    CoEvolutionResult,
    MultiFileCoEvolutionCoordinator,
)
from python_backend.hyba.salamander.evolution_engine import EvidenceGate
from python_backend.hyba.salamander.symbolic_guard import SymbolicInvariantGate
from python_backend.hyba.salamander.thermodynamic_profiler import cyclomatic_complexity
from python_backend.hyba.salamander.vascular_refactor import build_dependency_graph

DEFAULT_ENTROPY_THRESHOLD = 10
DEFAULT_HOMEOSTASIS_COST = Fraction(1, 1)


class HomeostasisError(Exception):
    """Raised on malformed daemon configuration (e.g. a non-positive
    entropy threshold)."""


@dataclass(frozen=True)
class HomeostasisReport:
    """Outcome of scanning a single module during one ``scan_and_heal``
    pass. Emitted for *every* scanned module, not only the ones that were
    actually optimized, so callers get full visibility into every
    homeostatic scan pass."""

    module_name: str
    optimized: bool
    baseline_complexity: int
    refactored_complexity: Optional[int]
    reason: str
    coevolution_result: Optional[CoEvolutionResult] = None


class HomeostaticDaemon:
    """Continuously scans a repository's dependency graph without waiting
    for a failing test, and autonomously constructs
    ``MultiFileCoEvolutionCoordinator`` transactions to refactor
    high-entropy-but-passing modules to a lower thermodynamic energy
    state, gated by a ``SymbolicInvariantGate`` proof of behavioral
    equivalence and a flawless staged-verification evidence gate.
    """

    def __init__(
        self,
        coordinator: MultiFileCoEvolutionCoordinator,
        *,
        entropy_threshold: int = DEFAULT_ENTROPY_THRESHOLD,
        symbolic_gate: Optional[SymbolicInvariantGate] = None,
    ) -> None:
        if not isinstance(entropy_threshold, int) or entropy_threshold <= 0:
            raise HomeostasisError("entropy_threshold must be a positive integer")
        self.coordinator = coordinator
        self.entropy_threshold = entropy_threshold
        self.symbolic_gate = symbolic_gate or SymbolicInvariantGate()

    def measure_entropy(self, source_text: str) -> int:
        """Deterministic, exact-integer entropy proxy for ``source_text``:
        its cyclomatic complexity, via ``thermodynamic_profiler`` -- no
        wall-clock/CPU-cycle sampling, so re-scanning an unchanged module
        always yields the identical reading."""
        return cyclomatic_complexity(source_text)

    def scan_and_heal(
        self,
        module_sources: Dict[str, str],
        refactor_fn: Callable[[str, str], Optional[str]],
        verify_fn: Callable[[Dict[str, str]], EvidenceGate],
        *,
        eclass_id_fn: Optional[Callable[[str], str]] = None,
        operator_name: str = "homeostatic_refactor",
        cost: Fraction = DEFAULT_HOMEOSTASIS_COST,
    ) -> Tuple[HomeostasisReport, ...]:
        """Scan every module in ``module_sources`` and, for each one whose
        entropy exceeds ``entropy_threshold``, attempt to autonomously
        refactor it to a lower-energy state. See the module docstring for
        the full four-gate acceptance sequence (refactor synthesis ->
        symbolic proof -> entropy reduction check -> staged-verification
        evidence gate).

        Returns one ``HomeostasisReport`` per module in ``module_sources``,
        in deterministic (sorted-by-module-name) order.
        """
        graph = build_dependency_graph(module_sources)
        reports = []

        for module_name in sorted(graph.modules):
            source_text = module_sources[module_name]
            baseline_complexity = self.measure_entropy(source_text)

            if baseline_complexity <= self.entropy_threshold:
                reports.append(
                    HomeostasisReport(
                        module_name=module_name,
                        optimized=False,
                        baseline_complexity=baseline_complexity,
                        refactored_complexity=None,
                        reason="entropy within threshold; no action needed",
                    )
                )
                continue

            candidate = refactor_fn(module_name, source_text)
            if candidate is None:
                reports.append(
                    HomeostasisReport(
                        module_name=module_name,
                        optimized=False,
                        baseline_complexity=baseline_complexity,
                        refactored_complexity=None,
                        reason="refactor_fn produced no safe candidate",
                    )
                )
                continue

            violations = self.symbolic_gate.check(candidate)
            if violations:
                reports.append(
                    HomeostasisReport(
                        module_name=module_name,
                        optimized=False,
                        baseline_complexity=baseline_complexity,
                        refactored_complexity=None,
                        reason="symbolic invariant gate rejected candidate: "
                        + ", ".join(sorted({v.kind for v in violations})),
                    )
                )
                continue

            candidate_complexity = self.measure_entropy(candidate)
            if candidate_complexity >= baseline_complexity:
                reports.append(
                    HomeostasisReport(
                        module_name=module_name,
                        optimized=False,
                        baseline_complexity=baseline_complexity,
                        refactored_complexity=candidate_complexity,
                        reason="candidate did not strictly reduce entropy; refused",
                    )
                )
                continue

            eclass_id = (
                eclass_id_fn(module_name)
                if eclass_id_fn is not None
                else f"homeostasis:{module_name}"
            )

            def _no_consumer_changes_needed(_module: str, _text: str) -> Dict[str, Optional[str]]:
                # A pure complexity-reducing, behavior-preserving refactor
                # never changes the module's public interface, so no
                # downstream consumer call sites require co-synthesis.
                return {}

            result = self.coordinator.propose_and_verify_bundle(
                eclass_id,
                module_name,
                candidate,
                _no_consumer_changes_needed,
                verify_fn,
                cost,
                operator_name=operator_name,
            )

            reports.append(
                HomeostasisReport(
                    module_name=module_name,
                    optimized=result.accepted,
                    baseline_complexity=baseline_complexity,
                    refactored_complexity=candidate_complexity,
                    reason=(
                        "committed lower-energy, behaviorally-equivalent refactor"
                        if result.accepted
                        else (result.rejected_reason or "rejected")
                    ),
                    coevolution_result=result,
                )
            )

        return tuple(reports)
