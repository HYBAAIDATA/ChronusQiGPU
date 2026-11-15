"""Check the documented non-negative input domain beyond the stored table."""
from chronus.hw.zeckendorf import fold_to_zeckendorf, unfold
n = 2**128
print('input:', n, flush=True)
actual = unfold(fold_to_zeckendorf(n))
print('round-trip:', actual)
assert actual == n, 'exact round trip failed'
