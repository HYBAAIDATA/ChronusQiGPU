"""Hendrix iGPU structured-search facade with Lucas/Pisot scheduling."""
from .lucas_pisot import HendrixSchedule, HendrixStructuredSearch


class HendrixIGPUSearch(HendrixStructuredSearch):
    """Explicitly classical/iGPU schedule; consensus remains external."""

    execution_plane = "iGPU_classical_structured_search"

    def schedule(self, nonce_count: int) -> HendrixSchedule:
        return self.plan(nonce_count)


__all__ = ["HendrixSchedule", "HendrixStructuredSearch", "HendrixIGPUSearch"]
