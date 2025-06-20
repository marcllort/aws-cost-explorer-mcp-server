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
# Usage metering request models will be imported as needed
from ...core.logger import AutocostLogger
from .auth import DatadogAuth


class DatadogClient:
    """DataDog API client wrapper."""
    
    def __init__(self, auth: DatadogAuth, logger: AutocostLogger):
        self.auth = auth
        self.logger = logger
        self._initialize_api_clients()
    
    def _initialize_api_clients(self):
        """Initialize or reinitialize API clients with current configuration."""
        self.api_client = self.auth.get_api_client()
        
        # Initialize API clients
        self.logs_api_v1 = LogsApi(self.api_client)
        self.logs_api_v2 = LogsApiV2(self.api_client)
        self.metrics_api_v1 = MetricsApi(self.api_client)
        self.metrics_api_v2 = MetricsApiV2(self.api_client)
        self.dashboards_api = DashboardsApi(self.api_client)
        self.usage_api = UsageMeteringApi(self.api_client)
        
        # Check if SSL verification is disabled in the auth config
        # and disable SSL warnings if needed
        config = self.auth.get_configuration()
        if hasattr(config, 'verify_ssl') and not config.verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def reinitialize_with_ssl_disabled(self):
        """Reinitialize all API clients with SSL verification disabled."""
        # Update auth configuration
        config = self.auth.get_configuration()
        config.verify_ssl = False
        
        # Recreate API client with new configuration
        from datadog_api_client import ApiClient
        self.auth.api_client = ApiClient(config)
        
        # Reinitialize all API clients
        self._initialize_api_clients()
    
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
            
            # Create logs request - use datetime objects directly
            sort_value = "time" if sort == "desc" else "-time"
            body = LogsListRequest(
                query=query,
                time={"from": start_time, "to": end_time},
                sort=sort_value,
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
            
            try:
                response = self.metrics_api_v1.query_metrics(
                    _from=start_ts,
                    to=end_ts,
                    query=query
                )
            except Exception as ssl_error:
                # Handle SSL certificate verification issues (corporate environments)
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(ssl_error):
                    self.logger.info("SSL verification failed in query_metrics, reinitializing with SSL disabled", "datadog")
                    self.reinitialize_with_ssl_disabled()
                    response = self.metrics_api_v1.query_metrics(
                        _from=start_ts,
                        to=end_ts,
                        query=query
                    )
                else:
                    raise ssl_error
            
            series_data = []
            if hasattr(response, 'series') and response.series:
                for series in response.series:
                    points = []
                    if hasattr(series, 'pointlist') and series.pointlist:
                        for point in series.pointlist:
                            # Parse DataDog Point objects correctly
                            try:
                                if hasattr(point, 'to_dict'):
                                    point_dict = point.to_dict()
                                    if isinstance(point_dict, list) and len(point_dict) >= 2:
                                        points.append({
                                            "timestamp": point_dict[0],
                                            "value": point_dict[1]
                                        })
                                else:
                                    # Parse using repr() method
                                    point_repr = repr(point)
                                    if '[' in point_repr and ']' in point_repr:
                                        import ast
                                        try:
                                            parsed = ast.literal_eval(point_repr)
                                            if isinstance(parsed, list) and len(parsed) >= 2:
                                                points.append({
                                                    "timestamp": parsed[0],
                                                    "value": parsed[1]
                                                })
                                        except:
                                            pass
                            except Exception:
                                # Fallback to old method
                                try:
                                    if hasattr(point, '__getitem__') and len(point) >= 2:
                                        points.append({
                                            "timestamp": point[0],
                                            "value": point[1]
                                        })
                                except:
                                    pass
                    
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
            try:
                response = self.dashboards_api.list_dashboards()
            except Exception as ssl_error:
                # Handle SSL certificate verification issues (corporate environments)
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(ssl_error):
                    self.logger.info("SSL verification failed in list_dashboards, reinitializing with SSL disabled", "datadog")
                    self.reinitialize_with_ssl_disabled()
                    response = self.dashboards_api.list_dashboards()
                else:
                    raise ssl_error
            
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
    
    async def get_dashboard_data(
        self, 
        dashboard_id: str, 
        template_variables: Optional[Dict[str, str]] = None,
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get dashboard data including widget values using the dashboard data API."""
        try:
            # Use the dashboard data API endpoint that the web interface uses
            import requests
            import urllib3
            from datetime import datetime, timedelta
            
            # Disable SSL warnings if we're in disabled SSL mode
            if hasattr(self, '_ssl_disabled') and self._ssl_disabled:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Calculate timestamps if not provided
            if not from_ts or not to_ts:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=24)
                from_ts = int(start_time.timestamp() * 1000)
                to_ts = int(end_time.timestamp() * 1000)
            
            # Build the dashboard data URL (this is what the web interface calls)
            site = self.auth.config.datadog_site
            base_url = f"https://app.{site}"
            data_url = f"{base_url}/api/v1/dashboard/{dashboard_id}/data"
            
            # Build query parameters like the web interface
            params = {
                'from_ts': from_ts,
                'to_ts': to_ts,
                'live': 'true',
                'refresh_mode': 'sliding',
                'fromUser': 'false'
            }
            
            # Add template variables
            if template_variables:
                for key, value in template_variables.items():
                    params[f'tpl_var_{key}[0]'] = value
            
            # Make the API request with proper headers
            headers = {
                'DD-API-KEY': self.auth.config.datadog_api_key,
                'DD-APPLICATION-KEY': self.auth.config.datadog_app_key,
                'Content-Type': 'application/json',
                'User-Agent': 'DataDog/MCP-Client'
            }
            
            try:
                # Try with SSL verification first
                response = requests.get(
                    data_url, 
                    params=params, 
                    headers=headers, 
                    timeout=30,
                    verify=True
                )
            except Exception as ssl_error:
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(ssl_error):
                    self.logger.info("SSL verification failed in dashboard data API, trying without verification", "datadog")
                    # Retry without SSL verification
                    response = requests.get(
                        data_url, 
                        params=params, 
                        headers=headers, 
                        timeout=30,
                        verify=False
                    )
                    self._ssl_disabled = True
                else:
                    raise ssl_error
            
            if response.status_code == 200:
                return response.json()
            else:
                # Try multiple API endpoints that DataDog might use
                api_endpoints = [
                    f"{base_url}/api/v1/dashboard/{dashboard_id}/widget_values",
                    f"{base_url}/api/v2/dashboard/{dashboard_id}/data", 
                    f"{base_url}/api/internal/dashboard/{dashboard_id}/data",
                    f"{base_url}/api/v1/graph/embed/{dashboard_id}/widget_data",
                    f"{base_url}/dashboard/api/v1/{dashboard_id}/data"
                ]
                
                for endpoint in api_endpoints:
                    try:
                        alt_response = requests.get(
                            endpoint,
                            params=params,
                            headers=headers,
                            timeout=30,
                            verify=not getattr(self, '_ssl_disabled', False)
                        )
                        
                        if alt_response.status_code == 200:
                            result = alt_response.json()
                            result['_endpoint_used'] = endpoint
                            return result
                    except Exception:
                        continue
                
                # If all endpoints fail, try getting individual widget data
                try:
                    # Get dashboard definition first to get widget IDs
                    dashboard_def = await self.get_dashboard(dashboard_id)
                    widgets = dashboard_def.get('widgets', [])
                    
                    widget_data = []
                    for widget in widgets:
                        widget_id = widget.get('id')
                        if widget_id:
                            widget_url = f"{base_url}/api/v1/dashboard/{dashboard_id}/widget/{widget_id}/data"
                            try:
                                widget_response = requests.get(
                                    widget_url,
                                    params=params,
                                    headers=headers,
                                    timeout=30,
                                    verify=not getattr(self, '_ssl_disabled', False)
                                )
                                if widget_response.status_code == 200:
                                    widget_data.append(widget_response.json())
                            except Exception:
                                continue
                    
                    if widget_data:
                        return {
                            'widgets': widget_data,
                            '_method': 'individual_widgets'
                        }
                except Exception:
                    pass
                
                # If everything fails, return detailed error info
                return {
                    'error': f'All dashboard data APIs failed. Primary status: {response.status_code}',
                    'response_text': response.text[:500],
                    'url': data_url,
                    'params': params,
                    'attempted_endpoints': api_endpoints
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get dashboard data for {dashboard_id}: {e}", "datadog")
            raise

    async def get_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Get dashboard information including widgets and template variables."""
        try:
            try:
                response = self.dashboards_api.get_dashboard(dashboard_id)
            except Exception as ssl_error:
                # Handle SSL certificate verification issues (corporate environments)
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(ssl_error):
                    self.logger.info("SSL verification failed in get_dashboard, reinitializing with SSL disabled", "datadog")
                    self.reinitialize_with_ssl_disabled()
                    response = self.dashboards_api.get_dashboard(dashboard_id)
                else:
                    raise ssl_error
            
            # Process widgets including nested widgets in groups
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
                            "requests": []
                        }
                        
                        # Handle requests - convert to dict format
                        requests = getattr(definition, 'requests', [])
                        if requests:
                            for request in requests:
                                if hasattr(request, 'to_dict'):
                                    widget_data["definition"]["requests"].append(request.to_dict())
                                elif isinstance(request, dict):
                                    widget_data["definition"]["requests"].append(request)
                                else:
                                    # Convert request object to dict manually
                                    request_dict = {}
                                    for attr in ['q', 'query', 'formulas', 'queries', 'response_format', 'style']:
                                        if hasattr(request, attr):
                                            value = getattr(request, attr)
                                            if value is not None:
                                                # Handle complex objects
                                                if hasattr(value, 'to_dict'):
                                                    request_dict[attr] = value.to_dict()
                                                elif isinstance(value, list):
                                                    # Handle lists of objects
                                                    request_dict[attr] = []
                                                    for item in value:
                                                        if hasattr(item, 'to_dict'):
                                                            request_dict[attr].append(item.to_dict())
                                                        else:
                                                            request_dict[attr].append(item)
                                                else:
                                                    request_dict[attr] = value
                                    if request_dict:
                                        widget_data["definition"]["requests"].append(request_dict)
                        
                        # Handle group widgets with nested widgets
                        if getattr(definition, 'type', '') == 'group':
                            # Extract nested widgets from group
                            if hasattr(definition, 'to_dict'):
                                definition_dict = definition.to_dict()
                                nested_widgets = definition_dict.get('widgets', [])
                                
                                widget_data["definition"]["widgets"] = []
                                widget_data["definition"]["nested_widgets"] = []  # Keep both for compatibility
                                
                                for nested_widget in nested_widgets:
                                    nested_data = {
                                        "id": nested_widget.get('id', ''),
                                        "definition": nested_widget.get('definition', {}),
                                        "layout": nested_widget.get('layout', {})
                                    }
                                    
                                    widget_data["definition"]["widgets"].append(nested_data)
                                    widget_data["definition"]["nested_widgets"].append(nested_data)  # Compatibility
                    
                    widgets.append(widget_data)
            
            # Process template variables
            template_variables = []
            if hasattr(response, 'template_variables') and response.template_variables:
                for var in response.template_variables:
                    if hasattr(var, 'to_dict'):
                        template_variables.append(var.to_dict())
                    else:
                        template_variables.append({
                            'name': getattr(var, 'name', ''),
                            'prefix': getattr(var, 'prefix', ''),
                            'default': getattr(var, 'default', ''),
                            'available_values': getattr(var, 'available_values', [])
                        })
            
            return {
                "id": getattr(response, 'id', ''),
                "title": getattr(response, 'title', ''),
                "description": getattr(response, 'description', ''),
                "created_at": getattr(response, 'created_at', None),
                "modified_at": getattr(response, 'modified_at', None),
                "author_handle": getattr(response, 'author_handle', ''),
                "widget_count": len(widgets),
                "widgets": widgets,
                "template_variables": template_variables
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