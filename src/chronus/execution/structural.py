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


def zeckendorf_increment(indices: tuple[int, ...]) -> tuple[int, ...]:
    """Increment a canonical Zeckendorf representation by one (add F_2 = 1).

    Pure rewrite-rule stepping with no binary carry chain:
      - adding F_k to an empty slot then folds adjacencies F_j + F_{j+1} -> F_{j+2};
      - landing on an occupied slot uses the doubling identity
        2F_k = F_{k+1} + F_{k-2} (with 2F_2 = F_3 and 2F_3 = F_4 + F_2).
    """
    bits = set(indices)
    worklist = [2]

    def add(k: int) -> None:
        if k not in bits:
            bits.add(k)
        elif k == 2:
            bits.discard(2)
            worklist.append(3)   # 2F_2 = F_3
        elif k == 3:
            bits.discard(3)
            worklist.extend((4, 2))  # 2F_3 = F_4 + F_2
        else:
            bits.discard(k)
            worklist.extend((k + 1, k - 2))  # 2F_k = F_{k+1} + F_{k-2}

    while worklist:
        add(worklist.pop())
        # Fold any adjacency created by the insertion.
        adjacent = [k for k in bits if (k + 1) in bits]
        for k in adjacent:
            bits.discard(k)
            bits.discard(k + 1)
            worklist.append(k + 2)
    return tuple(sorted(bits, reverse=True))


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
