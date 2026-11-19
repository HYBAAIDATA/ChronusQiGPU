"""Exact projective Hadamard coined-cycle walk, ported from the original TURING walk.

A common positive radical sqrt(2**(steps+1)) normalises the numerator
state. The exact Gaussian-rational numerator uses TURING SparseState
and the shift is a basis permutation. No floating-point conversion.
"""
from fractions import Fraction
from turing.exact.geometry.hilbert import ExactComplex, SparseState, TensorHilbert, ZERO


class CoinedCycleWalk:
    def __init__(self, num_positions: int, start: int = 0):
        if type(num_positions) is not int or not 2 <= num_positions <= 1024:
            raise ValueError("cycle requires 2..1024 positions")
        if type(start) is not int or not 0 <= start < num_positions:
            raise ValueError("start outside cycle")
        self.num_positions = num_positions
        self.pos_bits = (num_positions - 1).bit_length()
        self.coin_q = self.pos_bits
        self.n_qubits = self.pos_bits + 1
        self.space = TensorHilbert((2, 1 << self.pos_bits))
        self.scale_squared = 2
        self.register = SparseState(self.space, {
            start: ExactComplex(1), start | (1 << self.coin_q): ExactComplex(0, 1)
        })

    def step(self):
        # Projective H = [[1,1],[1,-1]] / sqrt(2); apply to numerator,
        # then conditionally shift. The two operations are kept separate.
        bit = 1 << self.coin_q
        a = self.register.amplitudes
        positions = {i & (bit - 1) for i in a}
        coin = {}
        for x in positions:
            left, right = a.get(x, ZERO), a.get(x | bit, ZERO)
            coin[x] = left + right
            coin[x | bit] = left - right
        shifted = {}
        for i, z in coin.items():
            if z != ZERO:
                c, x = divmod(i, bit)
                j = (x + (1 if c else -1)) % self.num_positions
                shifted[j | (c * bit)] = z
        self.register = SparseState(self.space, shifted)
        self.scale_squared *= 2
        if self.register.norm2() != self.scale_squared:
            raise ArithmeticError("projective Hadamard walk lost exact norm")

    def position_distribution(self):
        bit = 1 << self.coin_q
        result = {}
        for i, z in self.register.amplitudes.items():
            x = i & (bit - 1)
            result[x] = result.get(x, Fraction(0)) + z.norm2() / self.scale_squared
        return result
