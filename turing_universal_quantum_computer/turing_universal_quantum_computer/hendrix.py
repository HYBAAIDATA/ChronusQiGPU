"""Hendrix iGPU structured-search facade with Lucas/Pisot scheduling."""
from .pisot import HendrixSchedule, HendrixStructuredSearch


class HendrixChronusSearch(HendrixStructuredSearch):
    """Explicitly classical/iGPU schedule; consensus remains external."""

    execution_plane = "iGPU_classical_structured_search"
    # Receipts carry the declared execution plane as the execution mode.
    execution_mode = "iGPU_classical_structured_search"

    def schedule(self, nonce_count: int) -> HendrixSchedule:
        return self.plan(nonce_count)


__all__ = ["HendrixSchedule", "HendrixStructuredSearch", "HendrixChronusSearch"]
