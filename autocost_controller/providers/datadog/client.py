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
                    widget_data = self._extract_widget_data(widget)
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

    def _extract_widget_data(self, widget) -> Dict[str, Any]:
        """Extract widget data including nested widgets and their requests."""
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
            
            # Extract requests from this widget
            requests = self._extract_requests_from_definition(definition)
            widget_data["definition"]["requests"] = requests
            
            # Handle group widgets with nested widgets
            if getattr(definition, 'type', '') == 'group':
                nested_widgets = self._extract_nested_widgets(definition)
                widget_data["definition"]["widgets"] = nested_widgets
                widget_data["definition"]["nested_widgets"] = nested_widgets  # Compatibility
        
        return widget_data

    def _extract_requests_from_definition(self, definition) -> List[Dict[str, Any]]:
        """Extract requests from a widget definition."""
        requests = []
        
        # Get direct requests
        direct_requests = getattr(definition, 'requests', [])
        if direct_requests:
            for request in direct_requests:
                request_dict = self._convert_request_to_dict(request)
                if request_dict:
                    requests.append(request_dict)
        
        return requests

    def _convert_request_to_dict(self, request) -> Dict[str, Any]:
        """Convert a request object to dictionary format."""
        if hasattr(request, 'to_dict'):
            return request.to_dict()
        elif isinstance(request, dict):
            return request
        else:
            # Convert request object to dict manually
            request_dict = {}
            
            # Common request attributes to extract
            attributes = [
                'q', 'query', 'formulas', 'queries', 'response_format', 'style',
                'aggregator', 'conditional_formats', 'limit', 'order',
                'metric_query', 'log_query', 'apm_query', 'network_query',
                'rum_query', 'security_query', 'event_query'
            ]
            
            for attr in attributes:
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
            
            return request_dict if request_dict else None

    def _extract_nested_widgets(self, definition) -> List[Dict[str, Any]]:
        """Extract nested widgets from a group widget definition with enhanced parsing."""
        nested_widgets = []
        
        # Method 1: Try to get nested widgets using to_dict()
        if hasattr(definition, 'to_dict'):
            try:
                definition_dict = definition.to_dict()
                raw_nested_widgets = definition_dict.get('widgets', [])
                
                for nested_widget in raw_nested_widgets:
                    nested_data = {
                        "id": nested_widget.get('id', ''),
                        "definition": nested_widget.get('definition', {}),
                        "layout": nested_widget.get('layout', {})
                    }
                    
                    # Extract requests from nested widget definition
                    nested_def = nested_widget.get('definition', {})
                    if nested_def and 'requests' in nested_def:
                        nested_data["definition"]["requests"] = nested_def['requests']
                    elif nested_def:
                        # Try to extract requests from the nested definition object
                        nested_data["definition"]["requests"] = self._extract_requests_from_nested_def(nested_def)
                    
                    nested_widgets.append(nested_data)
                    
            except Exception as e:
                self.logger.debug(f"Failed to extract nested widgets via to_dict: {e}")
        
        # Method 2: Try alternative approach using direct attribute access
        if not nested_widgets and hasattr(definition, 'widgets'):
            try:
                for nested_widget in definition.widgets:
                    nested_data = self._extract_widget_data(nested_widget)
                    nested_widgets.append(nested_data)
            except Exception as e:
                self.logger.debug(f"Failed to extract nested widgets via direct access: {e}")
        
        # Method 3: Enhanced extraction using raw API response parsing
        if not nested_widgets:
            try:
                # Try to access the raw API response data directly
                if hasattr(definition, '_data_store'):
                    raw_data = definition._data_store
                    if 'widgets' in raw_data:
                        for widget_data in raw_data['widgets']:
                            nested_widgets.append(self._parse_raw_widget_data(widget_data))
                
                # Alternative: try to parse from string representation if available
                elif hasattr(definition, '_raw_data') or hasattr(definition, 'additional_properties'):
                    # Some DataDog objects store raw data in additional_properties
                    additional_props = getattr(definition, 'additional_properties', {})
                    if 'widgets' in additional_props:
                        for widget_data in additional_props['widgets']:
                            nested_widgets.append(self._parse_raw_widget_data(widget_data))
                            
            except Exception as e:
                self.logger.debug(f"Failed enhanced nested widget extraction: {e}")
        
        # Method 4: Brute force - try to extract from any available attributes
        if not nested_widgets:
            try:
                # Get all attributes and look for anything that might contain widgets
                definition_attrs = dir(definition)
                for attr_name in definition_attrs:
                    if 'widget' in attr_name.lower() and not attr_name.startswith('_'):
                        try:
                            attr_value = getattr(definition, attr_name)
                            if isinstance(attr_value, list):
                                for item in attr_value:
                                    if hasattr(item, 'definition') or isinstance(item, dict):
                                        nested_data = self._extract_widget_data(item) if hasattr(item, 'definition') else self._parse_raw_widget_data(item)
                                        nested_widgets.append(nested_data)
                        except:
                            continue
            except Exception as e:
                self.logger.debug(f"Failed brute force widget extraction: {e}")
        
        return nested_widgets

    def _parse_raw_widget_data(self, widget_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw widget data from API response."""
        return {
            "id": widget_data.get('id', ''),
            "definition": widget_data.get('definition', {}),
            "layout": widget_data.get('layout', {}),
            "raw_data": widget_data  # Store raw data for debugging
        }

    def _extract_requests_from_nested_def(self, nested_def) -> List[Dict[str, Any]]:
        """Extract requests from a nested widget definition dictionary."""
        requests = []
        
        # Handle different request formats in nested definitions
        if 'requests' in nested_def:
            raw_requests = nested_def['requests']
            if isinstance(raw_requests, list):
                for req in raw_requests:
                    if isinstance(req, dict):
                        requests.append(req)
                    else:
                        converted = self._convert_request_to_dict(req)
                        if converted:
                            requests.append(converted)
        
        # Look for other potential request containers
        for key in ['queries', 'formulas', 'query']:
            if key in nested_def and nested_def[key]:
                value = nested_def[key]
                if isinstance(value, str):
                    # Direct query string
                    requests.append({'q': value})
                elif isinstance(value, dict):
                    requests.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            requests.append(item)
                        elif isinstance(item, str):
                            requests.append({'q': item})
        
        return requests

    async def extract_all_metrics_from_dashboard(self, dashboard_id: str) -> List[Dict[str, Any]]:
        """Extract all metric queries from a dashboard, including nested widgets with fallback strategies."""
        try:
            dashboard_data = await self.get_dashboard(dashboard_id)
            all_metrics = []
            
            for widget in dashboard_data.get('widgets', []):
                metrics = self._extract_metrics_from_widget(widget)
                all_metrics.extend(metrics)
            
            # If no metrics found with standard extraction, try alternative approaches
            if not all_metrics:
                self.logger.info("No metrics found with standard extraction, trying alternative methods", "datadog")
                
                # Try to get raw dashboard data and parse it differently
                try:
                    raw_response = self.dashboards_api.get_dashboard(dashboard_id)
                    if hasattr(raw_response, 'to_dict'):
                        raw_dict = raw_response.to_dict()
                        alt_metrics = self._extract_metrics_from_raw_dict(raw_dict, dashboard_id)
                        all_metrics.extend(alt_metrics)
                except Exception as e:
                    self.logger.debug(f"Alternative extraction failed: {e}")
            
            return all_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to extract metrics from dashboard {dashboard_id}: {e}", "datadog")
            raise

    def _extract_metrics_from_widget(self, widget) -> List[Dict[str, Any]]:
        """Extract all metric queries from a widget (including nested widgets)."""
        metrics = []
        
        # Extract from direct requests
        definition = widget.get('definition', {})
        requests = definition.get('requests', [])
        
        for request in requests:
            metric_queries = self._extract_queries_from_request(request)
            for query in metric_queries:
                metrics.append({
                    'widget_id': widget.get('id', ''),
                    'widget_title': definition.get('title', ''),
                    'widget_type': definition.get('type', ''),
                    'query': query,
                    'request_type': 'direct'
                })
        
        # Extract from nested widgets (for group widgets)
        nested_widgets = definition.get('widgets', [])
        for nested_widget in nested_widgets:
            nested_metrics = self._extract_metrics_from_widget(nested_widget)
            for metric in nested_metrics:
                metric['parent_widget_id'] = widget.get('id', '')
                metric['parent_widget_title'] = definition.get('title', '')
                metric['request_type'] = 'nested'
            metrics.extend(nested_metrics)
        
        return metrics

    def _extract_queries_from_request(self, request) -> List[str]:
        """Extract metric query strings from a request."""
        queries = []
        
        # Common query fields
        query_fields = ['q', 'query', 'metric_query']
        
        for field in query_fields:
            if field in request and request[field]:
                value = request[field]
                if isinstance(value, str):
                    queries.append(value)
                elif isinstance(value, dict) and 'q' in value:
                    queries.append(value['q'])
        
        # Handle formulas and queries arrays
        if 'formulas' in request:
            formulas = request['formulas']
            if isinstance(formulas, list):
                for formula in formulas:
                    if isinstance(formula, dict) and 'formula' in formula:
                        queries.append(formula['formula'])
        
        if 'queries' in request:
            query_list = request['queries']
            if isinstance(query_list, list):
                for query_obj in query_list:
                    if isinstance(query_obj, dict):
                        for field in ['metric_query', 'data_source', 'query']:
                            if field in query_obj and query_obj[field]:
                                if isinstance(query_obj[field], str):
                                    queries.append(query_obj[field])
                                elif isinstance(query_obj[field], dict) and 'q' in query_obj[field]:
                                    queries.append(query_obj[field]['q'])
        
        return queries

    def _extract_metrics_from_raw_dict(self, raw_dict: Dict[str, Any], dashboard_id: str) -> List[Dict[str, Any]]:
        """Extract metrics from raw dashboard dictionary with more aggressive parsing."""
        metrics = []
        
        def recursive_search(obj, path="", parent_title=""):
            """Recursively search for metric queries in any object structure."""
            if isinstance(obj, dict):
                # Look for direct metric queries
                for key in ['q', 'query', 'metric_query']:
                    if key in obj and isinstance(obj[key], str):
                        if any(metric_word in obj[key].lower() for metric_word in ['sum:', 'avg:', 'max:', 'min:', 'count:']):
                            metrics.append({
                                'dashboard_id': dashboard_id,
                                'widget_title': parent_title or obj.get('title', 'Unknown'),
                                'widget_type': obj.get('type', 'unknown'),
                                'query': obj[key],
                                'extraction_path': path,
                                'request_type': 'raw_dict'
                            })
                
                # Recursively search all nested objects
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    new_title = value.get('title', parent_title) if isinstance(value, dict) and 'title' in value else parent_title
                    recursive_search(value, new_path, new_title)
                    
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    recursive_search(item, new_path, parent_title)
        
        # Start recursive search
        recursive_search(raw_dict)
        
        return metrics
    
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
    
    async def query_metrics(
        self,
        query: str,
        start_time: int,
        end_time: int
    ) -> Dict[str, Any]:
        """Query metrics using full DataDog query syntax with grouping support."""
        try:
            try:
                response = self.metrics_api_v1.query_metrics(
                    _from=start_time,
                    to=end_time,
                    query=query
                )
            except Exception as ssl_error:
                # Handle SSL certificate verification issues (corporate environments)
                if "SSL: CERTIFICATE_VERIFY_FAILED" in str(ssl_error):
                    self.logger.info("SSL verification failed in query_metrics, reinitializing with SSL disabled", "datadog")
                    self.reinitialize_with_ssl_disabled()
                    response = self.metrics_api_v1.query_metrics(
                        _from=start_time,
                        to=end_time,
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
                    
                    # Extract scope for grouping
                    scope = getattr(series, 'scope', '')
                    
                    series_data.append({
                        "metric": getattr(series, 'metric', ''),
                        "tags": getattr(series, 'tag_set', []),
                        "display_name": getattr(series, 'display_name', ''),
                        "unit": getattr(series, 'unit', None),
                        "scope": scope,
                        "points": points
                    })
            
            return {
                "query": query,
                "series": series_data
            }
            
        except Exception as e:
            self.logger.error(f"Failed to query DataDog metrics: {e}", "datadog")
            raise 