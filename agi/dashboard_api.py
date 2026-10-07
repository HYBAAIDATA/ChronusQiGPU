"""
Mass Gap Relaxation Dashboard API
==================================

FastAPI service providing real-time monitoring and control
for the Mass Gap Relaxation Engine.

Endpoints:
- GET /dashboard - Real-time dashboard data
- GET /dashboard/summary - Human-readable summary
- POST /relaxation/trigger - Trigger relaxation
- POST /relaxation/global - Trigger global relaxation
- GET /health - Health check
- GET /metrics - System metrics
- POST /autonomous/start - Start autonomous operation
- POST /autonomous/stop - Stop autonomous operation
"""

import asyncio
import logging
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from hyba_backend.platform.intelligence.bus import IntelligenceBus
from hyba_backend.services.agi.intelligence_bus_integration import (
    AutonomousMassGapOrchestrator,
    MassGapIntelligenceBusAdapter,
)
from hyba_backend.services.agi.mass_gap_relaxation import MassGapRelaxationEngine
from hyba_backend.services.agi.monitoring_dashboard import MassGapDashboard

logger = logging.getLogger(__name__)

# Initialize components
app = FastAPI(
    title="Mass Gap Relaxation Dashboard",
    description="Real-time monitoring and control for Mass Gap Relaxation Engine",
    version="3.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
bus: Optional[IntelligenceBus] = None
engine: Optional[MassGapRelaxationEngine] = None
adapter: Optional[MassGapIntelligenceBusAdapter] = None
orchestrator: Optional[AutonomousMassGapOrchestrator] = None
dashboard: Optional[MassGapDashboard] = None


class RelaxationRequest(BaseModel):
    topic: str
    force_integration: bool = True


class GlobalRelaxationRequest(BaseModel):
    parallel: bool = False


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup."""
    global bus, engine, adapter, orchestrator, dashboard

    logger.info("🚀 Starting Mass Gap Relaxation Dashboard API...")

    # Initialize IntelligenceBus
    bus = IntelligenceBus()
    await bus.start()
    logger.info("✅ IntelligenceBus started")

    # Initialize Mass Gap Engine with auto-tuning
    engine = MassGapRelaxationEngine(enable_auto_tuning=True)
    logger.info("✅ Mass Gap Engine initialized")

    # Connect to IntelligenceBus
    adapter = MassGapIntelligenceBusAdapter(engine, bus)
    logger.info("✅ IntelligenceBus adapter connected")

    # Initialize orchestrator (not started by default)
    orchestrator = AutonomousMassGapOrchestrator(engine, bus)
    logger.info("✅ Autonomous orchestrator initialized")

    # Initialize dashboard
    dashboard = MassGapDashboard(engine, engine.auto_tuner, adapter)
    asyncio.create_task(dashboard.start_monitoring())
    logger.info("✅ Monitoring dashboard started")

    logger.info("🎉 Mass Gap Relaxation Dashboard API ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("🛑 Shutting down Mass Gap Relaxation Dashboard API...")

    if dashboard:
        dashboard.stop_monitoring()

    if orchestrator and orchestrator.is_running:
        orchestrator.stop()

    if bus:
        await bus.stop()

    logger.info("✅ Shutdown complete")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Mass Gap Relaxation Dashboard",
        "version": "3.0.0",
        "status": "operational",
        "endpoints": {
            "dashboard": "/dashboard",
            "summary": "/dashboard/summary",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not engine or not bus or not dashboard:
        raise HTTPException(status_code=503, detail="System not initialized")

    return {
        "status": "healthy",
        "components": {
            "engine": "operational",
            "bus": (
                "connected" if adapter and adapter.get_status()["connected"] else "disconnected"
            ),
            "dashboard": "monitoring" if dashboard.is_monitoring else "stopped",
            "orchestrator": ("running" if orchestrator and orchestrator.is_running else "stopped"),
        },
    }


@app.get("/dashboard")
async def get_dashboard():
    """Get complete dashboard data."""
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not initialized")

    return dashboard.get_dashboard_data()


@app.get("/dashboard/summary", response_class=HTMLResponse)
async def get_dashboard_summary():
    """Get human-readable dashboard summary."""
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not initialized")

    summary = dashboard.get_summary()

    # Convert to HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mass Gap Relaxation Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: 'Courier New', monospace;
                padding: 20px;
            }}
            pre {{
                background-color: #0a0a0a;
                border: 2px solid #00ff00;
                padding: 20px;
                border-radius: 10px;
                font-size: 14px;
                line-height: 1.4;
            }}
            .header {{
                text-align: center;
                color: #00ffff;
                margin-bottom: 20px;
            }}
            .footer {{
                text-align: center;
                color: #888;
                margin-top: 20px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌊 Mass Gap Relaxation Dashboard</h1>
            <p>Real-Time System Monitoring | Auto-refresh: 5s</p>
        </div>
        <pre>{summary}</pre>
        <div class="footer">
            <p>HYBA Software Limited — Mathematical substrate for computational intelligence</p>
            <p>Version 3.0.0 | Status: Production Ready ✅</p>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    if not engine or not dashboard:
        raise HTTPException(status_code=503, detail="System not initialized")

    data = dashboard.get_dashboard_data()

    return {
        "system_status": data["system_status"],
        "topic_health": data["topic_health"],
        "auto_tuning": data.get("auto_tuning_metrics"),
        "intelligence_bus": data.get("intelligence_bus_status"),
    }


@app.post("/relaxation/trigger")
async def trigger_relaxation(request: RelaxationRequest):
    """Trigger relaxation for a specific topic."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    try:
        result = await engine.trigger_relaxation(
            request.topic, force_integration=request.force_integration
        )

        # Publish to IntelligenceBus if adapter available
        if adapter:
            await adapter.publish_relaxation_complete([result])

        return result
    except Exception as e:
        logger.error(f"Relaxation trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/relaxation/global")
async def trigger_global_relaxation(request: GlobalRelaxationRequest):
    """Trigger global relaxation across all topics."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    try:
        results = await engine.run_global_relaxation(parallel=request.parallel)

        # Publish to IntelligenceBus if adapter available
        if adapter:
            await adapter.publish_relaxation_complete(results)

        total_absorbed = sum(r["data_absorbed"] for r in results)
        avg_coherence = sum(r["coherence"] for r in results) / len(results)

        return {
            "status": "success",
            "topics_relaxed": len(results),
            "total_data_absorbed": total_absorbed,
            "average_coherence": avg_coherence,
            "results": results,
        }
    except Exception as e:
        logger.error(f"Global relaxation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/autonomous/start")
async def start_autonomous_operation(background_tasks: BackgroundTasks):
    """Start autonomous orchestration."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    if orchestrator.is_running:
        return {
            "status": "already_running",
            "message": "Autonomous operation already active",
        }

    # Start in background
    background_tasks.add_task(orchestrator.start)

    return {
        "status": "started",
        "message": "Autonomous operation activated",
        "check_interval": orchestrator.check_interval,
        "auto_relax_threshold": orchestrator.auto_relax_threshold,
    }


@app.post("/autonomous/stop")
async def stop_autonomous_operation():
    """Stop autonomous orchestration."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    if not orchestrator.is_running:
        return {
            "status": "already_stopped",
            "message": "Autonomous operation not active",
        }

    orchestrator.stop()

    return {"status": "stopped", "message": "Autonomous operation deactivated"}


@app.get("/topics")
async def get_topics():
    """Get all tracked topics with their current thresholds."""
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    topics = []
    for topic in engine.active_topics:
        threshold = engine.get_topic_threshold(topic)
        topics.append(
            {
                "topic": topic,
                "threshold": threshold,
                "phi_resonant": abs(threshold - 0.618034) < 0.01,
            }
        )

    return {"topics": topics}


@app.get("/recommendations")
async def get_recommendations():
    """Get auto-tuning recommendations."""
    if not engine or not engine.auto_tuner:
        raise HTTPException(status_code=503, detail="Auto-tuner not available")

    recommendations = engine.auto_tuner.get_recommendations()

    return {"count": len(recommendations), "recommendations": recommendations}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
