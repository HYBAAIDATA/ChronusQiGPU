"""Finite Mandelbrot diagnostics used only as experimental ranking advice."""
class MandelbrotResonanceEngine:
    def escape_iterations(self, c, max_iterations=32):
        import math
        if not math.isfinite(c.real) or not math.isfinite(c.imag) or type(max_iterations) is not int or not 1 <= max_iterations <= 1024:
            raise ValueError("finite c and bounded iterations required")
        z = 0j
        for i in range(max_iterations):
            z = z*z+c
            if abs(z) > 2: return i+1
        return max_iterations
    def rank(self, candidates):
        values = list(candidates)
        if not values: return []
        lo, hi = min(values), max(values); width = max(1, hi-lo)
        return sorted(values, key=lambda n: (-self.escape_iterations(complex(-2+3*(n-lo)/width, 0.25)), n))
class FractalQuantumOptimizer(MandelbrotResonanceEngine):
    """Compatibility name for finite diagnostic ranking, not physical cooling."""

def _snap_boundary(self,c,iterations=64,steps=48):
    if type(steps)is not int or not 1<=steps<=128:raise ValueError('bounded boundary refinement required')
    self.escape_iterations(c,iterations)
    if self.escape_iterations(c,iterations)==iterations:raise ValueError('outside endpoint required for boundary bisection')
    inside=0j;outside=complex(c)
    for _ in range(steps):
        midpoint=(inside+outside)/2
        if self.escape_iterations(midpoint,iterations)==iterations:inside=midpoint
        else:outside=midpoint
    return {'boundary_estimate':(inside+outside)/2,'bracket_width':abs(outside-inside),'iterations':iterations,'steps':steps}
MandelbrotResonanceEngine.snap_boundary=_snap_boundary
