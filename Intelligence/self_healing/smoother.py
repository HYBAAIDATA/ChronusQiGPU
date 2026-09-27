"""
SALAMANDER SUBSTRATE: HARDWARE THERMAL & PFC NETWORK SMOOTHER
Smooths transient PFC network pauses and modulates stream execution under thermal load.
"""

from collections import deque
import logging
import typing

logger = logging.getLogger("hyba.salamander.smoother")


class SalamanderHardwareSmoother:

    def __init__(self, target_gpus: int = 8):
        self.pfc_frame_buffer = deque(maxlen=2048)
        self.gpu_thermal_caps = [85.0] * target_gpus  # 85°C thermal threshold limit

    def ingest_pfc_pause_event(self, pfc_event_data: dict) -> bool:
        """Intercepts RoCEv2 PFC pause frame bursts and buffers incoming packets to prevent frame drops."""
        pause_count = pfc_event_data.get("pause_frame_count", 0)

        if pause_count > 50:  # High congestion signal
            # Buffer packet headers in sidecar memory during transient network stall
            self.pfc_frame_buffer.append(pfc_event_data)
            return True  # Signal that frame was safely buffered
        return False

    async def monitor_and_smooth_thermals(
        self, gpu_temperatures: typing.List[float]
    ) -> typing.List[float]:
        """Calculates required micro-delay insertion to smooth GPU thermal spikes without failing tasks."""
        stream_delays = [0.0] * len(gpu_temperatures)

        for gpu_idx, temp in enumerate(gpu_temperatures):
            if temp >= self.gpu_thermal_caps[gpu_idx]:
                # Calculate proportional micro-delay adjustment in milliseconds
                overflow = temp - self.gpu_thermal_caps[gpu_idx]
                stream_delays[gpu_idx] = min(15.0, overflow * 2.5)  # Cap max micro-delay at 15ms

                logger.warning(
                    f"[SalamanderSmoother] GPU {gpu_idx} temp ({temp}°C) exceeds cap. "
                    f"Inserting {stream_delays[gpu_idx]}ms micro-yield to maintain thermal stability."
                )

        return stream_delays
