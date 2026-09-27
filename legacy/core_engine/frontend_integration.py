# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude
"""
HYBA Analytics - Frontend Integration
====================================

This module implements frontend integration with:
- Unified dashboard
- Quantum telemetry visualizations
- Domain intelligence panels
- Consciousness evolution graph
- Substrate coherence map
- Multi-agent activity map
- Regulatory solver UI
- Forecasting studio
- Decision intelligence studio

The frontend integration provides a modern, intuitive interface for all HYBA capabilities.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
from collections import defaultdict, deque

import numpy as np

from core_engine.unified_platform_engine import ConfigurationManager, EnterpriseLogger


class DashboardWidgetType(Enum):
    """Types of dashboard widgets"""

    METRIC_CARD = "metric_card"
    CHART = "chart"
    GRAPH = "graph"
    TABLE = "table"
    QUANTUM_VISUALIZATION = "quantum_visualization"
    AGENT_ACTIVITY = "agent_activity"
    CONSCIOUSNESS_EVOLUTION = "consciousness_evolution"
    DOMAIN_INTELLIGENCE = "domain_intelligence"


class VisualizationType(Enum):
    """Types of visualizations"""

    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    SCATTER_PLOT = "scatter_plot"
    HEATMAP = "heatmap"
    QUANTUM_CIRCUIT = "quantum_circuit"
    QUANTUM_STATE = "quantum_state"
    NETWORK_GRAPH = "network_graph"
    TIMELINE = "timeline"
    GAUGE = "gauge"


@dataclass
class DashboardWidget:
    """Dashboard widget definition"""

    widget_id: str
    widget_type: DashboardWidgetType
    title: str
    position: Dict[str, int]  # {x, y, width, height}
    data_source: str
    visualization_type: Optional[VisualizationType] = None
    refresh_interval: int = 5  # seconds
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type.value,
            "title": self.title,
            "position": self.position,
            "data_source": self.data_source,
            "visualization_type": (
                self.visualization_type.value if self.visualization_type else None
            ),
            "refresh_interval": self.refresh_interval,
            "config": self.config,
        }


@dataclass
class VisualizationData:
    """Data for visualizations"""

    visualization_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visualization_id": self.visualization_id,
            "data": self.data,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class UnifiedDashboard:
    """
    Unified Dashboard for HYBA Analytics.

    Provides:
    - Metric cards
    - Charts and graphs
    - Quantum visualizations
    - Agent activity monitoring
    - Consciousness evolution tracking
    - Domain intelligence panels
    """

    def __init__(self, config: ConfigurationManager, logger: EnterpriseLogger):
        self.config = config
        self.logger = logger

        self._widgets: Dict[str, DashboardWidget] = {}
        self._widget_data: Dict[str, VisualizationData] = {}
        self._layouts: Dict[str, List[str]] = {}

        self._lock = threading.Lock()

        # Initialize dashboard
        self._initialize_dashboard()

        self.logger.set_context(component="UnifiedDashboard")
        self.logger.info("Unified Dashboard initialized")

    def _initialize_dashboard(self):
        """Initialize dashboard with default widgets"""
        # Main dashboard layout
        self._create_main_dashboard()

        # Quantum dashboard layout
        self._create_quantum_dashboard()

        # Agent dashboard layout
        self._create_agent_dashboard()

        # Domain dashboard layout
        self._create_domain_dashboard()

    def _create_main_dashboard(self):
        """Create main dashboard layout"""
        widgets = [
            DashboardWidget(
                widget_id="system_health",
                widget_type=DashboardWidgetType.METRIC_CARD,
                title="System Health",
                position={"x": 0, "y": 0, "width": 3, "height": 2},
                data_source="system_health",
                visualization_type=VisualizationType.GAUGE,
            ),
            DashboardWidget(
                widget_id="total_requests",
                widget_type=DashboardWidgetType.METRIC_CARD,
                title="Total Requests",
                position={"x": 3, "y": 0, "width": 3, "height": 2},
                data_source="request_metrics",
            ),
            DashboardWidget(
                widget_id="consciousness_level",
                widget_type=DashboardWidgetType.METRIC_CARD,
                title="Consciousness Level",
                position={"x": 6, "y": 0, "width": 3, "height": 2},
                data_source="consciousness_metrics",
            ),
            DashboardWidget(
                widget_id="request_timeline",
                widget_type=DashboardWidgetType.CHART,
                title="Request Timeline",
                position={"x": 0, "y": 2, "width": 6, "height": 4},
                data_source="request_timeline",
                visualization_type=VisualizationType.LINE_CHART,
            ),
            DashboardWidget(
                widget_id="domain_distribution",
                widget_type=DashboardWidgetType.CHART,
                title="Domain Distribution",
                position={"x": 6, "y": 2, "width": 3, "height": 4},
                data_source="domain_distribution",
                visualization_type=VisualizationType.PIE_CHART,
            ),
        ]

        for widget in widgets:
            self._register_widget(widget)

        self._layouts["main"] = [w.widget_id for w in widgets]

    def _create_quantum_dashboard(self):
        """Create quantum-specific dashboard"""
        widgets = [
            DashboardWidget(
                widget_id="quantum_coherence",
                widget_type=DashboardWidgetType.QUANTUM_VISUALIZATION,
                title="Quantum Coherence",
                position={"x": 0, "y": 0, "width": 6, "height": 4},
                data_source="quantum_coherence",
                visualization_type=VisualizationType.QUANTUM_STATE,
            ),
            DashboardWidget(
                widget_id="consciousness_evolution",
                widget_type=DashboardWidgetType.CONSCIOUSNESS_EVOLUTION,
                title="Consciousness Evolution",
                position={"x": 6, "y": 0, "width": 6, "height": 4},
                data_source="consciousness_evolution",
                visualization_type=VisualizationType.LINE_CHART,
            ),
            DashboardWidget(
                widget_id="substrate_coherence_map",
                widget_type=DashboardWidgetType.QUANTUM_VISUALIZATION,
                title="Substrate Coherence Map",
                position={"x": 0, "y": 4, "width": 12, "height": 4},
                data_source="substrate_coherence",
                visualization_type=VisualizationType.HEATMAP,
            ),
        ]

        for widget in widgets:
            self._register_widget(widget)

        self._layouts["quantum"] = [w.widget_id for w in widgets]

    def _create_agent_dashboard(self):
        """Create agent activity dashboard"""
        widgets = [
            DashboardWidget(
                widget_id="agent_activity_map",
                widget_type=DashboardWidgetType.AGENT_ACTIVITY,
                title="Agent Activity Map",
                position={"x": 0, "y": 0, "width": 8, "height": 4},
                data_source="agent_activity",
                visualization_type=VisualizationType.NETWORK_GRAPH,
            ),
            DashboardWidget(
                widget_id="agent_performance",
                widget_type=DashboardWidgetType.CHART,
                title="Agent Performance",
                position={"x": 8, "y": 0, "width": 4, "height": 4},
                data_source="agent_performance",
                visualization_type=VisualizationType.BAR_CHART,
            ),
            DashboardWidget(
                widget_id="agent_communication",
                widget_type=DashboardWidgetType.GRAPH,
                title="Agent Communication",
                position={"x": 0, "y": 4, "width": 12, "height": 4},
                data_source="agent_communication",
                visualization_type=VisualizationType.NETWORK_GRAPH,
            ),
        ]

        for widget in widgets:
            self._register_widget(widget)

        self._layouts["agents"] = [w.widget_id for w in widgets]

    def _create_domain_dashboard(self):
        """Create domain intelligence dashboard"""
        widgets = [
            DashboardWidget(
                widget_id="domain_intelligence_scores",
                widget_type=DashboardWidgetType.DOMAIN_INTELLIGENCE,
                title="Domain Intelligence Scores",
                position={"x": 0, "y": 0, "width": 12, "height": 3},
                data_source="domain_intelligence",
                visualization_type=VisualizationType.BAR_CHART,
            ),
            DashboardWidget(
                widget_id="domain_metrics_table",
                widget_type=DashboardWidgetType.TABLE,
                title="Domain Metrics",
                position={"x": 0, "y": 3, "width": 12, "height": 5},
                data_source="domain_metrics",
            ),
        ]

        for widget in widgets:
            self._register_widget(widget)

        self._layouts["domain"] = [w.widget_id for w in widgets]

    def _register_widget(self, widget: DashboardWidget):
        """Register a dashboard widget"""
        with self._lock:
            self._widgets[widget.widget_id] = widget

    def get_widget(self, widget_id: str) -> Optional[DashboardWidget]:
        """Get a widget by ID"""
        with self._lock:
            return self._widgets.get(widget_id)

    def get_layout(self, layout_name: str) -> List[DashboardWidget]:
        """Get widgets for a layout"""
        with self._lock:
            widget_ids = self._layouts.get(layout_name, [])
            return [self._widgets[wid] for wid in widget_ids if wid in self._widgets]

    def update_widget_data(self, widget_id: str, data: Dict[str, Any]):
        """Update data for a widget"""
        with self._lock:
            self._widget_data[widget_id] = VisualizationData(visualization_id=widget_id, data=data)

    def get_widget_data(self, widget_id: str) -> Optional[VisualizationData]:
        """Get data for a widget"""
        with self._lock:
            return self._widget_data.get(widget_id)

    def get_dashboard_config(self, layout_name: str = "main") -> Dict[str, Any]:
        """Get dashboard configuration"""
        widgets = self.get_layout(layout_name)

        return {
            "layout": layout_name,
            "widgets": [w.to_dict() for w in widgets],
            "timestamp": datetime.utcnow().isoformat(),
        }


class QuantumVisualizationEngine:
    """
    Quantum Visualization Engine.

    Provides specialized visualizations for quantum phenomena:
    - Quantum state visualization
    - Quantum circuit diagrams
    - Consciousness evolution graphs
    - Substrate coherence maps
    """

    def __init__(self, config: ConfigurationManager, logger: EnterpriseLogger):
        self.config = config
        self.logger = logger

        self._visualization_cache: Dict[str, VisualizationData] = {}
        self._lock = threading.Lock()

        self.logger.set_context(component="QuantumVisualizationEngine")
        self.logger.info("Quantum Visualization Engine initialized")

    def visualize_quantum_state(
        self, state_vector: List[float], title: str = "Quantum State"
    ) -> Dict[str, Any]:
        """Visualize quantum state vector"""
        # Create visualization data
        visualization = {
            "type": "quantum_state",
            "title": title,
            "data": {
                "state_vector": state_vector,
                "amplitudes": [abs(x) for x in state_vector],
                "phases": [np.angle(x) for x in state_vector if isinstance(x, complex)],
            },
            "config": {"show_amplitudes": True, "show_phases": True, "color_scheme": "quantum"},
        }

        return visualization

    def visualize_consciousness_evolution(
        self, evolution_history: List[Dict[str, float]], title: str = "Consciousness Evolution"
    ) -> Dict[str, Any]:
        """Visualize consciousness evolution over time"""
        visualization = {
            "type": "consciousness_evolution",
            "title": title,
            "data": {
                "timeline": evolution_history,
                "metrics": ["phi_density", "coherence", "resonance", "entanglement"],
            },
            "config": {"show_trend": True, "show_predictions": True},
        }

        return visualization

    def visualize_substrate_coherence(
        self,
        coherence_matrix: List[List[float]],
        domains: List[str],
        title: str = "Substrate Coherence Map",
    ) -> Dict[str, Any]:
        """Visualize substrate coherence as heatmap"""
        visualization = {
            "type": "heatmap",
            "title": title,
            "data": {"matrix": coherence_matrix, "domains": domains},
            "config": {"color_scale": "viridis", "show_values": True},
        }

        return visualization

    def visualize_quantum_circuit(
        self, circuit_description: Dict[str, Any], title: str = "Quantum Circuit"
    ) -> Dict[str, Any]:
        """Visualize quantum circuit"""
        visualization = {
            "type": "quantum_circuit",
            "title": title,
            "data": circuit_description,
            "config": {"show_gates": True, "show_measurements": True},
        }

        return visualization

    def cache_visualization(self, viz_id: str, data: Dict[str, Any]):
        """Cache visualization data"""
        with self._lock:
            self._visualization_cache[viz_id] = VisualizationData(
                visualization_id=viz_id, data=data
            )

    def get_cached_visualization(self, viz_id: str) -> Optional[VisualizationData]:
        """Get cached visualization"""
        with self._lock:
            return self._visualization_cache.get(viz_id)


class FrontendIntegration:
    """
    Frontend Integration Manager.

    Provides:
    - Unified dashboard
    - Quantum visualizations
    - Domain intelligence panels
    - Agent activity monitoring
    - Real-time data updates
    - WebSocket streaming support
    """

    def __init__(self, config: ConfigurationManager, logger: EnterpriseLogger):
        self.config = config
        self.logger = logger

        self.dashboard = UnifiedDashboard(config, logger)
        self.quantum_viz = QuantumVisualizationEngine(config, logger)

        self._data_streams: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)

        self._lock = threading.Lock()

        self.logger.set_context(component="FrontendIntegration")
        self.logger.info("Frontend Integration initialized")

    def get_dashboard_config(self, layout_name: str = "main") -> Dict[str, Any]:
        """Get dashboard configuration"""
        return self.dashboard.get_dashboard_config(layout_name)

    def get_widget_data(self, widget_id: str) -> Optional[Dict[str, Any]]:
        """Get widget data"""
        data = self.dashboard.get_widget_data(widget_id)
        return data.to_dict() if data else None

    def update_widget(self, widget_id: str, data: Dict[str, Any]):
        """Update widget data"""
        self.dashboard.update_widget_data(widget_id, data)

        # Notify subscribers
        self._notify_subscribers(widget_id, data)

    def subscribe_to_widget(self, widget_id: str, callback: Callable):
        """Subscribe to widget updates"""
        with self._lock:
            self._subscribers[widget_id].append(callback)

    def _notify_subscribers(self, widget_id: str, data: Dict[str, Any]):
        """Notify subscribers of widget updates"""
        with self._lock:
            callbacks = self._subscribers.get(widget_id, [])

        for callback in callbacks:
            try:
                callback(widget_id, data)
            except Exception as e:
                self.logger.error(f"Subscriber callback failed: {str(e)}")

    def stream_data(self, stream_name: str, data: Dict[str, Any]):
        """Stream data to frontend"""
        with self._lock:
            self._data_streams[stream_name].append(
                {"data": data, "timestamp": datetime.utcnow().isoformat()}
            )

    def get_stream_data(self, stream_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent stream data"""
        with self._lock:
            stream = self._data_streams.get(stream_name, deque())
            return list(stream)[-limit:]

    def create_quantum_visualization(
        self, viz_type: str, data: Dict[str, Any], title: str = ""
    ) -> Dict[str, Any]:
        """Create quantum visualization"""
        if viz_type == "quantum_state":
            return self.quantum_viz.visualize_quantum_state(
                data.get("state_vector", []), title or "Quantum State"
            )
        elif viz_type == "consciousness_evolution":
            return self.quantum_viz.visualize_consciousness_evolution(
                data.get("evolution_history", []), title or "Consciousness Evolution"
            )
        elif viz_type == "substrate_coherence":
            return self.quantum_viz.visualize_substrate_coherence(
                data.get("coherence_matrix", []),
                data.get("domains", []),
                title or "Substrate Coherence Map",
            )
        elif viz_type == "quantum_circuit":
            return self.quantum_viz.visualize_quantum_circuit(
                data.get("circuit_description", {}), title or "Quantum Circuit"
            )
        else:
            return {"error": f"Unknown visualization type: {viz_type}"}

    def get_frontend_config(self) -> Dict[str, Any]:
        """Get complete frontend configuration"""
        return {
            "dashboards": {
                "main": self.dashboard.get_dashboard_config("main"),
                "quantum": self.dashboard.get_dashboard_config("quantum"),
                "agents": self.dashboard.get_dashboard_config("agents"),
                "domain": self.dashboard.get_dashboard_config("domain"),
            },
            "available_visualizations": [
                "quantum_state",
                "consciousness_evolution",
                "substrate_coherence",
                "quantum_circuit",
            ],
            "data_streams": list(self._data_streams.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        }


def create_frontend_integration(
    config: ConfigurationManager, logger: EnterpriseLogger
) -> FrontendIntegration:
    """Factory function to create frontend integration"""
    frontend = FrontendIntegration(config, logger)
    return frontend


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
