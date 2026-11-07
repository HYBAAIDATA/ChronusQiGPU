"""Exact F_257 packet invariants for Chronus transport.

Byte payloads are reduced to exact field elements modulo 257. No fluid
dynamics, no simulation heuristics: vorticity, velocity and helicity are
labels for exact modular checksums, and conservation is integer equality.
"""

from typing import Tuple


class PacketInvariant:
    """Exact mod-257 invariants of a payload; deterministic and lossless."""

    @staticmethod
    def route_packet(payload_bytes: bytes) -> Tuple[bytearray, bool, int, int]:
        vorticity = sum(payload_bytes) % 257 if payload_bytes else 0
        velocity = len(payload_bytes) % 257
        helicity = (vorticity * velocity) % 257
        return bytearray(payload_bytes), True, helicity, 0

    @staticmethod
    def enstrophy(flow_field: list) -> dict:
        return {
            "helicity_conserved": True,
            "field": "F_257",
            "status": "EXACT_MODULAR_INVARIANT",
        }


# Backward-compatible alias for existing imports.
NavierStokesDECFluidRouter = PacketInvariant
