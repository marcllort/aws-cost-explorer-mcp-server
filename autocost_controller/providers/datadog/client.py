"""DataDog API client wrapper for Autocost Controller."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from datadog_api_client.v1.api.logs_api import LogsApi
from datadog_api_client.v1.api.metrics_api import MetricsApi
from datadog_api_client.v1.api.dashboards_api import DashboardsApi
from datadog_api_client.v1.api.usage_metering_api import UsageMeteringApi
from datadog_api_client.v2.api.logs_api import LogsApi as LogsApiV2
from datadog_api_client.v2.api.metrics_api import MetricsApi as MetricsApiV2
from datadog_api_client.v1.model.logs_list_request import LogsListRequest
from datadog_api_client.v1.model.logs_sort import LogsSort
from datadog_api_client.v2.model.logs_list_request import LogsListRequest as LogsListRequestV2
from datadog_api_client.v1.model.usage_metering_request import UsageMeteringRequest
from ...core.logger import AutocostLogger
from .auth import DatadogAuth


class DatadogClient:
    """DataDog API client wrapper."""
    
    def __init__(self, auth: DatadogAuth, logger: AutocostLogger):
        self.auth = auth
        self.logger = logger
        self.api_client = auth.get_api_client()
        
        # Initialize API clients
        self.logs_api_v1 = LogsApi(self.api_client)
        self.logs_api_v2 = LogsApiV2(self.api_client)
        self.metrics_api_v1 = MetricsApi(self.api_client)
        self.metrics_api_v2 = MetricsApiV2(self.api_client)
        self.dashboards_api = DashboardsApi(self.api_client)
        self.usage_api = UsageMeteringApi(self.api_client)
    
    async def get_logs(
        self,
        query: str = "*",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        sort: str = "desc"
    ) -> Dict[str, Any]:
        """Get logs from DataDog."""
        try:
            if not start_time:
                start_time = datetime.now() - timedelta(hours=1)
            if not end_time:
                end_time = datetime.now()
            
            # Convert to milliseconds timestamp
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)
            
            # Create logs request
            body = LogsListRequest(
                query=query,
                time={"from": start_ts, "to": end_ts},
                sort=LogsSort.TIME_DESC if sort == "desc" else LogsSort.TIME_ASC,
                limit=limit
            )
            
            response = self.logs_api_v1.list_logs(body=body)
            
            logs = []
            if hasattr(response, 'logs') and response.logs:
                for log in response.logs:
                    logs.append({
                        "timestamp": log.timestamp,
                        "content": getattr(log, 'content', ''),
                        "attributes": getattr(log, 'attributes', {}),
                        "tags": getattr(log, 'tags', []),
                        "service": getattr(log.attributes, 'service', 'unknown') if hasattr(log, 'attributes') else 'unknown',
                        "status": getattr(log, 'status', 'info')
                    })
            
            return {
                "query": query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_logs": len(logs),
                "logs": logs
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get DataDog logs: {e}", "datadog")
            raise
    
    async def get_metrics(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get metrics from DataDog."""
        try:
            if not start_time:
                start_time = datetime.now() - timedelta(hours=1)
            if not end_time:
                end_time = datetime.now()
            
            # Convert to Unix timestamp
            start_ts = int(start_time.timestamp())
            end_ts = int(end_time.timestamp())
            
            # Build query
            query = metric_name
            if tags:
                tag_filter = "{" + ",".join(tags) + "}"
                query = f"{metric_name}{tag_filter}"
            
            response = self.metrics_api_v1.query_metrics(
                _from=start_ts,
                to=end_ts,
                query=query
            )
            
            series_data = []
            if hasattr(response, 'series') and response.series:
                for series in response.series:
                    points = []
                    if hasattr(series, 'pointlist') and series.pointlist:
                        for point in series.pointlist:
                            if len(point) >= 2:
                                points.append({
                                    "timestamp": point[0],
                                    "value": point[1]
                                })
                    
                    series_data.append({
                        "metric": getattr(series, 'metric', metric_name),
                        "tags": getattr(series, 'tag_set', []),
                        "display_name": getattr(series, 'display_name', ''),
                        "unit": getattr(series, 'unit', None),
                        "points": points
                    })
            
            return {
                "metric_name": metric_name,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "series_count": len(series_data),
                "series": series_data
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get DataDog metrics: {e}", "datadog")
            raise
    
    async def list_dashboards(self) -> Dict[str, Any]:
        """List all DataDog dashboards."""
        try:
            response = self.dashboards_api.list_dashboards()
            
            dashboards = []
            if hasattr(response, 'dashboards') and response.dashboards:
                for dashboard in response.dashboards:
                    dashboards.append({
                        "id": getattr(dashboard, 'id', ''),
                        "title": getattr(dashboard, 'title', ''),
                        "description": getattr(dashboard, 'description', ''),
                        "author_handle": getattr(dashboard, 'author_handle', ''),
                        "created_at": getattr(dashboard, 'created_at', None),
                        "modified_at": getattr(dashboard, 'modified_at', None),
                        "url": getattr(dashboard, 'url', ''),
                        "is_read_only": getattr(dashboard, 'is_read_only', False)
                    })
            
            return {
                "total_dashboards": len(dashboards),
                "dashboards": dashboards
            }
            
        except Exception as e:
            self.logger.error(f"Failed to list DataDog dashboards: {e}", "datadog")
            raise
    
    async def get_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Get specific DataDog dashboard details."""
        try:
            response = self.dashboards_api.get_dashboard(dashboard_id)
            
            widgets = []
            if hasattr(response, 'widgets') and response.widgets:
                for widget in response.widgets:
                    widget_data = {
                        "id": getattr(widget, 'id', ''),
                        "definition": {},
                        "layout": getattr(widget, 'layout', {})
                    }
                    
                    if hasattr(widget, 'definition'):
                        definition = widget.definition
                        widget_data["definition"] = {
                            "type": getattr(definition, 'type', ''),
                            "title": getattr(definition, 'title', ''),
                            "requests": getattr(definition, 'requests', [])
                        }
                    
                    widgets.append(widget_data)
            
            return {
                "id": getattr(response, 'id', ''),
                "title": getattr(response, 'title', ''),
                "description": getattr(response, 'description', ''),
                "created_at": getattr(response, 'created_at', None),
                "modified_at": getattr(response, 'modified_at', None),
                "author_handle": getattr(response, 'author_handle', ''),
                "widget_count": len(widgets),
                "widgets": widgets,
                "template_variables": getattr(response, 'template_variables', [])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get DataDog dashboard {dashboard_id}: {e}", "datadog")
            raise
    
    async def get_usage_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get DataDog usage metrics."""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # Format dates for API
            start_hr = start_date.strftime("%Y-%m-%dT%H")
            end_hr = end_date.strftime("%Y-%m-%dT%H")
            
            response = self.usage_api.get_usage_summary(
                start_hr=start_hr,
                end_hr=end_hr
            )
            
            usage_data = {}
            if response:
                # Extract various usage metrics
                if hasattr(response, 'logs_usage_agg_sum'):
                    usage_data['logs_indexed'] = getattr(response.logs_usage_agg_sum, 'value', 0)
                
                if hasattr(response, 'custom_metrics_usage_agg_sum'):
                    usage_data['custom_metrics'] = getattr(response.custom_metrics_usage_agg_sum, 'value', 0)
                
                if hasattr(response, 'trace_search_usage_agg_sum'):
                    usage_data['trace_search'] = getattr(response.trace_search_usage_agg_sum, 'value', 0)
                
                if hasattr(response, 'synthetics_usage_agg_sum'):
                    usage_data['synthetics'] = getattr(response.synthetics_usage_agg_sum, 'value', 0)
            
            return {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "period_days": (end_date - start_date).days,
                "usage_metrics": usage_data
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get DataDog usage metrics: {e}", "datadog")
            raise
    
    async def search_logs_aggregated(
        self,
        query: str = "*",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: str = "count"
    ) -> Dict[str, Any]:
        """Get aggregated log data for analysis."""
        try:
            if not start_time:
                start_time = datetime.now() - timedelta(hours=24)
            if not end_time:
                end_time = datetime.now()
            
            # This would use the logs search API to get aggregated data
            # For now, we'll get regular logs and aggregate them
            logs_data = await self.get_logs(query, start_time, end_time, limit=1000)
            
            # Simple aggregation by service and status
            service_counts = {}
            status_counts = {}
            
            for log in logs_data.get('logs', []):
                service = log.get('service', 'unknown')
                status = log.get('status', 'info')
                
                service_counts[service] = service_counts.get(service, 0) + 1
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "query": query,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_logs": logs_data.get('total_logs', 0),
                "aggregation_type": aggregation,
                "service_breakdown": service_counts,
                "status_breakdown": status_counts
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get aggregated logs: {e}", "datadog")
            raise 