"""DataDog-specific data models for Autocost Controller."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class DatadogLog(BaseModel):
    """Individual log entry from DataDog."""
    timestamp: datetime
    content: str
    attributes: Dict[str, Any] = {}
    tags: List[str] = []
    service: str = "unknown"
    status: str = "info"


class DatadogLogAnalysis(BaseModel):
    """Complete log analysis results."""
    query: str
    start_time: str
    end_time: str
    total_logs: int
    logs: List[DatadogLog]
    service_breakdown: Dict[str, int] = {}
    status_breakdown: Dict[str, int] = {}


class DatadogMetricPoint(BaseModel):
    """Individual metric data point."""
    timestamp: float
    value: float


class DatadogMetricSeries(BaseModel):
    """Metric series data."""
    metric: str
    tags: List[str] = []
    display_name: str = ""
    unit: Optional[str] = None
    points: List[DatadogMetricPoint] = []


class DatadogMetricAnalysis(BaseModel):
    """Complete metric analysis results."""
    metric_name: str
    start_time: str
    end_time: str
    series_count: int
    series: List[DatadogMetricSeries]


class DatadogWidgetDefinition(BaseModel):
    """Dashboard widget definition."""
    type: str = ""
    title: str = ""
    requests: List[Dict[str, Any]] = []


class DatadogWidget(BaseModel):
    """Dashboard widget."""
    id: str = ""
    definition: DatadogWidgetDefinition
    layout: Dict[str, Any] = {}


class DatadogDashboard(BaseModel):
    """DataDog dashboard information."""
    id: str
    title: str
    description: str = ""
    author_handle: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    url: str = ""
    is_read_only: bool = False
    widget_count: int = 0
    widgets: List[DatadogWidget] = []
    template_variables: List[Dict[str, Any]] = []


class DatadogDashboardList(BaseModel):
    """List of DataDog dashboards."""
    total_dashboards: int
    dashboards: List[DatadogDashboard]


class DatadogUsageMetrics(BaseModel):
    """DataDog usage metrics."""
    start_date: str
    end_date: str
    period_days: int
    usage_metrics: Dict[str, float] = {
        "logs_indexed": 0.0,
        "custom_metrics": 0.0,
        "trace_search": 0.0,
        "synthetics": 0.0
    }


class DatadogCostAnalysis(BaseModel):
    """DataDog cost analysis results."""
    period_days: int
    total_cost: float = 0.0
    cost_breakdown: Dict[str, float] = {}
    usage_metrics: DatadogUsageMetrics
    optimization_opportunities: List[str] = []
    recommendations: List[str] = []


class DatadogServiceHealth(BaseModel):
    """Service health metrics from DataDog."""
    service_name: str
    error_rate: float = 0.0
    latency_p95: float = 0.0
    throughput: float = 0.0
    apdex_score: float = 0.0
    status: str = "unknown"  # healthy, warning, critical, unknown


class DatadogInfrastructureMetrics(BaseModel):
    """Infrastructure metrics from DataDog."""
    host_count: int = 0
    container_count: int = 0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    disk_utilization: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0 