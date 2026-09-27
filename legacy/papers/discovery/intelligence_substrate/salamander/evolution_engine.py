"""
Salamander Evolution Engine: Michie-McLaren TDD genesis loop
==============================================================

Implements the ``SalamanderEvolutionEngine`` orchestration blueprint: a
failing/blueprint test suite acts as the biological "lesion" that
catalyzes generation of net-new code, gated end-to-end by the
exact-rational Michie policy (``michie_policy.MichiePolicy``) and the
immutable Veritas ledger.

Sequencing guarantees preserved from ``michie_policy``:

  * The survival gate (``scan_patch_for_violations``) runs BEFORE a single
    test is executed. A forbidden mutation never reaches staged
    verification -- it is permanently pinned to zero weight and rejected
    immediately.
  * Staged verification for each generation runs inside a
    ``StagedVerificationSession``; the Michie loop only ever reinforces or
    penalizes a prior once that session has been torn down.
  * A flawless evidence gate reinforces the selected operator's prior by
    an exact-rational ``reward``; a failed-but-clean evidence gate applies
    an exact-rational ``penalty`` (clamped at zero) rather than leaving
    the prior untouched, so repeatedly failing operators are steadily
    deprioritized relative to ones that eventually succeed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Dict, List, Optional, Sequence

from python_backend.hyba.salamander.cellular_agents import CellularSwarmCoordinator, SwarmCandidate
from python_backend.hyba.salamander.deterministic_profiler import (
    ProfileMetrics,
    compute_algorithmic_action_integral,
)
from python_backend.hyba.salamander.egraph import ExactCostEGraph
from python_backend.hyba.salamander.michie_policy import (
    MichiePolicy,
    PolicyState,
    StagedVerificationSession,
    apply_rigidity,
    compute_vcs_age_days,
    context_fingerprint,
    epigenetic_context_fingerprint,
    scan_patch_for_violations,
)

DEFAULT_MAX_GENERATIONS = 8
DEFAULT_REWARD = Fraction(1, 1)
DEFAULT_PENALTY = Fraction(1, 10)


class ExhaustedGenesisError(Exception):
    """Raised when no stable AST/candidate could be synthesized within the
    configured generation budget."""


@dataclass(frozen=True)
class GenesisOperator:
    """A named transformation operator the McLaren loop can select.

    ``synthesize`` receives the ``target_module`` object passed to
    ``execute_tdd_genesis`` and must return candidate source/patch text.
    """

    name: str
    synthesize: Callable[[Any], str]


@dataclass
class EvidenceGate:
    """Outcome of a single staged-verification run against the blueprint
    test suite for one candidate."""

    test_passed: bool
    tests_run: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    failure_hash: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def is_flawless(self) -> bool:
        return self.test_passed is True and self.tests_failed == 0 and self.tests_skipped == 0

    def to_evidence(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "test_passed": self.test_passed,
            "tests_run": self.tests_run,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "failure_hash": self.failure_hash,
        }
        payload.update(self.extra)
        return payload


@dataclass(frozen=True)
class GenesisResult:
    """A synthesized, verified-flawless candidate returned by
    ``execute_tdd_genesis``."""

    candidate: str
    operator_name: str
    generation: int
    fingerprint: str


class SalamanderEvolutionEngine:
    """Orchestrates the McLaren (isolated generation + staged verification)
    and Michie (cross-run exact-rational reinforcement) loops for
    TDD-driven code genesis.
    """

    def __init__(self, policy: MichiePolicy, ledger: Optional[Any] = None):
        self.policy = policy
        self.ledger = ledger if ledger is not None else policy.ledger

    # -- context binding ------------------------------------------------

    @staticmethod
    def hash_canonical_context(context_slice: Dict[str, Any]) -> str:
        """Deterministic SHA-256 fingerprint over a canonicalized
        repository dependency-slice context. Delegates to
        ``michie_policy.context_fingerprint`` so genesis fingerprints and
        policy fingerprints are always computed identically."""
        return context_fingerprint(context_slice)

    # -- operator selection ------------------------------------------------

    def select_operator_by_fractional_weight(
        self, fingerprint: str, operators: Sequence[GenesisOperator]
    ) -> GenesisOperator:
        """Deterministically select the operator with the highest
        exact-rational prior for this context. Ties are broken by
        (ascending) operator name so operator selection is fully
        reproducible across runs and hosts."""
        if not operators:
            raise ValueError("no operators supplied")
        weights = {op.name: self.policy.get_weight(fingerprint, op.name) for op in operators}
        max_weight = max(weights.values())
        tied = sorted(
            (op for op in operators if weights[op.name] == max_weight), key=lambda op: op.name
        )
        return tied[0]

    # -- the McLaren/Michie genesis loop ------------------------------------------------

    def execute_tdd_genesis(
        self,
        operators: Sequence[GenesisOperator],
        context_slice: Dict[str, Any],
        target_module: Any,
        verify_fn: Callable[[str], EvidenceGate],
        *,
        max_generations: int = DEFAULT_MAX_GENERATIONS,
        reward: Fraction = DEFAULT_REWARD,
        penalty: Fraction = DEFAULT_PENALTY,
        age_days: Optional[int] = None,
        target_file_path: Optional[str] = None,
    ) -> GenesisResult:
        """Run the McLaren/Michie TDD genesis loop until a flawless
        candidate is synthesized or ``max_generations`` is exhausted.

        ``verify_fn`` performs staged verification of a candidate (e.g. by
        running the blueprint test suite against it in an isolated
        environment) and MUST return an ``EvidenceGate``. It is invoked
        only AFTER the survival gate has cleared the candidate, and always
        runs inside a ``StagedVerificationSession`` so the Michie-side
        prior update is only ever applied once that environment has been
        torn down.

        ``age_days``, when supplied, activates the epigenetic memory
        layer: the context fingerprint folds in an age-decay marker (see
        ``michie_policy.epigenetic_context_fingerprint``) and the
        ``reward``/``penalty`` magnitudes are dampened by the exact
        ``mutation_rigidity(age_days)`` multiplier via ``apply_rigidity``,
        so long-unmodified code is reinforced/penalized more
        conservatively than actively-developed code, without ever using
        floating-point arithmetic.

        ``target_file_path``, when supplied and ``age_days`` is omitted,
        auto-resolves ``age_days`` via
        ``michie_policy.compute_vcs_age_days`` (git commit timestamp, with
        an ``os.path.getmtime`` fallback), so callers no longer need to
        compute the epigenetic age themselves. Explicit ``age_days``
        always takes precedence over auto-resolution; supplying neither
        preserves the original (genetic-only) fingerprinting behavior
        exactly.
        """
        if age_days is None and target_file_path is not None:
            age_days = compute_vcs_age_days(target_file_path)
        if age_days is None:
            fingerprint = self.hash_canonical_context(context_slice)
        else:
            fingerprint = epigenetic_context_fingerprint(context_slice, age_days)
            reward = apply_rigidity(reward, age_days)
            penalty = apply_rigidity(penalty, age_days)
        generations_attempted: List[str] = []

        for generation in range(1, max_generations + 1):
            selected_op = self.select_operator_by_fractional_weight(fingerprint, operators)
            candidate = selected_op.synthesize(target_module)
            generations_attempted.append(selected_op.name)

            # Survival gate: reject forbidden mutations BEFORE a single
            # test is run. A permanent zero-weight pin is assigned and the
            # candidate never reaches staged verification.
            if scan_patch_for_violations(candidate):
                accepted, _reasons = self.policy.accept_or_reject(
                    context_hash=fingerprint,
                    operator=selected_op.name,
                    patch_text=candidate,
                    evidence={"generation": generation},
                    verification_environment_torn_down=True,
                )
                if accepted:
                    raise RuntimeError(
                        "invariant violated: accept_or_reject accepted a candidate that "
                        "scan_patch_for_violations flagged as a forbidden mutation"
                    )
                continue

            # Staged verification, in absolute isolation. The Michie loop
            # must not observe `session.torn_down is True` until this
            # `with` block has fully exited.
            with StagedVerificationSession() as session:
                gate = verify_fn(candidate)

            accepted, _reasons = self.policy.accept_or_reject(
                context_hash=fingerprint,
                operator=selected_op.name,
                patch_text=candidate,
                evidence=gate.to_evidence(),
                verification_environment_torn_down=session.torn_down,
                reinforcement_increment=reward,
                failure_penalty=(
                    penalty if self.policy.state != PolicyState.POLICY_QUARANTINE else None
                ),
            )
            if accepted:
                return GenesisResult(
                    candidate=candidate,
                    operator_name=selected_op.name,
                    generation=generation,
                    fingerprint=fingerprint,
                )

        raise ExhaustedGenesisError(
            f"Failed to synthesize a stable candidate within {max_generations} generations "
            f"(operators attempted: {generations_attempted})"
        )

    # -- e-graph + cellular-swarm + thermodynamic genesis (additive extension) ------

    def execute_tdd_genesis_thermodynamic(
        self,
        swarm: CellularSwarmCoordinator,
        spec: Any,
        context_slice: Dict[str, Any],
        verify_fn: Callable[[str], EvidenceGate],
        baseline_metrics: ProfileMetrics,
        profile_fn: Callable[[str], ProfileMetrics],
        *,
        max_generations: int = DEFAULT_MAX_GENERATIONS,
        age_days: Optional[int] = None,
        target_file_path: Optional[str] = None,
    ) -> GenesisResult:
        """Elevated McLaren/Michie genesis loop that (a) differentiates
        candidates via a ``CellularSwarmCoordinator`` (Architect ->
        Implementation -> Refactoring pipeline) instead of a single
        monolithic AST mutation, (b) projects every differentiated
        candidate into an ``ExactCostEGraph`` keyed by its *behavioral*
        (test-outcome) signature so structurally-different but
        behaviorally-equivalent candidates collapse into a single
        equivalence class, and (c) rewards the winning operator pairing
        with the exact-rational Algorithmic Action Integral
        (``deterministic_profiler.compute_algorithmic_action_integral``)
        rather than a fixed flat reward, so operators that produce
        provably faster/leaner/no-more-complex code are reinforced more
        strongly than operators that merely pass the tests.

        This method is fully additive: it does not alter the semantics of
        ``execute_tdd_genesis`` and callers that do not need E-Graph
        deduplication or thermodynamic rewards can continue to use the
        original API unchanged.

        ``baseline_metrics`` must be produced by profiling the pre-genesis
        (failing) ``target_module``/blueprint baseline with the same
        ``profile_fn`` used for candidates, so the two are comparable.

        ``target_file_path``, when supplied and ``age_days`` is omitted,
        auto-resolves ``age_days`` via
        ``michie_policy.compute_vcs_age_days`` -- see
        ``execute_tdd_genesis`` for the precedence/fallback rules, which
        are identical here.
        """
        if age_days is None and target_file_path is not None:
            age_days = compute_vcs_age_days(target_file_path)
        if age_days is None:
            fingerprint = self.hash_canonical_context(context_slice)
        else:
            fingerprint = epigenetic_context_fingerprint(context_slice, age_days)

        egraph = ExactCostEGraph()
        generations_attempted: List[str] = []

        for generation in range(1, max_generations + 1):
            candidates: List[SwarmCandidate] = swarm.differentiate(spec)
            signatures_this_generation: List[str] = []

            for swarm_candidate in candidates:
                operator_name = (
                    f"{swarm_candidate.architect_name}+{swarm_candidate.implementation_name}"
                )
                candidate_text = swarm_candidate.text
                generations_attempted.append(operator_name)

                # Survival gate BEFORE a single test runs.
                if scan_patch_for_violations(candidate_text):
                    self.policy.accept_or_reject(
                        context_hash=fingerprint,
                        operator=operator_name,
                        patch_text=candidate_text,
                        evidence={"generation": generation},
                        verification_environment_torn_down=True,
                    )
                    continue

                with StagedVerificationSession() as session:
                    gate = verify_fn(candidate_text)

                if not gate.is_flawless():
                    self.policy.accept_or_reject(
                        context_hash=fingerprint,
                        operator=operator_name,
                        patch_text=candidate_text,
                        evidence=gate.to_evidence(),
                        verification_environment_torn_down=session.torn_down,
                        reinforcement_increment=Fraction(0, 1),
                        failure_penalty=(
                            (
                                apply_rigidity(DEFAULT_PENALTY, age_days)
                                if age_days is not None
                                else DEFAULT_PENALTY
                            )
                            if self.policy.state != PolicyState.POLICY_QUARANTINE
                            else None
                        ),
                    )
                    continue

                # Flawless: compute the exact-rational thermodynamic
                # reward AFTER teardown, then admit into the e-graph keyed
                # by behavioral signature so equivalent-but-differently
                # -shaped survivors collapse together.
                mutant_metrics = profile_fn(candidate_text)
                reward = compute_algorithmic_action_integral(baseline_metrics, mutant_metrics)
                if age_days is not None:
                    reward = apply_rigidity(reward, age_days)
                if reward <= 0:
                    # compute_algorithmic_action_integral only ever
                    # combines strictly-positive ratios, and
                    # mutation_rigidity is bounded strictly below 1, so a
                    # non-positive reward here indicates a profiling
                    # anomaly rather than a legitimate outcome -- fail
                    # loudly instead of admitting an arbitrarily-costed
                    # candidate into the e-graph.
                    raise RuntimeError(
                        f"non-positive thermodynamic reward ({reward!r}) computed for operator "
                        f"{operator_name!r}; refusing to admit into the e-graph"
                    )

                behavioral_signature = ExactCostEGraph.behavioral_signature(gate.to_evidence())
                egraph.add_candidate(
                    behavioral_signature,
                    operator_name,
                    candidate_text,
                    cost=Fraction(1, 1) / reward,
                )
                if behavioral_signature not in signatures_this_generation:
                    signatures_this_generation.append(behavioral_signature)

                self.policy.accept_or_reject(
                    context_hash=fingerprint,
                    operator=operator_name,
                    patch_text=candidate_text,
                    evidence=gate.to_evidence(),
                    verification_environment_torn_down=session.torn_down,
                    reinforcement_increment=reward,
                    failure_penalty=None,
                )

            # Collapse the e-graph: among every flawless candidate admitted
            # this generation, deterministically extract the single lowest
            # -cost (i.e. highest thermodynamic-reward) survivor per
            # behavioral-equivalence class, then pick the best across
            # classes -- never simply the first candidate that happened to
            # pass.
            best_node = None
            for signature in signatures_this_generation:
                candidate_node = egraph.extract_best(signature)
                if best_node is None or candidate_node.cost < best_node.cost:
                    best_node = candidate_node

            if best_node is not None:
                return GenesisResult(
                    candidate=best_node.text,
                    operator_name=best_node.operator_name,
                    generation=generation,
                    fingerprint=fingerprint,
                )

        raise ExhaustedGenesisError(
            f"Failed to synthesize a stable candidate within {max_generations} generations "
            f"(operators attempted: {generations_attempted})"
        )
