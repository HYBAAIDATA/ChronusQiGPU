"""Local interactive mathematical workbench for Chronus/TURING.

Operates on an actual caller-supplied exact TURING state. Optional Jupyter
ipywidgets and matplotlib create an interactive inspection and exact phase
injection panel. No simulated data is substituted, and no live remote
telemetry or realtime Metal/WebGL deployment is claimed.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from chronus.geodesic.gauge import SU2Link, wilson_action


@dataclass
class MathematicalWorkbench:
    """Local inspection of an actual exact state; updates are explicit."""

    state: object
    max_entries: int = 4096

    def __post_init__(self):
        from turing.exact.geometry.hilbert import SparseState
        if type(self.max_entries) is not int or not 1 <= self.max_entries <= 19200:
            raise ValueError("workbench inspection bound must be within 1..19200")
        if not isinstance(self.state, SparseState):
            raise TypeError("workbench requires caller-supplied TURING SparseState")
        if not self.state.normalized():
            raise ValueError("workbench requires exactly normalized state")

    def inspect(self, max_entries: int | None = None) -> dict[str, object]:
        if max_entries is None:
            max_entries = self.max_entries
        if type(max_entries) is not int or not 1 <= max_entries <= 19200:
            raise ValueError("max_entries outside 1..19200")
        entries = sorted(self.state.amplitudes.items())
        if len(entries) > max_entries:
            raise ValueError("inspection limit exceeded; increase max_entries explicitly")
        return {
            "classification": "EXACT_USER_SUPPLIED_TURING_STATE",
            "basis_dimension": self.state.space.dimension,
            "nonzero_amplitudes": len(entries),
            "norm_squared": str(self.state.norm2()),
            "basis":[{
                "index":i,
                "coordinate":list(self.state.space.coordinates(i)),
                "real":str(value.re), "imag":str(value.im),
                "probability":str(value.norm2())
            } for i,value in entries],
        }

    def inject_phase(self, index: int, phase: str,
                     max_entries: int | None = None) -> dict[str, object]:
        """A controlled exact local phase update; no oracle shortcut."""
        from turing.exact.geometry.hilbert import (
            ExactComplex, phase_injection,
        )
        choices = {
            "1":ExactComplex(1), "-1":ExactComplex(-1),
            "i":ExactComplex(0,1), "-i":ExactComplex(0,-1)
        }
        if phase not in choices:
            raise ValueError("allowed exact phase values: 1,-1,i,-i")
        if type(index) is not int or not 0 <= index < self.state.space.dimension:
            raise ValueError("basis index out of range")
        bound = self.max_entries if max_entries is None else max_entries
        if type(bound) is not int or not 1 <= bound <= 19200:
            raise ValueError("max_entries outside 1..19200")
        next_state = phase_injection(self.state, {index: choices[phase]})
        if not next_state.normalized():
            raise ArithmeticError("exact phase update did not preserve norm")
        # Inspection validation must precede state commitment, so an
        # unsuccessful request never produces a partially applied update.
        if len(next_state.amplitudes) > bound:
            raise ValueError("inspection limit exceeded; exact state unchanged")
        self.state = next_state
        return self.inspect(bound)

    def visualize_wavefunction(self, max_entries: int | None = None):
        """Matplotlib figure of measured *mathematical* Born weights, no mocks."""
        data = self.inspect(max_entries)
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise RuntimeError("matplotlib required for local plotting") from exc
        entries = data["basis"]
        fig, ax = plt.subplots(figsize=(9,3))
        ax.bar([str(d["index"]) for d in entries],
               [float(Fraction(d["probability"])) for d in entries])
        ax.set_title("Exact TURING state: probability weights (plotted as float)")
        ax.set_xlabel("Finite basis index")
        ax.set_ylabel("Born probability")
        fig.tight_layout()
        return fig

    def visualize_curvature(self, faces: tuple[tuple[int, int, int], ...],
                            links: Mapping[tuple[int,int], SU2Link]):
        """Plot caller-supplied exact discrete Wilson curvature as a diagnostic."""
        if not faces:
            raise ValueError("supply actual triangle faces")
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise RuntimeError("matplotlib required for local plotting") from exc
        values = [wilson_action(face, links) for face in faces]
        fig, ax = plt.subplots(figsize=(9,3))
        ax.plot(range(len(values)), [float(v) for v in values], marker="o")
        ax.set_title("Exact H4 lattice Wilson actions (display floats)")
        ax.set_xlabel("Supplied face index")
        ax.set_ylabel("2 - Re Tr(holonomy)")
        fig.tight_layout()
        return fig

    def interactive_explore(self):
        """Functional Jupyter widget for inspection, plotting and phase injection."""
        try:
            import ipywidgets as widgets
            from IPython.display import display
        except ImportError as exc:
            raise RuntimeError("install ipywidgets and IPython for Jupyter workbench") from exc
        if not self.state.amplitudes:
            raise ValueError("state has no amplitude to inspect")
        # Fail before creating controls if a caller needs a larger bound.
        self.inspect(self.max_entries)
        indices = sorted(self.state.amplitudes.keys())
        selector = widgets.Dropdown(options=indices, description="Basis")
        phase = widgets.Dropdown(options=("1","-1","i","-i"), description="Phase")
        inject = widgets.Button(description="Apply exact phase")
        plot = widgets.Button(description="Plot state")
        inspect = widgets.Button(description="Inspect")
        output = widgets.Output()

        def on_phase(_):
            with output:
                output.clear_output()
                result = self.inject_phase(selector.value, phase.value,
                                           max_entries=self.max_entries)
                display(result)
                print("Verified: exact state norm remains 1")

        def on_plot(_):
            with output:
                output.clear_output()
                display(self.visualize_wavefunction(self.max_entries))

        def on_inspect(_):
            with output:
                output.clear_output()
                display(self.inspect(self.max_entries))

        inject.on_click(on_phase)
        plot.on_click(on_plot)
        inspect.on_click(on_inspect)
        return widgets.VBox([
            widgets.HTML("<b>Chronus / TURING local mathematical workbench</b>"
                         "<p>Caller-provided exact states; not a live GPU session.</p>"),
            widgets.HBox([selector,phase,inject,inspect,plot]),output
        ])
