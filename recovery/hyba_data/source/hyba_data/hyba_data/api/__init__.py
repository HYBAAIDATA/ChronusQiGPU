"""
HYBA_DATA API Layer — McKinsey-grade REST API with telemetry.

Provides programmatic access to the quantum-geometric optimization framework
with full observability, health checks, and metrics.

Usage:
    from hyba_data.api import create_app
    app = create_app()
    # Run with: uvicorn hyba_data.api.app:app --host 0.0.0.0 --port 8080
"""
from .app import create_app
from .telemetry import TelemetryCollector, MetricType

__all__ = ["create_app", "TelemetryCollector", "MetricType"]
