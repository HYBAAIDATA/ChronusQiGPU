"""Constant registry / simulation parameters; cannot mutate physical constants."""
import math
class CosmicRegistry:
    def __init__(self):
        self.constants = {"c": 299792458.0, "h": 6.62607015e-34, "G": 6.67430e-11, "alpha": 1/137.035999084}
    def snapshot(self): return dict(self.constants)
class OmniscienceKernel:
    def __init__(self): self.registry = CosmicRegistry()
    def parameterize(self, **overrides):
        out = self.registry.snapshot()
        for name, value in overrides.items():
            if name not in out or not math.isfinite(value) or value <= 0: raise ValueError("unknown or nonpositive simulation parameter")
            out[name] = float(value)
        return {"parameters": out, "truth_class": "parameterized_simulation", "physical_constants_mutated": False}

    def evolve(self,amplitudes,hamiltonian,time=1.0,**overrides):
        from .quantum_state import MathematicalQuantumState,HamiltonianEngine
        parameters=self.parameterize(**overrides)['parameters']
        reference=self.registry.snapshot()
        # Constant-normalised computational units: changing h changes time scaling.
        scaled_time=time*reference['h']/parameters['h']
        result=HamiltonianEngine().evolve(MathematicalQuantumState(amplitudes),hamiltonian,scaled_time)
        return {'state':result,'parameters':parameters,'time_scale':reference['h']/parameters['h']}
