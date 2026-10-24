"""Bounded, deterministic native actions. No eval, shell, injected handlers or expected-output writes."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, localcontext
import hashlib
import json
import math
import os
import platform
import sys
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


_CACHED_ENV_HASH = None


def environment_hash():
    global _CACHED_ENV_HASH
    if _CACHED_ENV_HASH is None:
        _CACHED_ENV_HASH = digest({"python": platform.python_version(), "system": platform.system(),
                                   "machine": platform.machine(), "engine": artifact_hash()})
    return _CACHED_ENV_HASH


def artifact_hash():
    with open(__file__, "rb") as source:
        return hashlib.sha256(source.read()).hexdigest()


def finite_number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def matches(actual, expected, tolerance):
    if finite_number(actual) and finite_number(expected):
        return abs(Decimal(str(actual)) - Decimal(str(expected))) <= Decimal(str(tolerance))
    return type(actual) is type(expected) and actual == expected


def stability(trajectories):
    """Minimum coordinate stability over repeated output trajectories, not timings.

    Compare repeated trials within each seed; use |mu| for signed coordinates.
    Decimal avoids silently downcasting exact integer state to Float32/Float64.
    """
    if len(trajectories) < 2 or not trajectories[0]:
        return 0.0
    if any(len(row) != len(trajectories[0]) for row in trajectories):
        return 0.0
    score = Decimal(1)
    with localcontext() as ctx:
        ctx.prec = max(80, max(len(str(v)) for row in trajectories for v in row) + 40)
        for column in zip(*trajectories):
            values = [Decimal(str(v)) for v in column]
            mean = sum(values) / len(values)
            sigma = (sum((v - mean) ** 2 for v in values) / (len(values) - 1)).sqrt()
            score = min(score, max(Decimal(0), 1 - sigma / (abs(mean) + Decimal('1e-12'))))
    return float(score)


def entropy(actions):
    counts = Counter(actions)
    if not counts:
        raise ValueError("empty entropy stream")
    if len(counts) == 1:
        return 0.0
    total = sum(counts.values())
    return -sum((v / total) * math.log2(v / total) for v in counts.values()) / math.log2(len(counts))


def validate_protocol(protocol):
    steps, required = protocol['steps'], protocol['required_observables']
    if not steps or len(steps) > 10000 or not required or len(set(required)) != len(required):
        raise ValueError("nonempty bounded steps and unique observables required")
    if not all(type(key) is str and key for key in required):
        raise ValueError("observable names required")
    if not finite_number(protocol['statistical_tolerance']) or not 0 < protocol['statistical_tolerance'] <= 1:
        raise ValueError("invalid statistical tolerance")
    if not protocol['seed_suite'] or not all(type(seed) is int for seed in protocol['seed_suite']):
        raise ValueError("explicit integer seed suite required")
    final = steps[-1]
    if type(final) is not dict or final.get('action') != 'assert_observables':
        raise ValueError("final assert_observables step required")
    expected, tolerance = final.get('expected'), final.get('tolerance', 0)
    if type(expected) is not dict or set(expected) != set(required):
        raise ValueError("every required observable needs an explicit expectation")
    if not finite_number(tolerance) or tolerance < 0:
        raise ValueError("finite nonnegative absolute observable tolerance required")
    if not all(finite_number(v) or type(v) is bool for v in expected.values()):
        raise ValueError("numeric or boolean expected observables required")
    canonical(protocol)
    return expected, tolerance


def run_trial(protocol, seed):
    expected, tolerance = validate_protocol(protocol)
    state, trajectory, trace, violations = {}, [], [], []
    start = time.perf_counter_ns()
    for index, step in enumerate(protocol['steps']):
        if type(step) is not dict or set(step) - {'action', 'args', 'expected', 'tolerance'}:
            raise ValueError("invalid action schema")
        action, args = step.get('action'), step.get('args', {})
        if action != 'assert_observables' and set(step) - {'action', 'args'}:
            raise ValueError('assertion fields are only valid in the final assertion')
        if type(args) is not dict:
            raise ValueError("action args must be a dictionary")
        if action == 'init_state':
            if index != 0 or set(args) - {'accumulator', 'previous'}:
                raise ValueError("init_state must be first; unknown initialization input")
            a, b = args.get('accumulator', 1), args.get('previous', 1)
            if type(a) is not int or type(b) is not int or max(abs(a), abs(b)).bit_length() > 4096:
                raise ValueError("bounded exact integer initialization required")
            state = {'accumulator': a, 'previous': b, 'history': [], 'seed': seed}
        elif action == 'lucas_step':
            if not state or args:
                raise ValueError("initialized state and no lucas_step arguments required")
            a, b = state['accumulator'], state['previous']
            state['accumulator'], state['previous'] = a + b, a
            state['history'].append(a + b)
            if (a + b).bit_length() > 16384:
                raise ValueError("host execution integer bound exceeded")
            if state['accumulator'] - state['previous'] != b:
                violations.append('recurrence_identity')
        elif action == 'modular_invariant':
            if not state or set(args) - {'modulus'}:
                raise ValueError("initialized state and known modular inputs required")
            modulus = args.get('modulus', 10007)
            if type(modulus) is not int or not 1 <= modulus <= 2**63 - 1:
                raise ValueError("positive bounded modulus required")
            state['invariant_residue'] = (state['accumulator'] * 31 + 17) % modulus
            if not 0 <= state['invariant_residue'] < modulus:
                violations.append('residue_range')
        elif action == 'assert_observables':
            if index != len(protocol['steps']) - 1 or args:
                raise ValueError("assert_observables must be final")
            for key, value in expected.items():
                if key not in state or not matches(state[key], value, tolerance):
                    violations.append('observable:' + key)
        else:
            raise ValueError('Unknown action: ' + str(action))
        trace.append(action)
        # Numeric output trajectory at every executed step; never inferred from expectations.
        trajectory.extend(state[key] for key in sorted(expected) if key in state and finite_number(state[key]))
    duration = (time.perf_counter_ns() - start) / 1e6
    return {'state': state, 'trajectory': trajectory, 'actions': trace,
            'invariant_violations': violations, 'duration_ms': duration,
            'pid': os.getpid(), 'seed': seed}


def execute_request(request):
    protocol, repetitions = request['protocol'], request['repetitions']
    validate_protocol(protocol)
    if type(repetitions) is not int or not 2 <= repetitions <= 1000:
        raise ValueError("2..1000 repetitions per seed required")
    if len(protocol['seed_suite']) * repetitions * len(protocol['steps']) > 1000000:
        raise ValueError("host action budget exceeded")
    trials = [run_trial(protocol, seed) for seed in protocol['seed_suite'] for _ in range(repetitions)]
    return {'trials': trials, 'artifact_hash': artifact_hash(), 'environment_hash': environment_hash()}


def summarize(protocol, trials, repetitions):
    expected, tolerance = validate_protocol(protocol)
    if len(trials) != repetitions * len(protocol['seed_suite']):
        raise ValueError("incomplete execution window")
    scores, observed = [], []
    for offset, seed in enumerate(protocol['seed_suite']):
        group = trials[offset * repetitions:(offset + 1) * repetitions]
        scores.append(stability([trial['trajectory'] for trial in group]))
        for trial in group:
            if trial['seed'] != seed or trial['actions'] != [s['action'] for s in protocol['steps']]:
                raise ValueError("trial seed/action sequence mismatch")
            if not finite_number(trial['duration_ms']) or trial['duration_ms'] < 0:
                raise ValueError("invalid measured latency")
            observed.append(not trial['invariant_violations'] and all(
                k in trial['state'] and matches(trial['state'][k], v, tolerance) for k, v in expected.items()))
    rate = sum(observed) / len(observed)
    return {'observed': all(observed), 'reproduction_rate': rate, 'stability': min(scores),
            'latency_ms': sum(t['duration_ms'] for t in trials) / len(trials),
            'entropy': entropy([a for t in trials for a in t['actions']]),
            'observed_behaviors': sorted(expected) if all(observed) else []}


if __name__ == '__main__':
    try:
        data = execute_request(json.load(sys.stdin))
        sys.stdout.buffer.write(canonical(data))
    except Exception as exc:
        sys.stderr.write(type(exc).__name__ + ': ' + str(exc))
        sys.exit(1)
