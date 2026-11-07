"""Exact integer representations and reversible byte transformations."""


def zeckendorf_encode(value: int) -> tuple[int, ...]:
    """Return canonical Fibonacci indices in descending order."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("value must be a non-negative integer")
    if value == 0:
        return ()
    fibs = [1, 2]
    while fibs[-1] <= value:
        fibs.append(fibs[-1] + fibs[-2])
    indices = []
    for position in range(len(fibs) - 1, -1, -1):
        if fibs[position] <= value:
            indices.append(position + 2)
            value -= fibs[position]
    return tuple(indices)


def zeckendorf_decode(indices: tuple[int, ...]) -> int:
    if any(not isinstance(index, int) or isinstance(index, bool) or index < 2 for index in indices):
        raise ValueError("indices must be integers >= 2")
    if any(left - right < 2 for left, right in zip(indices, indices[1:])):
        raise ValueError("indices must be descending, distinct and non-adjacent")
    if not indices:
        return 0
    fibs = [1, 2]
    while len(fibs) <= indices[0] - 2:
        fibs.append(fibs[-1] + fibs[-2])
    return sum(fibs[index - 2] for index in indices)


def fold_pair(first: int, second: int) -> tuple[int, int]:
    """Apply the M15 byte map in Z/256Z; this is not authentication."""
    if any(not isinstance(x, int) or isinstance(x, bool) or not 0 <= x < 256 for x in (first, second)):
        raise ValueError("inputs must be bytes")
    return ((219 * first + 98 * second) % 256, (98 * first + 121 * second) % 256)


def unfold_pair(first: int, second: int) -> tuple[int, int]:
    """Apply the inverse of M15 in Z/256Z."""
    if any(not isinstance(x, int) or isinstance(x, bool) or not 0 <= x < 256 for x in (first, second)):
        raise ValueError("inputs must be bytes")
    return ((135 * first + 98 * second) % 256, (98 * first + 37 * second) % 256)
