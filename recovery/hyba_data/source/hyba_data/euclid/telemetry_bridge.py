"""Host Telemetry Bridge — physical-to-logical degradation mapping. 19 July 2026."""
import time
from typing import Dict, Tuple

class HostTelemetryBridge:
    def __init__(self, cns_endpoint="http://localhost:9090", node_id="host_local", poll_interval=1.0):
        self.cns_endpoint = cns_endpoint; self.node_id = node_id; self.poll_interval = poll_interval
        self.mem_critical = 90.0; self.temp_critical = 85.0
        self._sim_mem = 45.0; self._sim_temp = 60.0

    def set_simulated_metrics(self, mem_pct: float, temp_c: float):
        self._sim_mem = mem_pct; self._sim_temp = temp_c

    def query_host_metrics(self) -> Tuple[float, float]:
        return (self._sim_mem, self._sim_temp)

    def evaluate_hardware_health(self, mem_pct: float, temp_c: float) -> str:
        if mem_pct >= self.mem_critical: return "DEGRADED"
        if temp_c >= self.temp_critical: return "DEGRADED"
        return "HEALTHY"

    def sample_once(self) -> Dict:
        m, t = self.query_host_metrics()
        s = self.evaluate_hardware_health(m, t)
        return {"node_id": self.node_id, "hardware_status": s, "metrics": {"mem_pct": m, "temp_c": t}, "timestamp": time.time()}
