"""Deterministic test doubles. Never use as evidence of real domain behavior."""
from copy import deepcopy


class StubNetwork:
    def __init__(self, contracted_result, invariants, ledger):
        self._result = deepcopy(contracted_result)
        self._invariants = deepcopy(invariants)
        self._ledger = deepcopy(ledger)
        self.calls = []

    def contract(self, encoded):
        self.calls.append(deepcopy(encoded))
        return {'result': deepcopy(self._result),
                'invariants': deepcopy(self._invariants),
                'ledger': deepcopy(self._ledger)}


class StubDomain:
    def __init__(self, encoding):
        self._encoding = deepcopy(encoding)
        self.calls = []

    def encode(self, value):
        self.calls.append(deepcopy(value))
        return deepcopy(self._encoding)


class StubInvariants:
    def __init__(self, invariants):
        self._invariants = deepcopy(invariants)
        self.calls = []

    def evaluate(self, result):
        self.calls.append(deepcopy(result))
        return deepcopy(self._invariants)
