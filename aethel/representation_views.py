"""Zero-copy finite basis views with compositional, adjoint permutations.

The admitted morphisms are basis permutations on fixed-width immutable state
bytes. General lossy feature extraction is not admitted as an equivalence.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BasisPermutation:
    indices: tuple[int, ...]

    def __post_init__(self):
        if not isinstance(self.indices, tuple) or len(self.indices) > 1048576:
            raise ValueError("permutation requires a bounded immutable index tuple")
        if any(type(i) is not int for i in self.indices) or set(self.indices) != set(
            range(len(self.indices))
        ):
            raise ValueError("basis map must be bijective")

    @classmethod
    def identity(cls, size):
        if type(size) is not int or not 0 <= size <= 1048576:
            raise ValueError("basis size exceeds bound")
        return cls(tuple(range(size)))

    def then(self, other):
        if len(self.indices) != len(other.indices):
            raise ValueError("composition requires equal dimensions")
        return BasisPermutation(tuple(self.indices[i] for i in other.indices))

    def adjoint(self):
        inverse = [0] * len(self.indices)
        for i, j in enumerate(self.indices):
            inverse[j] = i
        return BasisPermutation(tuple(inverse))

    def tensor(self, other):
        n = len(other.indices)
        if len(self.indices) * n > 1048576:
            raise MemoryError("tensor basis exceeds admitted size")
        return BasisPermutation(tuple(a * n + b for a in self.indices for b in other.indices))


@dataclass(frozen=True)
class BasisView:
    payload: bytes
    item_bytes: int
    permutation: BasisPermutation

    def __post_init__(self):
        if (
            not isinstance(self.payload, bytes)
            or type(self.item_bytes) is not int
            or self.item_bytes < 1
        ):
            raise TypeError("view requires immutable bytes and positive item width")
        if len(self.payload) != self.item_bytes * len(self.permutation.indices):
            raise ValueError("basis view shape does not match payload")

    def transformed(self, morphism):
        return BasisView(self.payload, self.item_bytes, self.permutation.then(morphism))

    def item(self, index):
        if type(index) is not int or not 0 <= index < len(self.permutation.indices):
            raise IndexError("basis index outside view")
        start = self.permutation.indices[index] * self.item_bytes
        return memoryview(self.payload)[start : start + self.item_bytes]

    @property
    def data_bytes_copied(self):
        return 0
