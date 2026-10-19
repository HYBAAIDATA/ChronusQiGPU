"""Finite-domain exhaustive minimizer, not a continuous-angle VQE solver."""

from fractions import Fraction
from .contracts import Evaluation, OptimizationResult
from .exceptions import ParameterValidationError, CapabilityError


def exact_less(left, right):
    """Compare a+b sqrt(2) by rational arithmetic, including near ties."""
    a = Fraction(left.exact_coefficients[0]) - Fraction(right.exact_coefficients[0])
    b = Fraction(left.exact_coefficients[1]) - Fraction(right.exact_coefficients[1])
    if a == 0:
        return b < 0
    if b == 0 or (a > 0) == (b > 0):
        return a < 0
    # Opposite signs: compare magnitudes without taking an approximate root.
    return (a < 0) if a * a > 2 * b * b else (b < 0)


class FiniteGridOptimizer:
    def minimize(self, evaluate, candidates, *, max_iterations):
        if type(max_iterations) is not int or max_iterations < 1 or not candidates:
            raise ParameterValidationError(
                "positive max_iterations and nonempty candidates required"
            )
        history = []
        for parameters in candidates[:max_iterations]:
            estimate = evaluate(parameters)
            if estimate.shots is not None:
                raise CapabilityError(
                    "exhaustive exact convergence cannot be claimed from noisy shot estimates"
                )
            history.append(Evaluation(parameters, estimate))
        best = history[0]
        for evaluation in history[1:]:
            if exact_less(evaluation.estimate, best.estimate):
                best = evaluation
        complete = len(history) == len(candidates)
        return OptimizationResult(
            best.parameters,
            best.estimate.value,
            complete,
            len(history),
            "finite_domain_exhausted" if complete else "iteration_limit",
            tuple(history),
        )
