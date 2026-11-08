"""Sovereign control plane console: embedded telemetry dashboard."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from chronus.execution import execution_router
from chronus.execution.qigpu import QiGPUOrchestrator
from chronus.execution.reference import NativeMathReferenceBackend
from chronus.service.dependencies import get_current_tenant
from chronus.service.routers.workloads import workload_counts

router = APIRouter(prefix="/console", tags=["console"])

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Chronus Sovereign Control Plane</title>
<style>
 body {{ background:#0b1020; color:#d8e0f0; font-family:monospace; margin:2em; }}
 h1 {{ color:#e8b64c; }} h2 {{ color:#7fa6e8; font-size:1em; }}
 canvas {{ background:#111a30; border:1px solid #2a3a5f; }}
 pre {{ background:#111a30; padding:1em; overflow:auto; }}
</style>
</head>
<body>
<h1>Chronus Sovereign Control Plane</h1>
<h2>QiGPU execution surfaces &mdash; {surface_count} provisioned (default: {default_surface})</h2>
<h2>Phyllotaxis storage &mdash; {record_count} records across {lane_count} golden-ratio lanes</h2>
<canvas id="spiral" width="420" height="420"></canvas>
<canvas id="lanes" width="420" height="160"></canvas>
<h2>Workloads: {total_workloads} total / {active_workloads} active</h2>
<pre id="telemetry"></pre>
<script>
const telemetry = {telemetry};
document.getElementById("telemetry").textContent = JSON.stringify(telemetry, null, 2);
const golden = (3 - Math.sqrt(5)) / 2;
const sc = document.getElementById("spiral").getContext("2d");
sc.fillStyle = "#e8b64c";
for (let n = 0; n < Math.max(telemetry.storage.records, 1); n++) {{
  const r = 8 * Math.sqrt(n), t = 2 * Math.PI * golden * n;
  sc.beginPath();
  sc.arc(210 + r * Math.cos(t), 210 + r * Math.sin(t), 3, 0, 7);
  sc.fill();
}}
const lc = document.getElementById("lanes").getContext("2d");
const hist = telemetry.storage.lane_histogram;
const peak = Math.max(...hist, 1);
lc.fillStyle = "#7fa6e8";
hist.forEach((count, lane) => {{
  lc.fillRect(lane * 13 + 2, 150 - 140 * count / peak, 10, 140 * count / peak);
}});
</script>
</body>
</html>
"""


@router.get(
    "",
    response_class=HTMLResponse,
    summary="Sovereign control plane dashboard",
    description="Renders live QiGPU surfaces, phyllotaxis lane density and workload telemetry.",
)
async def console(
    tenant_id: Optional[str] = Depends(get_current_tenant),
) -> HTMLResponse:
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid authentication token required for the console.",
        )
    inventory = QiGPUOrchestrator(execution_router).inventory()
    storage = NativeMathReferenceBackend._theseus.stats()
    total_workloads, active_workloads = workload_counts()
    telemetry = {
        "tenant_id": tenant_id,
        "qigpu": inventory,
        "storage": storage,
        "workloads": {"total": total_workloads, "active": active_workloads},
    }
    return HTMLResponse(
        _PAGE.format(
            surface_count=len(inventory["surfaces"]),
            default_surface=inventory["default_surface"],
            record_count=storage["records"],
            lane_count=storage["lane_count"],
            total_workloads=total_workloads,
            active_workloads=active_workloads,
            telemetry=json.dumps(telemetry),
        )
    )
