"""Bounded multi-level interleaving, not a search of 2**100 executed states."""
class GoldenQuantumInfinityFold:
    def rank(self, candidates, levels=4):
        values = list(candidates)
        if type(levels) is not int or not 1 <= levels <= 16: raise ValueError("bounded fold levels required")
        lanes = min(2**levels, len(values))
        return [v for lane in range(lanes) for v in values[lane::lanes]]
