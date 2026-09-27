import math

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI: float = PHI - 1.0


class PhiStructureAnalyzer:
    """Quantify phi-structure in a set of integers. s in [0,1]; >= INV_PHI
    (~0.618) selects the structured phi-Grover lane (solve), else flat."""

    def __init__(self) -> None:
        self.phi = PHI
        self.inv_phi = INV_PHI
        self.phi15 = PHI**15

    def _uniformity_bias(self, values):
        vals = sorted(float(v) % 1.0 for v in values)
        n = len(vals)
        if n == 0:
            return 0.0
        dev = 0.0
        for i, v in enumerate(vals):
            dev += abs(v - (i + 0.5) / n)
        return min(1.0, dev / (n * 0.5))

    def compute_structure_parameter(self, problem_instance, search_space=None) -> float:
        values = [int(v) for v in problem_instance]
        if len(values) < 2:
            return 0.0
        weyl = [(v * self.phi) % 1.0 for v in values]
        weyl_dev = self._uniformity_bias(weyl)
        pisot = [(v / self.phi15) % 1.0 for v in values]
        pisot_dev = self._uniformity_bias(pisot)
        srt = sorted(values)
        steps = [(srt[i + 1] - srt[i]) % (2**32) for i in range(len(srt) - 1)]
        step_frac = [(st * self.inv_phi) % 1.0 for st in steps] if steps else [0.0]
        step_dev = self._uniformity_bias(step_frac)
        return min(1.0, (weyl_dev * 0.4 + pisot_dev * 0.35 + step_dev * 0.25) * 2.2)


def phi_structure_strength(values):
    return PhiStructureAnalyzer().compute_structure_parameter(values)
