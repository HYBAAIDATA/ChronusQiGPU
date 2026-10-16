"""
M_φ fold — exact integer invertible transform on pairs of integers.

The Q-matrix Q = [[1, 1], [1, 0]] has determinant -1, making it an
exact integer invertible transform. Applied to pairs (x, y):

    fold:   (x, y) → (x + y, x)
    unfold: (u, v) → (v, u - v)

This is lossless — unfold(fold(x, y)) = (x, y) for all integers.

Applied to arrays of even length, this transforms pairs independently.
Odd-length arrays pass the final element through unchanged.
"""

from typing import List


def fold_pair(x: int, y: int) -> tuple[int, int]:
    """Apply M_φ fold to a single pair: (x, y) → (x + y, x).

    This is the transform [[1,1],[1,0]] · [x, y]^T = [x+y, x]^T.
    """
    return (x + y, x)


def unfold_pair(u: int, v: int) -> tuple[int, int]:
    """Inverse M_φ fold: (u, v) → (v, u - v).

    Recovers (x, y) from (x+y, x): x = v, y = u - v.
    """
    return (v, u - v)


def fold_array(data: List[int]) -> List[int]:
    """Apply M_φ fold to an array of integers.

    Pairs are transformed independently: [x0,y0,x1,y1,...] →
    [x0+y0, x0, x1+y1, x1, ...].

    Odd-length arrays pass the final element through unchanged.
    """
    result = []
    for i in range(0, len(data) - 1, 2):
        u, v = fold_pair(data[i], data[i + 1])
        result.append(u)
        result.append(v)
    if len(data) % 2 == 1:
        result.append(data[-1])
    return result


def unfold_array(data: List[int]) -> List[int]:
    """Inverse M_φ fold on an array.

    Pairs are inverted independently: [u0,v0,u1,v1,...] →
    [v0, u0-v0, v1, u1-v1, ...].

    Odd-length arrays pass the final element through unchanged.
    """
    result = []
    for i in range(0, len(data) - 1, 2):
        x, y = unfold_pair(data[i], data[i + 1])
        result.append(x)
        result.append(y)
    if len(data) % 2 == 1:
        result.append(data[-1])
    return result


def fold_roundtrip(data: List[int]) -> bool:
    """Verify that unfold_array(fold_array(data)) == data."""
    folded = fold_array(data)
    unfolded = unfold_array(folded)
    return unfolded == data
