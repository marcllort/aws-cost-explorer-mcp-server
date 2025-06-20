"""DataDog-specific tools for the Autocost Controller."""

from typing import Optional, List, Union, Dict, Any
from datetime import datetime, timedelta
import json

from mcp.server.fastmcp import FastMCP
from ..core.config import Config
from ..core.logger import AutocostLogger
from ..core.provider_manager import ProviderManager


def register_datadog_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register DataDog-specific tools."""
    
    datadog_provider = provider_manager.get_provider("datadog")
    if not datadog_provider:
        logger.warning("DataDog provider not available, skipping DataDog tools registration")
        return

    logger.info("🔧 Registering DataDog monitoring tools...")

    @mcp.tool()
    async def datadog_logs_search(
        query: str = "*",
        hours: int = 1,
        limit: int = 100,
        service: Optional[str] = None
    ) -> str:
        """DataDog Logs: Search and analyze logs with filtering."""
        logger.info(f"🔍 Searching DataDog logs with query: '{query}' for {hours} hours...")
        
        try:
            client = datadog_provider.get_client("logs")
            
            # Build query with service filter if provided
            search_query = query
            if service:
                search_query = f"service:{service} {query}" if query != "*" else f"service:{service}"
            
            # Set time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            logs_data = await client.get_logs(
                query=search_query,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            # Format response
            response = f"🔍 **DATADOG LOGS SEARCH RESULTS**\n\n"
            response += f"📊 **Query**: {search_query}\n"
            response += f"⏰ **Time Range**: {hours} hours\n"
            response += f"📈 **Total Logs Found**: {logs_data['total_logs']}\n\n"
            
            if logs_data['logs']:
                response += f"📋 **Recent Logs** (showing up to {limit}):\n"
                for i, log in enumerate(logs_data['logs'][:10], 1):
                    timestamp = datetime.fromtimestamp(log['timestamp'] / 1000) if isinstance(log['timestamp'], (int, float)) else log['timestamp']
                    response += f"{i:2d}. **{timestamp.strftime('%H:%M:%S')}** [{log['status'].upper()}] {log['service']}\n"
                    response += f"    {log['content'][:100]}{'...' if len(log['content']) > 100 else ''}\n"
                    if log['tags']:
                        response += f"    Tags: {', '.join(log['tags'][:3])}{'...' if len(log['tags']) > 3 else ''}\n"
                    response += "\n"
            else:
                response += "📭 No logs found matching the criteria.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog logs search failed: {e}", provider="datadog")
            return f"❌ Error searching DataDog logs: {str(e)}"

    @mcp.tool()
    async def datadog_metrics_query(
        metric_name: str,
        hours: int = 1,
        tags: Optional[str] = None
    ) -> str:
        """DataDog Metrics: Query specific metrics with optional tag filtering."""
        logger.info(f"📈 Querying DataDog metric: {metric_name} for {hours} hours...")
        
        try:
            client = datadog_provider.get_client("metrics")
            
            # Parse tags if provided
            tag_list = []
            if tags:
                tag_list = [tag.strip() for tag in tags.split(",")]
            
            # Set time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            metrics_data = await client.get_metrics(
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time,
                tags=tag_list
            )
            
            response = f"📈 **DATADOG METRICS QUERY RESULTS**\n\n"
            response += f"🎯 **Metric**: {metric_name}\n"
            response += f"⏰ **Time Range**: {hours} hours\n"
            response += f"📊 **Series Count**: {metrics_data['series_count']}\n\n"
            
            if metrics_data['series']:
                for i, series in enumerate(metrics_data['series'][:5], 1):
                    response += f"**Series {i}**: {series['display_name'] or series['metric']}\n"
                    response += f"   Tags: {', '.join(series['tags']) if series['tags'] else 'None'}\n"
                    response += f"   Unit: {series['unit'] or 'N/A'}\n"
                    response += f"   Data Points: {len(series['points'])}\n"
                    
                    if series['points']:
                        # Show latest value
                        latest_point = series['points'][-1]
                        latest_time = datetime.fromtimestamp(latest_point['timestamp'] / 1000)
                        response += f"   Latest Value: {latest_point['value']:.2f} at {latest_time.strftime('%H:%M:%S')}\n"
                        
                        # Calculate basic stats
                        values = [point['value'] for point in series['points']]
                        avg_value = sum(values) / len(values)
                        min_value = min(values)
                        max_value = max(values)
                        
                        response += f"   Stats: Avg={avg_value:.2f}, Min={min_value:.2f}, Max={max_value:.2f}\n"
                    
                    response += "\n"
            else:
                response += "📭 No data found for this metric.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog metrics query failed: {e}", provider="datadog")
            return f"❌ Error querying DataDog metrics: {str(e)}"

    @mcp.tool()
    async def datadog_dashboards_list() -> str:
        """DataDog Dashboards: List all dashboards."""
        logger.info("📊 Listing DataDog dashboards...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            dashboards_data = await client.list_dashboards()
            
            response = f"📊 **DATADOG DASHBOARDS**\n\n"
            response += f"📈 **Total Dashboards**: {dashboards_data['total_dashboards']}\n\n"
            
            if dashboards_data['dashboards']:
                for i, dashboard in enumerate(dashboards_data['dashboards'][:20], 1):
                    response += f"{i:2d}. **{dashboard['title']}**\n"
                    response += f"    ID: {dashboard['id']}\n"
                    response += f"    Author: {dashboard['author_handle']}\n"
                    if dashboard['description']:
                        desc = dashboard['description'][:100]
                        response += f"    Description: {desc}{'...' if len(dashboard['description']) > 100 else ''}\n"
                    response += "\n"
                
                if len(dashboards_data['dashboards']) > 20:
                    response += f"... and {len(dashboards_data['dashboards']) - 20} more dashboards\n"
            else:
                response += "📭 No dashboards found.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog dashboards listing failed: {e}", provider="datadog")
            return f"❌ Error listing DataDog dashboards: {str(e)}"

    @mcp.tool()
    async def datadog_usage_analysis(days: int = 30) -> str:
        """DataDog Usage: Analyze DataDog usage and costs over specified period."""
        logger.info(f"💰 Analyzing DataDog usage for {days} days...")
        
        try:
            client = datadog_provider.get_client("usage")
            
            # Set time range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            usage_data = await client.get_usage_metrics(start_date, end_date)
            
            response = f"💰 **DATADOG USAGE ANALYSIS**\n\n"
            response += f"📅 **Period**: {days} days\n\n"
            
            usage_metrics = usage_data.get('usage_metrics', {})
            
            response += "📊 **Usage Breakdown:**\n"
            for metric_name, value in usage_metrics.items():
                if value > 0:
                    display_name = metric_name.replace('_', ' ').title()
                    response += f"   • {display_name}: {value:,.0f}\n"
            
            response += "\n💡 **Optimization Recommendations:**\n"
            response += "• Review log retention policies to reduce storage costs\n"
            response += "• Optimize custom metrics to avoid duplicates\n"
            response += "• Set up usage alerts to monitor consumption\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog usage analysis failed: {e}", provider="datadog")
            return f"❌ Error analyzing DataDog usage: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_get_data(
        dashboard_id: str,
        time_range: str = "24h",
        organization_filter: Optional[str] = None
    ) -> str:
        """DataDog Dashboard Data: Retrieve actual data from dashboard widgets with optional organization filtering."""
        logger.info(f"📊 Retrieving data from DataDog dashboard: {dashboard_id} for {time_range}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            # First get the dashboard details to understand its structure
            dashboard = await client.get_dashboard(dashboard_id)
            
            response = f"📊 **DATADOG DASHBOARD DATA**\n\n"
            response += f"🎯 **Dashboard**: {dashboard['title']}\n"
            response += f"📋 **ID**: {dashboard['id']}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            if organization_filter:
                response += f"🏢 **Organization Filter**: {organization_filter}\n"
            response += f"📈 **Widgets**: {dashboard['widget_count']}\n\n"
            
            # Parse time range to datetime objects
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)  # default
            
            response += "📊 **Widget Data:**\n\n"
            
            for i, widget in enumerate(dashboard['widgets'][:10], 1):  # Limit to first 10 widgets
                widget_def = widget.get('definition', {})
                widget_type = widget_def.get('type', 'unknown')
                widget_title = widget_def.get('title', f'Widget {i}')
                
                response += f"**{i}. {widget_title}** ({widget_type})\n"
                
                # Handle group widgets with nested widgets
                if str(widget_type) == 'group':
                    # Try both possible keys for nested widgets
                    nested_widgets = widget_def.get('widgets', widget_def.get('nested_widgets', []))
                    response += f"   🔍 Debug: Found {len(nested_widgets)} nested widgets\n"
                    if nested_widgets:
                        response += f"   📊 Contains {len(nested_widgets)} nested widgets:\n"
                        for j, nested_widget in enumerate(nested_widgets[:5], 1):  # Limit to first 5 nested
                            nested_def = nested_widget.get('definition', {})
                            nested_type = nested_def.get('type', 'unknown')
                            nested_title = nested_def.get('title', f'Nested {j}')
                            
                            response += f"      {j}. {nested_title} ({nested_type})\n"
                            
                            # Process nested widget requests
                            nested_requests = nested_def.get('requests', [])
                            if nested_requests:
                                for k, request in enumerate(nested_requests[:2], 1):  # Limit to first 2 requests
                                    try:
                                        if isinstance(request, dict):
                                            query = request.get('q', request.get('query', ''))
                                            if query:
                                                # Apply organization filter
                                                filtered_query = query
                                                if organization_filter:
                                                    if '{' in query:
                                                        filtered_query = query.replace('{', f'{{org:{organization_filter},')
                                                    else:
                                                        metric_part = query.split('(')[0] if '(' in query else query
                                                        filtered_query = f"{metric_part}{{org:{organization_filter}}}"
                                                
                                                response += f"         Query {k}: {filtered_query}\n"
                                                
                                                # Try to get actual data
                                                try:
                                                    metric_name = query.split('(')[0].split('{')[0].strip()
                                                    if metric_name:
                                                        tags = []
                                                        if organization_filter:
                                                            tags.append(f"org:{organization_filter}")
                                                        
                                                        metrics_data = await client.get_metrics(
                                                            metric_name=metric_name,
                                                            start_time=start_time,
                                                            end_time=end_time,
                                                            tags=tags
                                                        )
                                                        
                                                        if metrics_data['series']:
                                                            series = metrics_data['series'][0]
                                                            if series['points']:
                                                                values = [point['value'] for point in series['points']]
                                                                total = sum(values)
                                                                avg = total / len(values)
                                                                latest = values[-1] if values else 0
                                                                
                                                                response += f"            📈 Latest: {latest:.2f}, Avg: {avg:.2f}, Total: {total:.2f}\n"
                                                            else:
                                                                response += f"            📭 No data points found\n"
                                                        else:
                                                            response += f"            📭 No series data found\n"
                                                except Exception as query_error:
                                                    response += f"            ⚠️ Could not retrieve data: {str(query_error)[:50]}...\n"
                                    except Exception as request_error:
                                        response += f"         Query {k}: Error processing - {str(request_error)[:50]}...\n"
                            else:
                                response += f"      No queries found in nested widget\n"
                    else:
                        response += "   No nested widgets found\n"
                else:
                    # Process regular widget requests to get data
                    requests = widget_def.get('requests', [])
                
                if requests and widget_type != 'group':
                    for j, request in enumerate(requests[:3], 1):  # Limit to first 3 requests per widget
                        try:
                            # Extract query information
                            if isinstance(request, dict):
                                query = request.get('q', request.get('query', ''))
                                if query:
                                    # Apply organization filter if specified
                                    filtered_query = query
                                    if organization_filter:
                                        # Add organization filter to the query
                                        if '{' in query:
                                            # Insert organization filter into existing tag filter
                                            filtered_query = query.replace('{', f'{{org:{organization_filter},')
                                        else:
                                            # Add organization filter as new tag filter
                                            metric_part = query.split('(')[0] if '(' in query else query
                                            filtered_query = f"{metric_part}{{org:{organization_filter}}}"
                                    
                                    response += f"   Query {j}: {filtered_query}\n"
                                    
                                    # Try to get actual data for this query
                                    try:
                                        # Extract metric name from query
                                        metric_name = query.split('(')[0].split('{')[0].strip()
                                        if metric_name:
                                            # Parse tags from query
                                            tags = []
                                            if organization_filter:
                                                tags.append(f"org:{organization_filter}")
                                            
                                            # Query the metric data
                                            metrics_data = await client.get_metrics(
                                                metric_name=metric_name,
                                                start_time=start_time,
                                                end_time=end_time,
                                                tags=tags
                                            )
                                            
                                            if metrics_data['series']:
                                                series = metrics_data['series'][0]  # Take first series
                                                if series['points']:
                                                    values = [point['value'] for point in series['points']]
                                                    total = sum(values)
                                                    avg = total / len(values)
                                                    latest = values[-1] if values else 0
                                                    
                                                    response += f"      📈 Latest: {latest:.2f}, Avg: {avg:.2f}, Total: {total:.2f}\n"
                                                    response += f"      📊 Data Points: {len(values)}\n"
                                                else:
                                                    response += f"      📭 No data points found\n"
                                            else:
                                                response += f"      📭 No series data found\n"
                                    except Exception as query_error:
                                        response += f"      ⚠️ Could not retrieve data: {str(query_error)[:50]}...\n"
                                else:
                                    response += f"   Query {j}: No query string found\n"
                            else:
                                response += f"   Query {j}: {str(request)[:100]}...\n"
                        except Exception as request_error:
                            response += f"   Query {j}: Error processing - {str(request_error)[:50]}...\n"
                else:
                    response += "   No requests found in widget\n"
                
                response += "\n"
            
            if len(dashboard['widgets']) > 10:
                response += f"... and {len(dashboard['widgets']) - 10} more widgets\n\n"
            
            response += "💡 **Next Steps:**\n"
            response += "• Use specific widget queries to get detailed cost breakdowns\n"
            response += "• Apply organization filters to focus on specific teams/projects\n"
            response += "• Extend time ranges for trend analysis\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog dashboard data retrieval failed: {e}", provider="datadog")
            return f"❌ Error retrieving DataDog dashboard data: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_query_widget(
        dashboard_id: str,
        widget_title: str,
        time_range: str = "24h",
        organization_filter: Optional[str] = None
    ) -> str:
        """DataDog Dashboard Widget: Query specific widget data from a dashboard."""
        logger.info(f"🎯 Querying widget '{widget_title}' from dashboard {dashboard_id}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            # Get dashboard details
            dashboard = await client.get_dashboard(dashboard_id)
            
            # Find the specific widget
            target_widget = None
            for widget in dashboard['widgets']:
                widget_def = widget.get('definition', {})
                if widget_def.get('title', '').lower() == widget_title.lower():
                    target_widget = widget
                    break
            
            if not target_widget:
                # Try partial match
                for widget in dashboard['widgets']:
                    widget_def = widget.get('definition', {})
                    widget_name = widget_def.get('title', '')
                    if widget_title.lower() in widget_name.lower():
                        target_widget = widget
                        break
            
            if not target_widget:
                available_widgets = [w.get('definition', {}).get('title', 'Untitled') for w in dashboard['widgets']]
                response = f"❌ Widget '{widget_title}' not found.\n\n"
                response += f"📋 Available widgets in '{dashboard['title']}':\n"
                for i, widget_name in enumerate(available_widgets, 1):
                    response += f"{i:2d}. {widget_name}\n"
                return response
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            widget_def = target_widget.get('definition', {})
            widget_type = widget_def.get('type', 'unknown')
            widget_title_actual = widget_def.get('title', widget_title)
            
            response = f"🎯 **DATADOG WIDGET DATA**\n\n"
            response += f"📊 **Widget**: {widget_title_actual}\n"
            response += f"📋 **Type**: {widget_type}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            if organization_filter:
                response += f"🏢 **Organization Filter**: {organization_filter}\n"
            response += "\n"
            
            # Process widget requests
            requests = widget_def.get('requests', [])
            if requests:
                response += "📈 **Data Results:**\n\n"
                
                for i, request in enumerate(requests, 1):
                    try:
                        if isinstance(request, dict):
                            query = request.get('q', request.get('query', ''))
                            if query:
                                # Apply organization filter
                                filtered_query = query
                                if organization_filter:
                                    if '{' in query:
                                        filtered_query = query.replace('{', f'{{org:{organization_filter},')
                                    else:
                                        metric_part = query.split('(')[0] if '(' in query else query
                                        filtered_query = f"{metric_part}{{org:{organization_filter}}}"
                                
                                response += f"**Query {i}**: {filtered_query}\n"
                                
                                # Get metric data
                                metric_name = query.split('(')[0].split('{')[0].strip()
                                if metric_name:
                                    tags = []
                                    if organization_filter:
                                        tags.append(f"org:{organization_filter}")
                                    
                                    metrics_data = await client.get_metrics(
                                        metric_name=metric_name,
                                        start_time=start_time,
                                        end_time=end_time,
                                        tags=tags
                                    )
                                    
                                    if metrics_data['series']:
                                        for j, series in enumerate(metrics_data['series'][:5], 1):
                                            response += f"  📊 **Series {j}**: {series['display_name'] or series['metric']}\n"
                                            response += f"     Tags: {', '.join(series['tags']) if series['tags'] else 'None'}\n"
                                            
                                            if series['points']:
                                                values = [point['value'] for point in series['points']]
                                                total = sum(values)
                                                avg = total / len(values)
                                                latest = values[-1]
                                                max_val = max(values)
                                                min_val = min(values)
                                                
                                                response += f"     📈 Latest: {latest:.2f}\n"
                                                response += f"     📊 Average: {avg:.2f}\n"
                                                response += f"     📊 Total: {total:.2f}\n"
                                                response += f"     📊 Min/Max: {min_val:.2f} / {max_val:.2f}\n"
                                                response += f"     📊 Data Points: {len(values)}\n"
                                            else:
                                                response += f"     📭 No data points\n"
                                            response += "\n"
                                    else:
                                        response += f"  📭 No data found for this query\n\n"
                    except Exception as request_error:
                        response += f"**Query {i}**: Error - {str(request_error)}\n\n"
            else:
                response += "📭 No queries found in this widget.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog widget query failed: {e}", provider="datadog")
            return f"❌ Error querying DataDog widget: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_explore_nested(
        dashboard_id: str,
        group_name: str,
        organization_filter: Optional[str] = None,
        time_range: str = "24h"
    ) -> str:
        """DataDog Dashboard Explorer: Explore nested widgets within a group widget for detailed cost data."""
        logger.info(f"🔍 Exploring nested widgets in group '{group_name}' from dashboard {dashboard_id}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            # Get dashboard details
            dashboard = await client.get_dashboard(dashboard_id)
            
            # Find the group widget
            target_group = None
            for widget in dashboard['widgets']:
                widget_def = widget.get('definition', {})
                if (widget_def.get('title', '').lower() == group_name.lower() and 
                    widget_def.get('type', '') == 'group'):
                    target_group = widget
                    break
            
            if not target_group:
                available_groups = []
                debug_info = []
                for widget in dashboard['widgets']:
                    widget_def = widget.get('definition', {})
                    widget_type = widget_def.get('type', 'unknown')
                    widget_title = widget_def.get('title', 'Untitled')
                    debug_info.append(f"Widget: '{widget_title}' (type: {widget_type})")
                    if str(widget_type) == 'group':
                        available_groups.append(widget_title)
                
                response = f"❌ Group '{group_name}' not found.\n\n"
                response += f"📋 Available groups in '{dashboard['title']}':\n"
                for i, group_name_available in enumerate(available_groups, 1):
                    response += f"{i:2d}. {group_name_available}\n"
                
                response += f"\n🔍 **Debug - All Widgets Found:**\n"
                for debug in debug_info:
                    response += f"   {debug}\n"
                
                return response
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            group_def = target_group.get('definition', {})
            # Try both possible keys for nested widgets
            nested_widgets = group_def.get('widgets', group_def.get('nested_widgets', []))
            
            response = f"🔍 **DATADOG GROUP WIDGET EXPLORATION**\n\n"
            response += f"📊 **Group**: {group_name}\n"
            response += f"📋 **Dashboard**: {dashboard['title']}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            if organization_filter:
                response += f"🏢 **Organization Filter**: {organization_filter}\n"
            response += f"📈 **Nested Widgets**: {len(nested_widgets)}\n\n"
            
            if nested_widgets:
                response += "🔍 **Nested Widget Details:**\n\n"
                
                for i, nested_widget in enumerate(nested_widgets, 1):
                    nested_def = nested_widget.get('definition', {})
                    nested_type = nested_def.get('type', 'unknown')
                    nested_title = nested_def.get('title', f'Widget {i}')
                    
                    response += f"**{i}. {nested_title}** ({nested_type})\n"
                    
                    # Process requests for cost data
                    nested_requests = nested_def.get('requests', [])
                    if nested_requests:
                        response += f"   📊 **Data Sources** ({len(nested_requests)} queries):\n"
                        
                        total_cost = 0
                        for j, request in enumerate(nested_requests, 1):
                            try:
                                if isinstance(request, dict):
                                    query = request.get('q', request.get('query', ''))
                                    if query:
                                        # Apply organization filter
                                        filtered_query = query
                                        if organization_filter:
                                            if '{' in query:
                                                filtered_query = query.replace('{', f'{{org:{organization_filter},')
                                            else:
                                                metric_part = query.split('(')[0] if '(' in query else query
                                                filtered_query = f"{metric_part}{{org:{organization_filter}}}"
                                        
                                        response += f"      **Query {j}**: {filtered_query}\n"
                                        
                                        # Get actual cost data
                                        try:
                                            metric_name = query.split('(')[0].split('{')[0].strip()
                                            if metric_name:
                                                tags = []
                                                if organization_filter:
                                                    tags.append(f"org:{organization_filter}")
                                                
                                                metrics_data = await client.get_metrics(
                                                    metric_name=metric_name,
                                                    start_time=start_time,
                                                    end_time=end_time,
                                                    tags=tags
                                                )
                                                
                                                if metrics_data['series']:
                                                    for k, series in enumerate(metrics_data['series'], 1):
                                                        if series['points']:
                                                            values = [point['value'] for point in series['points']]
                                                            total = sum(values)
                                                            avg = total / len(values)
                                                            latest = values[-1]
                                                            total_cost += total
                                                            
                                                            # Extract service name from tags if available
                                                            service = "Unknown"
                                                            for tag in series.get('tags', []):
                                                                if tag.startswith('service:'):
                                                                    service = tag.split(':', 1)[1]
                                                                    break
                                                            
                                                            response += f"         💰 **{service}**: Latest: ${latest:.2f}, Total: ${total:.2f}\n"
                                                            response += f"         📊 Tags: {', '.join(series.get('tags', [])[:3])}\n"
                                                        else:
                                                            response += f"         📭 No data points for series {k}\n"
                                                else:
                                                    response += f"         📭 No data found for this metric\n"
                                        except Exception as query_error:
                                            response += f"         ⚠️ Data retrieval error: {str(query_error)[:50]}...\n"
                            except Exception as request_error:
                                response += f"      **Query {j}**: Processing error - {str(request_error)[:50]}...\n"
                        
                        if total_cost > 0:
                            response += f"   💰 **Group Total Cost**: ${total_cost:.2f}\n"
                    else:
                        response += "   📭 No data queries found\n"
                    
                    response += "\n"
            else:
                response += "📭 No nested widgets found in this group.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog nested widget exploration failed: {e}", provider="datadog")
            return f"❌ Error exploring nested widgets: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_debug_structure(
        dashboard_id: str
    ) -> str:
        """DataDog Dashboard Debug: Show raw dashboard structure for debugging."""
        logger.info(f"🔍 Debugging dashboard structure for {dashboard_id}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            # Get raw dashboard details
            dashboard = await client.get_dashboard(dashboard_id)
            
            response = f"🔍 **DATADOG DASHBOARD DEBUG**\n\n"
            response += f"📊 **Dashboard**: {dashboard['title']}\n"
            response += f"📋 **ID**: {dashboard_id}\n"
            response += f"📈 **Total Widgets**: {len(dashboard['widgets'])}\n\n"
            
            # Show raw widget structure
            for i, widget in enumerate(dashboard['widgets'], 1):
                widget_def = widget.get('definition', {})
                widget_type = widget_def.get('type', 'unknown')
                widget_title = widget_def.get('title', f'Widget {i}')
                
                response += f"**Widget {i}: {widget_title}**\n"
                response += f"   Type: {widget_type}\n"
                response += f"   Definition keys: {list(widget_def.keys())}\n"
                
                # Show ALL keys and their types for debugging
                for key, value in widget_def.items():
                    if key not in ['type', 'title']:
                        if isinstance(value, list):
                            response += f"   {key}: list[{len(value)}] = {[type(item).__name__ for item in value[:3]]}\n"
                        elif isinstance(value, dict):
                            response += f"   {key}: dict with keys = {list(value.keys())[:5]}\n"
                        else:
                            response += f"   {key}: {type(value).__name__} = {str(value)[:50]}...\n"
                
                # Show requests if any
                requests = widget_def.get('requests', [])
                if requests:
                    response += f"   Requests: {len(requests)}\n"
                    for j, request in enumerate(requests[:2], 1):
                        if isinstance(request, dict):
                            response += f"      Request {j}: {list(request.keys())}\n"
                            query = request.get('q', request.get('query', ''))
                            if query:
                                response += f"         Query: {query[:100]}...\n"
                        else:
                            response += f"      Request {j}: {type(request)} - {str(request)[:100]}...\n"
                else:
                    response += f"   No requests found\n"
                
                # Show nested widgets for groups
                if str(widget_type) == 'group':
                    nested_widgets = widget_def.get('widgets', [])  # Try 'widgets' instead of 'nested_widgets'
                    response += f"   Nested widgets (widgets key): {len(nested_widgets)}\n"
                    
                    # Also check for other possible keys
                    for key in widget_def.keys():
                        if 'widget' in key.lower():
                            value = widget_def.get(key, [])
                            if isinstance(value, list):
                                response += f"   Found widget list '{key}': {len(value)} items\n"
                
                response += "\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog dashboard debug failed: {e}", provider="datadog")
            return f"❌ Error debugging dashboard: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_raw_data(
        dashboard_id: str,
        organization_filter: Optional[str] = None
    ) -> str:
        """DataDog Dashboard Raw Data: Extract data using alternative parsing approach."""
        logger.info(f"🔍 Attempting raw data extraction from dashboard {dashboard_id}...")
        
        try:
            datadog_provider = provider_manager.get_provider("datadog")
            if not datadog_provider:
                return "❌ DataDog provider not available"
            
            # Get the raw dashboard API client
            client = datadog_provider.get_client("dashboards")
            
            # Try to get the dashboard using the raw API
            response = await client.get_dashboard(dashboard_id)
            
            output = f"🔍 **RAW DASHBOARD DATA EXTRACTION**\n\n"
            output += f"📊 **Dashboard**: {response.get('title', 'Unknown')}\n"
            output += f"📋 **ID**: {dashboard_id}\n"
            
            # Try alternative approaches to find data
            widgets = response.get('widgets', [])
            output += f"📈 **Total Widgets**: {len(widgets)}\n\n"
            
            # Look for template variables that might contain the org filter
            template_vars = response.get('template_variables', [])
            if template_vars:
                output += f"🔧 **Template Variables**: {len(template_vars)}\n"
                for var in template_vars:
                    if isinstance(var, dict):
                        name = var.get('name', 'Unknown')
                        default = var.get('default', 'None')
                        output += f"   - {name}: {default}\n"
                output += "\n"
            
            # Try to find metrics by searching for common cost patterns
            cost_metrics_found = []
            
            # Look through all widgets for any data, including non-group widgets
            for i, widget in enumerate(widgets, 1):
                widget_def = widget.get('definition', {})
                widget_type = widget_def.get('type', 'unknown')
                widget_title = widget_def.get('title', f'Widget {i}')
                
                output += f"**Widget {i}: {widget_title}** ({widget_type})\n"
                
                # Check for any metrics in requests
                requests = widget_def.get('requests', [])
                if requests:
                    output += f"   📊 Found {len(requests)} requests:\n"
                    
                    for j, request in enumerate(requests, 1):
                        if isinstance(request, dict):
                            # Look for different query patterns
                            for query_field in ['q', 'query', 'metric_query', 'log_query']:
                                query = request.get(query_field, '')
                                if query:
                                    # Apply organization filter if specified
                                    filtered_query = query
                                    if organization_filter:
                                        if '{' in query:
                                            filtered_query = query.replace('{', f'{{org:{organization_filter},')
                                        else:
                                            filtered_query = f"{query}{{org:{organization_filter}}}"
                                    
                                    output += f"      Request {j} ({query_field}): {filtered_query}\n"
                                    
                                    # Try to extract cost data if this looks like a cost metric
                                    if any(cost_term in query.lower() for cost_term in ['cost', 'billing', 'usage', 'spend']):
                                        cost_metrics_found.append({
                                            'widget': widget_title,
                                            'query': filtered_query,
                                            'type': query_field
                                        })
                            
                            # Check for formulas (newer DataDog query format)
                            formulas = request.get('formulas', [])
                            if formulas:
                                output += f"      Formulas ({len(formulas)}): {formulas}\n"
                            
                            queries = request.get('queries', [])
                            if queries:
                                output += f"      Queries ({len(queries)}): {queries}\n"
                
                output += "\n"
            
            # Try to execute cost metrics found
            if cost_metrics_found:
                output += f"💰 **COST METRICS FOUND**: {len(cost_metrics_found)}\n\n"
                
                total_cost = 0
                for metric in cost_metrics_found:
                    try:
                        output += f"**{metric['widget']}**:\n"
                        output += f"   Query: {metric['query']}\n"
                        
                        # Try to extract and query the metric
                        metric_name = metric['query'].split('(')[0].split('{')[0].strip()
                        if metric_name and organization_filter:
                            # Use metrics client to get actual data
                            metrics_client = datadog_provider.get_client("metrics")
                            end_time = datetime.now()
                            start_time = end_time - timedelta(hours=24)
                            
                            try:
                                metrics_data = await metrics_client.get_metrics(
                                    metric_name=metric_name,
                                    start_time=start_time,
                                    end_time=end_time,
                                    tags=[f"org:{organization_filter}"]
                                )
                                
                                if metrics_data['series']:
                                    for series in metrics_data['series']:
                                        if series['points']:
                                            values = [point['value'] for point in series['points']]
                                            latest = values[-1] if values else 0
                                            total = sum(values)
                                            total_cost += total
                                            
                                            # Get service info from tags
                                            service = "Unknown"
                                            for tag in series.get('tags', []):
                                                if tag.startswith('service:'):
                                                    service = tag.split(':', 1)[1]
                                                    break
                                            
                                            output += f"   💰 {service}: Latest: ${latest:.2f}, Total: ${total:.2f}\n"
                                            output += f"   📊 Tags: {', '.join(series.get('tags', [])[:3])}\n"
                                else:
                                    output += f"   📭 No data found\n"
                            except Exception as query_error:
                                output += f"   ⚠️ Query failed: {str(query_error)[:50]}...\n"
                        
                        output += "\n"
                    except Exception as metric_error:
                        output += f"   ❌ Error processing metric: {str(metric_error)[:50]}...\n"
                
                if total_cost > 0:
                    output += f"💰 **TOTAL COST for {organization_filter}**: ${total_cost:.2f}\n"
            else:
                output += "📭 No cost metrics found in dashboard widgets\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Raw dashboard data extraction failed: {e}", provider="datadog")
            return f"❌ Error extracting raw dashboard data: {str(e)}"

    @mcp.tool()
    async def datadog_search_cost_metrics(
        organization_filter: str = "b38uat",
        time_range: str = "24h"
    ) -> str:
        """DataDog Metrics Discovery: Search for cost-related metrics in the environment."""
        logger.info(f"🔍 Searching for cost metrics with organization filter {organization_filter}...")
        
        try:
            datadog_provider = provider_manager.get_provider("datadog")
            if not datadog_provider:
                return "❌ DataDog provider not available"
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            else:
                start_time = end_time - timedelta(hours=24)
            
            output = f"🔍 **DATADOG COST METRICS DISCOVERY**\n\n"
            output += f"🏢 **Organization**: {organization_filter}\n"
            output += f"⏰ **Time Range**: {time_range}\n\n"
            
            # List of common cost-related metric patterns
            cost_metric_patterns = [
                "aws.cost",
                "aws.billing", 
                "cost.allocation",
                "billing.cost",
                "usage.cost",
                "spend",
                "charge",
                "aws.estimated_charges",
                "cloudcost",
                "finops"
            ]
            
            metrics_client = datadog_provider.get_client("metrics")
            total_found = 0
            total_cost = 0
            
            output += "🔍 **SEARCHING COMMON COST METRICS**:\n\n"
            
            for pattern in cost_metric_patterns:
                try:
                    output += f"**{pattern}**:\n"
                    
                    # Try different tag combinations
                    tag_variations = [
                        [f"org:{organization_filter}"],
                        [f"organization:{organization_filter}"],
                        [f"env:{organization_filter}"],
                        [f"environment:{organization_filter}"],
                        [f"team:{organization_filter}"],
                        [f"project:{organization_filter}"]
                    ]
                    
                    found_data = False
                    
                    for tags in tag_variations:
                        try:
                            metrics_data = await metrics_client.get_metrics(
                                metric_name=pattern,
                                start_time=start_time,
                                end_time=end_time,
                                tags=tags
                            )
                            
                            if metrics_data['series']:
                                found_data = True
                                output += f"   ✅ Found data with tags: {', '.join(tags)}\n"
                                
                                for series in metrics_data['series']:
                                    if series['points']:
                                        values = [point['value'] for point in series['points']]
                                        latest = values[-1] if values else 0
                                        total = sum(values)
                                        total_cost += total
                                        total_found += 1
                                        
                                        # Extract service/resource info
                                        service = "Unknown"
                                        resource = "Unknown"
                                        
                                        for tag in series.get('tags', []):
                                            if tag.startswith('service:'):
                                                service = tag.split(':', 1)[1]
                                            elif tag.startswith('resource:'):
                                                resource = tag.split(':', 1)[1]
                                            elif tag.startswith('name:'):
                                                resource = tag.split(':', 1)[1]
                                        
                                        output += f"      💰 {service}/{resource}: ${latest:.2f} (total: ${total:.2f})\n"
                                        output += f"         📊 Tags: {', '.join(series.get('tags', [])[:4])}\n"
                                
                                break  # Found data with this tag pattern, move to next metric
                        
                        except Exception as tag_error:
                            continue  # Try next tag variation
                    
                    if not found_data:
                        output += f"   📭 No data found\n"
                    
                    output += "\n"
                    
                except Exception as pattern_error:
                    output += f"   ⚠️ Error searching {pattern}: {str(pattern_error)[:50]}...\n\n"
            
            # Also try log-based metrics which might be used for cost allocation
            output += "📊 **SEARCHING LOG-BASED COST METRICS**:\n\n"
            
            logs_client = datadog_provider.get_client("logs")
            
            # Common log queries for cost allocation
            log_queries = [
                f"@org:{organization_filter} cost",
                f"@organization:{organization_filter} billing",
                f"@env:{organization_filter} spend",
                f"service:* @organization:{organization_filter}",
                f"@{organization_filter} aws cost"
            ]
            
            for query in log_queries:
                try:
                    output += f"**Log Query**: {query}\n"
                    
                    logs_data = await logs_client.search_logs_aggregated(
                        query=query,
                        start_time=start_time,
                        end_time=end_time,
                        aggregation="count"
                    )
                    
                    if logs_data.get('total_count', 0) > 0:
                        output += f"   ✅ Found {logs_data['total_count']} log entries\n"
                        
                        # Try to extract cost information from logs
                        logs_search = await logs_client.get_logs(
                            query=query,
                            start_time=start_time,
                            end_time=end_time,
                            limit=5
                        )
                        
                        if logs_search.get('logs'):
                            for log in logs_search['logs'][:3]:
                                message = log.get('message', '')
                                attributes = log.get('attributes', {})
                                
                                # Look for cost values in message or attributes
                                import re
                                cost_match = re.search(r'\$?([0-9]+\.?[0-9]*)', message)
                                if cost_match:
                                    cost_value = float(cost_match.group(1))
                                    total_cost += cost_value
                                    output += f"      💰 Cost found: ${cost_value:.2f}\n"
                                
                                # Show relevant attributes
                                for key, value in attributes.items():
                                    if any(term in key.lower() for term in ['cost', 'billing', 'service', 'resource']):
                                        output += f"      📊 {key}: {value}\n"
                    else:
                        output += f"   📭 No log entries found\n"
                    
                    output += "\n"
                    
                except Exception as log_error:
                    output += f"   ⚠️ Log search error: {str(log_error)[:50]}...\n\n"
            
            # Summary
            output += f"📋 **SUMMARY**:\n"
            output += f"   🔢 Total metrics found: {total_found}\n"
            output += f"   💰 Total cost detected: ${total_cost:.2f}\n"
            
            if total_found == 0:
                output += f"\n❌ **No cost metrics found for {organization_filter}**\n"
                output += f"💡 **Suggestions**:\n"
                output += f"   • Check if organization tag is '{organization_filter}' or different\n"
                output += f"   • Verify custom metrics are being sent to DataDog\n"
                output += f"   • Dashboard might use calculated fields or formulas\n"
                output += f"   • Cost data might be in logs rather than metrics\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Cost metrics search failed: {e}", provider="datadog")
            return f"❌ Error searching cost metrics: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_get_live_data(
        dashboard_id: str,
        organization_filter: Optional[str] = None,
        time_range: str = "24h"
    ) -> str:
        """DataDog Dashboard Live Data: Get data using template variables and live mode like the web interface."""
        logger.info(f"🔍 Getting live dashboard data for {dashboard_id} with template variables...")
        
        try:
            datadog_provider = provider_manager.get_provider("datadog")
            if not datadog_provider:
                return "❌ DataDog provider not available"
            
            # Parse time range to timestamps like the dashboard URL
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            # Convert to timestamps (milliseconds like dashboard URL)
            from_ts = int(start_time.timestamp() * 1000)
            to_ts = int(end_time.timestamp() * 1000)
            
            client = datadog_provider.get_client("dashboards")
            
            # Get dashboard definition first
            dashboard = await client.get_dashboard(dashboard_id)
            
            response = f"🔍 **DATADOG LIVE DASHBOARD DATA**\n\n"
            response += f"📊 **Dashboard**: {dashboard['title']}\n"
            response += f"📋 **ID**: {dashboard_id}\n"
            response += f"⏰ **Time Range**: {time_range} ({from_ts} to {to_ts})\n"
            response += f"🔴 **Live Mode**: true\n"
            if organization_filter:
                response += f"🏢 **Template Variable**: tpl_var_organization[0]={organization_filter}\n"
            response += "\n"
            
            # Look for template variables
            template_vars = dashboard.get('template_variables', [])
            if template_vars:
                response += f"🔧 **Available Template Variables**:\n"
                for var in template_vars:
                    if isinstance(var, dict):
                        name = var.get('name', 'Unknown')
                        default = var.get('default', 'None')
                        available_values = var.get('available_values', [])
                        response += f"   - {name}: default={default}\n"
                        if available_values:
                            response += f"     Available: {', '.join(available_values[:5])}\n"
                response += "\n"
            
            # Try to get widget data using template variable format
            widgets = dashboard.get('widgets', [])
            total_cost = 0
            metrics_found = 0
            
            response += f"📊 **WIDGET DATA WITH TEMPLATE VARIABLES**:\n\n"
            
            metrics_client = datadog_provider.get_client("metrics")
            
            for i, widget in enumerate(widgets[:8], 1):  # Process all 8 widgets
                widget_def = widget.get('definition', {})
                widget_type = widget_def.get('type', 'unknown')
                widget_title = widget_def.get('title', f'Widget {i}')
                
                response += f"**{i}. {widget_title}** ({widget_type})\n"
                
                # Process requests with template variable substitution
                requests = widget_def.get('requests', [])
                if requests:
                    response += f"   📊 Processing {len(requests)} requests:\n"
                    
                    for j, request in enumerate(requests, 1):
                        if isinstance(request, dict):
                            # Look for queries in different formats
                            for query_field in ['q', 'query', 'metric_query', 'log_query']:
                                query = request.get(query_field, '')
                                if query:
                                    # Apply template variable substitution like the dashboard does
                                    processed_query = query
                                    
                                    # Replace template variables with actual values
                                    if organization_filter:
                                        # Handle template variable patterns
                                        processed_query = processed_query.replace('$tpl_var_organization', organization_filter)
                                        processed_query = processed_query.replace('${tpl_var_organization}', organization_filter)
                                        processed_query = processed_query.replace('$organization', organization_filter)
                                        processed_query = processed_query.replace('${organization}', organization_filter)
                                        
                                        # Also add as tag filter if not present
                                        if '{' in processed_query and f'organization:{organization_filter}' not in processed_query:
                                            processed_query = processed_query.replace('{', f'{{organization:{organization_filter},')
                                        elif '{' not in processed_query:
                                            processed_query = f"{processed_query}{{organization:{organization_filter}}}"
                                    
                                    response += f"      **Request {j}** ({query_field}):\n"
                                    response += f"         Original: {query}\n"
                                    response += f"         Processed: {processed_query}\n"
                                    
                                    # Execute the query with live data timestamps
                                    try:
                                        metric_name = processed_query.split('(')[0].split('{')[0].strip()
                                        if metric_name:
                                            # Extract tags from query
                                            tags = []
                                            if '{' in processed_query:
                                                tag_part = processed_query.split('{')[1].split('}')[0]
                                                for tag in tag_part.split(','):
                                                    tag = tag.strip()
                                                    if tag:
                                                        tags.append(tag)
                                            
                                            # Get metrics data using live timestamps
                                            metrics_data = await metrics_client.get_metrics(
                                                metric_name=metric_name,
                                                start_time=start_time,
                                                end_time=end_time,
                                                tags=tags
                                            )
                                            
                                            if metrics_data['series']:
                                                metrics_found += 1
                                                response += f"         ✅ **Data Found**: {len(metrics_data['series'])} series\n"
                                                
                                                for k, series in enumerate(metrics_data['series'][:3], 1):
                                                    if series['points']:
                                                        values = [point['value'] for point in series['points']]
                                                        latest = values[-1] if values else 0
                                                        total = sum(values)
                                                        avg = total / len(values) if values else 0
                                                        total_cost += total
                                                        
                                                        # Extract service info
                                                        service = "Unknown"
                                                        for tag in series.get('tags', []):
                                                            if tag.startswith('service:'):
                                                                service = tag.split(':', 1)[1]
                                                                break
                                                            elif tag.startswith('name:'):
                                                                service = tag.split(':', 1)[1]
                                                                break
                                                        
                                                        response += f"            💰 **{service}**: Latest=${latest:.2f}, Avg=${avg:.2f}, Total=${total:.2f}\n"
                                                        response += f"            📊 Points: {len(values)}, Tags: {', '.join(series.get('tags', [])[:3])}\n"
                                                    else:
                                                        response += f"            📭 Series {k}: No data points\n"
                                            else:
                                                response += f"         📭 No data series found\n"
                                        else:
                                            response += f"         ⚠️ Could not extract metric name\n"
                                    except Exception as query_error:
                                        response += f"         ❌ Query failed: {str(query_error)[:60]}...\n"
                            
                            # Check for formulas (newer DataDog format)
                            formulas = request.get('formulas', [])
                            if formulas:
                                response += f"      **Formulas**: {formulas}\n"
                            
                            queries = request.get('queries', [])
                            if queries:
                                response += f"      **Sub-queries**: {len(queries)} found\n"
                                for sub_query in queries[:2]:
                                    if isinstance(sub_query, dict):
                                        data_source = sub_query.get('data_source', 'metrics')
                                        query_str = sub_query.get('query', '')
                                        response += f"         {data_source}: {query_str}\n"
                else:
                    response += f"   📭 No requests found\n"
                
                response += "\n"
            
            # Summary
            response += f"📋 **SUMMARY**:\n"
            response += f"   🔢 Metrics found: {metrics_found}\n"
            response += f"   💰 Total cost: ${total_cost:.2f}\n"
            
            if metrics_found == 0:
                response += f"\n💡 **Troubleshooting**:\n"
                response += f"   • Try different organization values: '{organization_filter}'\n"
                response += f"   • Check template variable names in dashboard\n"
                response += f"   • Verify live data is available for this time range\n"
                response += f"   • Dashboard might use log-based metrics or custom calculations\n"
            else:
                response += f"\n✅ **Success**: Found cost data for {organization_filter}!\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Live dashboard data retrieval failed: {e}", provider="datadog")
            return f"❌ Error getting live dashboard data: {str(e)}"

    @mcp.tool()
    async def datadog_diagnose_dashboard_issue(
        dashboard_id: str = "csc-fuy-ae8"
    ) -> str:
        """DataDog Dashboard Diagnosis: Deep analysis of why dashboard data isn't accessible via API."""
        logger.info(f"🔍 Diagnosing dashboard access issue for {dashboard_id}...")
        
        try:
            datadog_provider = provider_manager.get_provider("datadog")
            if not datadog_provider:
                return "❌ DataDog provider not available"
            
            output = f"🔬 **DATADOG DASHBOARD DIAGNOSIS**\n\n"
            output += f"📊 **Dashboard ID**: {dashboard_id}\n"
            output += f"🎯 **Goal**: Understand why cost data isn't accessible via API\n\n"
            
            # Get dashboard details
            client = datadog_provider.get_client("dashboards")
            dashboard = await client.get_dashboard(dashboard_id)
            
            output += f"✅ **Dashboard Found**: {dashboard['title']}\n"
            output += f"📅 **Created**: {dashboard.get('created_at', 'Unknown')}\n"
            output += f"👤 **Author**: {dashboard.get('author_handle', 'Unknown')}\n\n"
            
            # Analyze template variables
            template_vars = dashboard.get('template_variables', [])
            output += f"🔧 **Template Variables Analysis**:\n"
            if template_vars:
                for var in template_vars:
                    if isinstance(var, dict):
                        name = var.get('name', 'Unknown')
                        prefix = var.get('prefix', '')
                        default = var.get('default', '')
                        available_values = var.get('available_values', [])
                        
                        output += f"   **{name}**:\n"
                        output += f"      Prefix: '{prefix}'\n"
                        output += f"      Default: '{default}'\n"
                        output += f"      Available values: {len(available_values)} items\n"
                        if available_values:
                            output += f"      Sample values: {', '.join(str(v) for v in available_values[:3])}\n"
                        output += f"\n"
            else:
                output += "   No template variables found\n\n"
            
            # Deep widget analysis
            widgets = dashboard.get('widgets', [])
            output += f"📊 **Widget Deep Analysis** ({len(widgets)} widgets):\n\n"
            
            for i, widget in enumerate(widgets, 1):
                widget_id = widget.get('id', f'widget-{i}')
                widget_def = widget.get('definition', {})
                widget_type = widget_def.get('type', 'unknown')
                widget_title = widget_def.get('title', f'Widget {i}')
                
                output += f"**Widget {i}: {widget_title}**\n"
                output += f"   ID: {widget_id}\n"
                output += f"   Type: {widget_type}\n"
                
                # Analyze all properties
                output += f"   Definition keys: {list(widget_def.keys())}\n"
                
                # Check layout information
                layout = widget.get('layout', {})
                if layout:
                    output += f"   Layout: {layout}\n"
                
                # Deep dive into definition properties
                for key, value in widget_def.items():
                    if key in ['title', 'type']:
                        continue
                    
                    if isinstance(value, list):
                        output += f"   {key}: [{len(value)} items]\n"
                        if value and len(value) > 0:
                            first_item = value[0]
                            if isinstance(first_item, dict):
                                output += f"      First item keys: {list(first_item.keys())}\n"
                                # Look for query-like structures
                                for sub_key, sub_value in first_item.items():
                                    if any(term in sub_key.lower() for term in ['query', 'metric', 'formula', 'request']):
                                        output += f"         {sub_key}: {str(sub_value)[:80]}...\n"
                            else:
                                output += f"      First item: {str(first_item)[:50]}...\n"
                    elif isinstance(value, dict):
                        output += f"   {key}: dict with {len(value)} keys\n"
                        if value:
                            output += f"      Keys: {list(value.keys())}\n"
                    else:
                        output += f"   {key}: {str(value)[:60]}...\n"
                
                output += "\n"
            
            # Test alternative data sources
            output += f"🔍 **Alternative Data Source Analysis**:\n\n"
            
            # Check if dashboard might use external data
            external_indicators = []
            
            for widget in widgets:
                widget_def = widget.get('definition', {})
                
                # Look for external data indicators
                widget_str = str(widget_def).lower()
                if any(term in widget_str for term in ['aws', 'cost', 'billing', 'cloudformation', 'external']):
                    external_indicators.append({
                        'widget': widget_def.get('title', 'Unknown'),
                        'type': widget_def.get('type', 'unknown'),
                        'indicators': [term for term in ['aws', 'cost', 'billing', 'cloudformation', 'external'] if term in widget_str]
                    })
            
            if external_indicators:
                output += f"🔗 **External Data Indicators Found**:\n"
                for indicator in external_indicators:
                    output += f"   {indicator['widget']} ({indicator['type']}): {', '.join(indicator['indicators'])}\n"
            else:
                output += f"📭 No external data indicators found\n"
            
            output += f"\n"
            
            # Possible explanations
            output += f"💡 **Possible Explanations for Missing Data**:\n\n"
            output += f"1. **Custom Integration**: Dashboard uses custom AWS Cost Explorer integration\n"
            output += f"   - Cost data pulled directly from AWS billing APIs\n"
            output += f"   - Not stored as standard DataDog metrics\n\n"
            
            output += f"2. **Calculated Fields**: Widgets use complex formulas or transformations\n"
            output += f"   - Data processed client-side in dashboard\n"
            output += f"   - Not accessible via standard metrics API\n\n"
            
            output += f"3. **External Data Sources**: Dashboard pulls from external systems\n"
            output += f"   - AWS Cost and Billing APIs\n"
            output += f"   - Custom FinOps tools\n"
            output += f"   - Third-party cost management platforms\n\n"
            
            output += f"4. **Log-Based Calculations**: Cost data derived from logs\n"
            output += f"   - CloudTrail billing events\n"
            output += f"   - Application cost tracking logs\n"
            output += f"   - Custom cost allocation logs\n\n"
            
            output += f"5. **Dashboard-Specific APIs**: Uses internal DataDog APIs\n"
            output += f"   - Dashboard rendering APIs\n"
            output += f"   - Not exposed in public metrics APIs\n\n"
            
            # Recommendations
            output += f"🎯 **Recommendations**:\n\n"
            output += f"1. **Use AWS Cost Explorer directly**: Get b38uat costs from AWS APIs\n"
            output += f"2. **Check DataDog Logs**: Search for cost allocation log entries\n"
            output += f"3. **Dashboard Export**: Try exporting dashboard data manually\n"
            output += f"4. **Alternative Metrics**: Search for AWS-specific cost metrics\n"
            output += f"5. **Contact DataDog Support**: Ask about dashboard data access patterns\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Dashboard diagnosis failed: {e}", provider="datadog")
            return f"❌ Error diagnosing dashboard: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_get_actual_data(
        dashboard_id: str,
        organization_filter: Optional[str] = None,
        time_range: str = "24h"
    ) -> str:
        """DataDog Dashboard Actual Data: Get real data using the same API the web interface uses."""
        logger.info(f"🔍 Getting actual dashboard data using web interface API for {dashboard_id}...")
        
        try:
            datadog_provider = provider_manager.get_provider("datadog")
            if not datadog_provider:
                return "❌ DataDog provider not available"
            
            # Parse time range to timestamps
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            # Convert to millisecond timestamps like the web interface
            from_ts = int(start_time.timestamp() * 1000)
            to_ts = int(end_time.timestamp() * 1000)
            
            client = datadog_provider.get_client("dashboards")
            
            # Prepare template variables
            template_vars = {}
            if organization_filter:
                template_vars['organization'] = organization_filter
            
            # Get actual dashboard data using the web interface API
            dashboard_data = await client.get_dashboard_data(
                dashboard_id=dashboard_id,
                template_variables=template_vars,
                from_ts=from_ts,
                to_ts=to_ts
            )
            
            response = f"🔍 **DATADOG ACTUAL DASHBOARD DATA**\n\n"
            response += f"📊 **Dashboard ID**: {dashboard_id}\n"
            response += f"⏰ **Time Range**: {time_range} ({from_ts} to {to_ts})\n"
            response += f"🔴 **Live Mode**: true\n"
            response += f"🔄 **Refresh Mode**: sliding\n"
            if organization_filter:
                response += f"🏢 **Organization Filter**: {organization_filter}\n"
            response += "\n"
            
            # Check if we got an error
            if 'error' in dashboard_data:
                response += f"❌ **API Error**: {dashboard_data['error']}\n"
                response += f"🔗 **URL**: {dashboard_data.get('url', 'Unknown')}\n"
                response += f"📋 **Params**: {dashboard_data.get('params', {})}\n"
                response += f"📄 **Response**: {dashboard_data.get('response_text', 'No response text')}\n"
                return response
            
            # Process the actual data response
            response += f"✅ **Data Retrieved Successfully**\n"
            response += f"📊 **Response Keys**: {list(dashboard_data.keys())}\n\n"
            
            # Look for widget data
            widgets_data = dashboard_data.get('widgets', dashboard_data.get('data', dashboard_data.get('series', [])))
            
            if widgets_data:
                response += f"📈 **Widget Data Found** ({len(widgets_data)} items):\n\n"
                
                total_cost = 0
                cost_breakdown = {}
                
                for i, widget_data in enumerate(widgets_data, 1):
                    if isinstance(widget_data, dict):
                        widget_title = widget_data.get('title', f'Widget {i}')
                        widget_id = widget_data.get('id', f'widget-{i}')
                        
                        response += f"**{i}. {widget_title}**\n"
                        response += f"   ID: {widget_id}\n"
                        
                        # Look for series data (cost values)
                        series = widget_data.get('series', widget_data.get('data', []))
                        if series:
                            response += f"   📊 Series: {len(series)} datasets\n"
                            
                            for j, serie in enumerate(series[:5], 1):  # Limit to first 5 series
                                if isinstance(serie, dict):
                                    # Extract cost information
                                    values = serie.get('values', serie.get('points', []))
                                    metric = serie.get('metric', serie.get('name', f'Series {j}'))
                                    tags = serie.get('tags', [])
                                    
                                    if values:
                                        # Calculate cost metrics
                                        if isinstance(values[0], list):  # [[timestamp, value], ...]
                                            cost_values = [point[1] for point in values if len(point) > 1]
                                        else:  # [value1, value2, ...]
                                            cost_values = values
                                        
                                        if cost_values:
                                            latest = cost_values[-1] if cost_values else 0
                                            total = sum(cost_values)
                                            avg = total / len(cost_values)
                                            total_cost += total
                                            
                                            # Extract service name
                                            service = metric
                                            for tag in tags:
                                                if isinstance(tag, str):
                                                    if tag.startswith('service:'):
                                                        service = tag.split(':', 1)[1]
                                                        break
                                                    elif tag.startswith('name:'):
                                                        service = tag.split(':', 1)[1]
                                                        break
                                            
                                            cost_breakdown[service] = {
                                                'latest': latest,
                                                'total': total,
                                                'avg': avg,
                                                'points': len(cost_values)
                                            }
                                            
                                            response += f"      💰 **{service}**: Latest=${latest:.2f}, Total=${total:.2f}, Avg=${avg:.2f}\n"
                                            response += f"      📊 Points: {len(cost_values)}, Tags: {tags[:3]}\n"
                                    else:
                                        response += f"      📭 No values in series {j}\n"
                        else:
                            response += f"   📭 No series data\n"
                        
                        # Look for other data structures
                        for key, value in widget_data.items():
                            if key not in ['title', 'id', 'series', 'data'] and isinstance(value, (list, dict)):
                                response += f"   {key}: {type(value).__name__} with {len(value) if hasattr(value, '__len__') else 'unknown'} items\n"
                        
                        response += "\n"
                
                # Summary
                response += f"💰 **COST BREAKDOWN FOR {organization_filter.upper()}**:\n\n"
                
                if cost_breakdown:
                    # Sort by total cost descending
                    sorted_costs = sorted(cost_breakdown.items(), key=lambda x: x[1]['total'], reverse=True)
                    
                    for service, costs in sorted_costs:
                        response += f"**{service}**: ${costs['total']:.2f} total (${costs['latest']:.2f} latest)\n"
                    
                    response += f"\n🔢 **Total Cost**: ${total_cost:.2f}\n"
                    response += f"📊 **Services**: {len(cost_breakdown)}\n"
                else:
                    response += "📭 No cost data found in widgets\n"
                    
            else:
                response += f"📭 No widget data found in response\n"
                response += f"🔍 **Raw Response Structure**: {str(dashboard_data)[:500]}...\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Dashboard actual data retrieval failed: {e}", provider="datadog")
            return f"❌ Error getting actual dashboard data: {str(e)}"

    @mcp.tool()
    async def datadog_discover_cost_metrics(
        search_pattern: str = "cost",
        organization_filter: Optional[str] = None,
        time_range: str = "24h"
    ) -> str:
        """DataDog Cost Metrics Discovery: Find all available cost-related metrics in your DataDog account."""
        logger.info(f"🔍 Discovering DataDog cost metrics with pattern: {search_pattern}...")
        
        try:
            metrics_client = datadog_provider.get_client("metrics")
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            response = f"🔍 **DATADOG COST METRICS DISCOVERY**\n\n"
            response += f"🎯 **Search Pattern**: {search_pattern}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            if organization_filter:
                response += f"🏢 **Organization Filter**: {organization_filter}\n"
            response += "\n"
            
            discovered_metrics = []
            total_tested = 0
            
            # Comprehensive search patterns for cost-related metrics
            search_patterns = [search_pattern]
            if search_pattern == "cost":
                search_patterns.extend(['billing', 'expense', 'spend', 'price', 'charge'])
            
            # Common service prefixes to test
            service_prefixes = [
                'datawarehouse', 'analytics', 'treasury', 'carma', 'whatif',
                'compute', 'storage', 'network', 'database', 'lambda', 'function',
                'ec2', 'rds', 's3', 'cloudfront', 'elb', 'api_gateway', 'dynamodb',
                'application', 'service', 'infrastructure', 'platform', 'system',
                'aws', 'gcp', 'azure', 'cloud', 'container', 'kubernetes', 'docker'
            ]
            
            # Metric aggregation functions
            aggregations = ['sum', 'avg', 'max', 'min', 'count']
            
            response += "🔍 **Searching for Cost Metrics**:\n\n"
            
            for pattern in search_patterns:
                response += f"**Pattern: '{pattern}'**\n"
                
                # Test different metric structures
                metric_structures = [
                    f"*.organization.{pattern}",
                    f"*.{pattern}",
                    f"{pattern}.*",
                    f"*.*.{pattern}",
                    f"{pattern}.organization.*",
                    f"organization.{pattern}.*"
                ]
                
                for structure in metric_structures:
                    for agg in aggregations:
                        # Build metric query
                        base_metric = f"{agg}:{structure}"
                        
                        if organization_filter:
                            metric_query = f"{base_metric}{{organization:{organization_filter}}}"
                        else:
                            metric_query = f"{base_metric}{{*}}"
                        
                        total_tested += 1
                        
                        try:
                            # Test if metric exists and has data
                            metrics_data = await metrics_client.get_metrics(
                                metric_name=metric_query,
                                start_time=start_time,
                                end_time=end_time
                            )
                            
                            if metrics_data.get('series') and len(metrics_data['series']) > 0:
                                series = metrics_data['series'][0]
                                if series.get('points') and len(series['points']) > 0:
                                    # Extract service name
                                    service_name = "unknown"
                                    try:
                                        metric_parts = structure.split('.')
                                        if len(metric_parts) > 0 and '*' not in metric_parts[0]:
                                            service_name = metric_parts[0]
                                        elif len(metric_parts) > 1 and '*' not in metric_parts[1]:
                                            service_name = metric_parts[1]
                                    except:
                                        pass
                                    
                                    # Calculate latest value
                                    latest_value = 0
                                    try:
                                        point = series['points'][-1]
                                        if hasattr(point, 'value'):
                                            latest_value = point.value
                                        elif isinstance(point, dict) and 'value' in point:
                                            latest_value = point['value']
                                        elif isinstance(point, list) and len(point) >= 2:
                                            latest_value = point[1]
                                        else:
                                            import ast
                                            parsed = ast.literal_eval(str(point))
                                            if isinstance(parsed, list) and len(parsed) >= 2:
                                                latest_value = parsed[1]
                                    except:
                                        latest_value = 0
                                    
                                    discovered_metrics.append({
                                        'query': metric_query,
                                        'metric': series['metric'],
                                        'service': service_name,
                                        'latest_value': latest_value,
                                        'points_count': len(series['points']),
                                        'tags': series.get('tags', [])
                                    })
                                    
                                    response += f"   ✅ {metric_query} → ${latest_value:.2f}\n"
                        except:
                            # Metric doesn't exist or has no data
                            pass
                
                response += "\n"
            
            # Also test specific service combinations
            response += "**Service-Specific Search**:\n"
            for service in service_prefixes[:10]:  # Limit to first 10 for performance
                for pattern in search_patterns[:3]:  # Limit patterns
                    metric_query = f"sum:{service}.{pattern}"
                    if organization_filter:
                        metric_query += f"{{organization:{organization_filter}}}"
                    else:
                        metric_query += "{*}"
                    
                    total_tested += 1
                    
                    try:
                        metrics_data = await metrics_client.get_metrics(
                            metric_name=metric_query,
                            start_time=start_time,
                            end_time=end_time
                        )
                        
                        if metrics_data.get('series') and len(metrics_data['series']) > 0:
                            series = metrics_data['series'][0]
                            if series.get('points') and len(series['points']) > 0:
                                latest_value = 0
                                try:
                                    point = series['points'][-1]
                                    if hasattr(point, 'value'):
                                        latest_value = point.value
                                    elif isinstance(point, dict) and 'value' in point:
                                        latest_value = point['value']
                                    elif isinstance(point, list) and len(point) >= 2:
                                        latest_value = point[1]
                                    else:
                                        import ast
                                        parsed = ast.literal_eval(str(point))
                                        if isinstance(parsed, list) and len(parsed) >= 2:
                                            latest_value = parsed[1]
                                except:
                                    pass
                                
                                discovered_metrics.append({
                                    'query': metric_query,
                                    'metric': series['metric'],
                                    'service': service,
                                    'latest_value': latest_value,
                                    'points_count': len(series['points']),
                                    'tags': series.get('tags', [])
                                })
                                
                                response += f"   ✅ {metric_query} → ${latest_value:.2f}\n"
                    except:
                        pass
            
            # Summary
            response += f"\n📊 **DISCOVERY SUMMARY**:\n"
            response += f"🔍 **Metrics Tested**: {total_tested}\n"
            response += f"✅ **Metrics Found**: {len(discovered_metrics)}\n"
            response += f"⏰ **Time Period**: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            if discovered_metrics:
                # Sort by latest value (highest first)
                discovered_metrics.sort(key=lambda x: x['latest_value'], reverse=True)
                
                response += "💰 **Top Cost Metrics** (by latest value):\n"
                total_discovered_cost = 0
                
                for i, metric in enumerate(discovered_metrics[:10], 1):  # Show top 10
                    total_discovered_cost += metric['latest_value']
                    response += f"{i:2d}. **{metric['service'].title()}**: ${metric['latest_value']:.2f}\n"
                    response += f"     Query: {metric['query']}\n"
                    response += f"     Metric: {metric['metric']}\n"
                    if metric['tags']:
                        response += f"     Tags: {', '.join(metric['tags'][:3])}\n"
                    response += f"     Data Points: {metric['points_count']}\n\n"
                
                response += f"💰 **Total Discovered Cost**: ${total_discovered_cost:.2f}\n\n"
                
                response += "🎯 **Usage Tips**:\n"
                response += "• Copy any of the above queries to use in datadog_cost_metrics_query\n"
                response += "• Adjust organization_filter to focus on specific teams\n"
                response += "• Use different time_range values for trend analysis\n"
                response += "• Combine multiple metrics for comprehensive cost tracking\n"
            else:
                response += "📭 **No cost metrics found**.\n\n"
                response += "💡 **Troubleshooting**:\n"
                response += f"• Try different search patterns: 'billing', 'expense', 'spend'\n"
                response += f"• Verify organization_filter: '{organization_filter}' has data\n"
                response += f"• Extend time_range to capture historical data\n"
                response += f"• Check if your DataDog account has cost/billing integrations\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to discover DataDog cost metrics: {e}", provider="datadog")
            return f"❌ Error discovering cost metrics: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_get_template_variables(
        dashboard_id: str
    ) -> str:
        """DataDog Dashboard Template Variables: List all available template variables and their options for any dashboard."""
        logger.info(f"🎛️ Getting template variables for DataDog dashboard: {dashboard_id}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            # Get dashboard
            dashboard = await client.get_dashboard(dashboard_id)
            
            response = f"🎛️ **DATADOG DASHBOARD TEMPLATE VARIABLES**\n\n"
            response += f"🎯 **Dashboard**: {dashboard['title']}\n"
            response += f"📋 **ID**: {dashboard['id']}\n\n"
            
            if dashboard.get('template_variables'):
                response += f"🎛️ **Template Variables**: {len(dashboard['template_variables'])} found\n\n"
                
                for i, var in enumerate(dashboard['template_variables'], 1):
                    var_name = var.get('name', 'unnamed')
                    var_default = var.get('default', '')
                    var_available_values = var.get('available_values', [])
                    var_prefix = var.get('prefix', '')
                    
                    response += f"**{i}. {var_name}**\n"
                    response += f"   Default: {var_default or 'None'}\n"
                    response += f"   Prefix: {var_prefix or 'None'}\n"
                    
                    if var_available_values:
                        response += f"   Available Values ({len(var_available_values)}):\n"
                        # Show first 10 values
                        for value in var_available_values[:10]:
                            response += f"     • {value}\n"
                        if len(var_available_values) > 10:
                            response += f"     ... and {len(var_available_values) - 10} more\n"
                    else:
                        response += f"   Available Values: None defined\n"
                    
                    response += "\n"
                
                # Show example usage
                response += "💡 **Example Usage with datadog_cost_metrics_query**:\n"
                example_filters = {}
                for var in dashboard['template_variables']:
                    var_name = var.get('name', '')
                    var_available_values = var.get('available_values', [])
                    if var_available_values:
                        example_filters[var_name] = var_available_values[0]
                    elif var.get('default'):
                        example_filters[var_name] = var['default']
                
                if example_filters:
                    import json
                    response += f"```\n"
                    response += f'template_variable_filters=\'{json.dumps(example_filters)}\'\n'
                    response += f"```\n\n"
                
            else:
                response += "📭 **No template variables found** in this dashboard.\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get DataDog dashboard template variables: {e}", "datadog")
            return f"❌ Error getting template variables: {str(e)}"

    @mcp.tool()
    async def datadog_tenant_cost_breakdown(
        service_name: str,
        organization_filter: Optional[str] = None,
        time_range: str = "24h",
        top_n: int = 10
    ) -> str:
        """DataDog Tenant Cost Breakdown: Get cost breakdown by tenant/organization for a specific service.
        
        Args:
            service_name: Service name (e.g., 'carma', 'datawarehouse', 'analytics')
            organization_filter: Optional filter for specific organization
            time_range: Time range for the query (1h, 24h, 7d, 30d)
            top_n: Number of top tenants to show
        """
        logger.info(f"💰 Getting tenant cost breakdown for {service_name}...")
        
        try:
            metrics_client = datadog_provider.get_client("metrics")
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            response = f"💰 **DATADOG TENANT COST BREAKDOWN**\n\n"
            response += f"🎯 **Service**: {service_name.title()}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            if organization_filter:
                response += f"🏢 **Organization Filter**: {organization_filter}\n"
            response += f"📊 **Top**: {top_n} tenants\n\n"
            
            # Try different metric patterns to get tenant-level data
            tenant_costs = {}
            patterns_to_try = [
                f"sum:{service_name}.organization.cost{{*}} by {{organization}}",
                f"sum:{service_name}.cost{{*}} by {{organization}}",
                f"avg:{service_name}.organization.cost{{*}} by {{organization}}",
                f"max:{service_name}.organization.cost{{*}} by {{organization}}"
            ]
            
            for pattern in patterns_to_try:
                try:
                    response += f"🔍 **Trying Pattern**: {pattern}\n"
                    
                    # Apply organization filter if provided
                    if organization_filter:
                        filtered_pattern = pattern.replace("{*}", f"{{organization:{organization_filter}}}")
                    else:
                        filtered_pattern = pattern
                    
                    metrics_data = await metrics_client.get_metrics(
                        metric_name=filtered_pattern,
                        start_time=start_time,
                        end_time=end_time
                    )
                    
                    if metrics_data.get('series') and len(metrics_data['series']) > 0:
                        response += f"✅ **Found Data**: {len(metrics_data['series'])} series\n\n"
                        
                        for series in metrics_data['series']:
                            # Extract organization/tenant from series metadata
                            tenant_name = "unknown"
                            if 'scope' in series:
                                # Look for organization tag in scope
                                scope_parts = series['scope'].split(',') if series['scope'] else []
                                for part in scope_parts:
                                    if 'organization:' in part:
                                        tenant_name = part.split('organization:')[1].strip()
                                        break
                            
                            # Get cost value
                            if series.get('points') and len(series['points']) > 0:
                                # Parse the last point
                                try:
                                    last_point = series['points'][-1]
                                    if hasattr(last_point, 'value'):
                                        cost_value = last_point.value
                                    elif isinstance(last_point, list) and len(last_point) >= 2:
                                        cost_value = last_point[1]
                                    else:
                                        # Try parsing as string
                                        import ast
                                        parsed_point = ast.literal_eval(str(last_point))
                                        cost_value = parsed_point[1] if isinstance(parsed_point, list) else 0
                                    
                                    tenant_costs[tenant_name] = tenant_costs.get(tenant_name, 0) + float(cost_value)
                                    
                                except Exception as parse_error:
                                    response += f"⚠️ **Parse Error**: {parse_error}\n"
                        
                        break  # Found working pattern, stop trying others
                    else:
                        response += f"📭 **No Data Found**\n"
                        
                except Exception as pattern_error:
                    response += f"❌ **Pattern Failed**: {str(pattern_error)[:100]}...\n"
            
            # Display results
            if tenant_costs:
                response += f"💰 **TENANT COST BREAKDOWN**:\n\n"
                sorted_tenants = sorted(tenant_costs.items(), key=lambda x: x[1], reverse=True)
                total_cost = sum(tenant_costs.values())
                
                for i, (tenant, cost) in enumerate(sorted_tenants[:top_n], 1):
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    response += f"**{i}. {tenant}**\n"
                    response += f"   💰 Cost: ${cost:.2f} ({percentage:.1f}%)\n\n"
                
                response += f"📊 **Summary**:\n"
                response += f"💰 **Total Cost**: ${total_cost:.2f}\n"
                response += f"🏢 **Total Tenants**: {len(tenant_costs)}\n"
                response += f"⏰ **Period**: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}\n"
            else:
                response += "📭 **No tenant cost data found**.\n\n"
                response += "💡 **Suggestions**:\n"
                response += "• Verify the service name is correct\n"
                response += "• Check if tenant-level metrics exist for this service\n"
                response += "• Try different time ranges\n"
                response += "• Use datadog_discover_cost_metrics to find available metrics\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get tenant cost breakdown: {e}", "datadog")
            return f"❌ Error getting tenant cost breakdown: {str(e)}"

    @mcp.tool()
    async def datadog_test_connection() -> str:
        """DataDog Connection: Test connection and show account information."""
        logger.info("🧪 Testing DataDog connection...")
        
        try:
            connection_result = await datadog_provider.test_connection()
            
            if connection_result:
                client = datadog_provider.get_client()
                dashboards = await client.list_dashboards()
                
                response = f"✅ **DATADOG CONNECTION TEST SUCCESSFUL**\n\n"
                response += f"🔑 **Authentication**: Valid\n"
                response += f"🌐 **DataDog Site**: {config.datadog_site}\n"
                response += f"📊 **Dashboards**: {dashboards.get('total_dashboards', 0)} found\n"
                response += f"🚀 **Status**: Ready for monitoring operations\n\n"
                
                response += f"🎯 **Available Capabilities**:\n"
                for capability in datadog_provider.get_capabilities():
                    formatted_cap = capability.replace('_', ' ').title()
                    response += f"   ✅ {formatted_cap}\n"
                
                return response
            else:
                return f"❌ DataDog connection test failed. Check your API keys and permissions."
                
        except Exception as e:
            logger.error(f"DataDog connection test failed: {e}", provider="datadog")
            return f"❌ DataDog connection test failed: {str(e)}" 

    @mcp.tool()
    async def datadog_cost_metrics_query(
        dashboard_id: str,
        template_variable_filters: Optional[str] = None,
        time_range: str = "24h"
    ) -> str:
        """DataDog Cost Metrics: Query actual cost metrics from any dashboard with dynamic template variable discovery and substitution.
        
        Args:
            dashboard_id: The DataDog dashboard ID to query
            template_variable_filters: Optional JSON string of template variable filters like '{"organization": "myorg", "service": "web"}' (Claude will auto-convert dict to string)
            time_range: Time range for the query (1h, 24h, 7d, 30d)
        """
        logger.info(f"💰 Querying DataDog cost metrics from dashboard: {dashboard_id}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            metrics_client = datadog_provider.get_client("metrics")
            
            # Get dashboard to extract template variables and discover structure
            dashboard = await client.get_dashboard(dashboard_id)
            
            response = f"💰 **DATADOG COST METRICS QUERY**\n\n"
            response += f"🎯 **Dashboard**: {dashboard['title']}\n"
            response += f"📋 **ID**: {dashboard['id']}\n"
            response += f"⏰ **Time Range**: {time_range}\n\n"
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            # Generic approach: Discover cost metrics dynamically
            total_cost = 0
            service_costs = {}
            
            response += "📊 **Cost Metrics Discovery:**\n\n"
            response += f"🔍 **Dashboard Analysis**: Found {len(dashboard['widgets'])} widgets\n"
            
            # Step 1: Extract and process template variables from dashboard
            template_vars = {}
            available_filters = {}
            
            if dashboard.get('template_variables'):
                response += f"🎯 **Template Variables**: {len(dashboard['template_variables'])} found\n"
                for var in dashboard['template_variables']:
                    var_name = var.get('name', '')
                    var_default = var.get('default', '')
                    var_available_values = var.get('available_values', [])
                    
                    template_vars[var_name] = var_default
                    available_filters[var_name] = {
                        'default': var_default,
                        'available_values': var_available_values
                    }
                    
                    response += f"   {var_name}: {var_default}"
                    if var_available_values:
                        response += f" (options: {', '.join(var_available_values[:5])}{'...' if len(var_available_values) > 5 else ''})"
                    response += "\n"
            
            # Step 2: Parse user-provided template variable filters
            user_filters = {}
            if template_variable_filters:
                try:
                    # Claude auto-converts dict to JSON string, but sometimes passes dict directly
                    # Handle both cases gracefully
                    if isinstance(template_variable_filters, str):
                        import json
                        user_filters = json.loads(template_variable_filters)
                    elif hasattr(template_variable_filters, 'items'):
                        # Treat as dict-like object
                        user_filters = dict(template_variable_filters)
                    else:
                        # Try to parse as string anyway
                        import json
                        user_filters = json.loads(str(template_variable_filters))
                    
                    if user_filters:
                        response += f"\n🎛️ **User Filters Applied**: {len(user_filters)}\n"
                        for key, value in user_filters.items():
                            response += f"   {key}: {value}\n"
                            # Override default template vars with user values
                            if key in template_vars:
                                template_vars[key] = value
                except Exception as e:
                    response += f"\n⚠️ **Error parsing template_variable_filters**: {str(e)}\n"
                    response += f"⚠️ **Received**: {template_variable_filters} (type: {type(template_variable_filters)})\n"
            
            response += "\n"
            
            # Step 3: Discover cost-related metrics using DataDog Metrics API
            response += "🔍 **Discovering Cost Metrics**:\n"
            try:
                # Search for metrics containing 'cost' keyword
                cost_metrics_discovered = []
                
                # Use DataDog metrics search API to find cost-related metrics
                # This is a more generic approach than hardcoding specific metrics
                search_patterns = ['cost', 'billing', 'expense', 'spend', 'price']
                
                for pattern in search_patterns:
                    try:
                        # Search for metrics with cost-related keywords
                        response += f"   Searching for '{pattern}' metrics...\n"
                        
                        # Build metric queries with discovered template variables
                        for base_pattern in [f"*.organization.{pattern}", f"*.{pattern}", f"{pattern}.*"]:
                            for agg in ['sum', 'avg', 'max']:
                                # Build base metric
                                base_metric = f"{agg}:{base_pattern}"
                                
                                # Apply template variable filters
                                tag_filters = []
                                for var_name, var_value in template_vars.items():
                                    if var_value and var_value != '*':
                                        tag_filters.append(f"{var_name}:{var_value}")
                                
                                if tag_filters:
                                    metric_with_filters = f"{base_metric}{{{','.join(tag_filters)}}}"
                                else:
                                    metric_with_filters = f"{base_metric}{{*}}"
                                
                                # Test if metric exists by attempting to query it
                                try:
                                    test_data = await metrics_client.get_metrics(
                                        metric_name=metric_with_filters,
                                        start_time=start_time,
                                        end_time=end_time
                                    )
                                    
                                    if test_data.get('series') and len(test_data['series']) > 0:
                                        cost_metrics_discovered.append(metric_with_filters)
                                        response += f"      ✅ Found: {metric_with_filters}\n"
                                        
                                except:
                                    # Metric doesn't exist, continue searching
                                    pass
                        
                    except Exception as search_error:
                        response += f"      ⚠️ Search failed for '{pattern}': {str(search_error)[:50]}...\n"
                
                # Step 4: If no metrics discovered through search, fall back to common patterns
                if not cost_metrics_discovered:
                    response += "\n🔄 **Fallback**: Using common cost metric patterns...\n"
                    
                    # Common service prefixes that might have cost metrics
                    common_services = [
                        'datawarehouse', 'analytics', 'treasury', 'carma', 'whatif',
                        'compute', 'storage', 'network', 'database', 'lambda', 
                        'ec2', 'rds', 's3', 'cloudfront', 'elb', 'api_gateway',
                        'application', 'service', 'infrastructure', 'platform'
                    ]
                    
                    for service in common_services:
                        for cost_field in ['cost', 'billing', 'spend', 'price']:
                            # Try different metric structures
                            patterns = [
                                f"sum:{service}.organization.{cost_field}",
                                f"sum:{service}.{cost_field}",
                                f"sum:{cost_field}.{service}",
                                f"avg:{service}.{cost_field}"
                            ]
                            
                            for pattern in patterns:
                                # Apply template variable filters discovered from dashboard
                                tag_filters = []
                                for var_name, var_value in template_vars.items():
                                    if var_value and var_value != '*':
                                        tag_filters.append(f"{var_name}:{var_value}")
                                
                                if tag_filters:
                                    metric_query = f"{pattern}{{{','.join(tag_filters)}}}"
                                else:
                                    metric_query = f"{pattern}{{*}}"
                                
                                try:
                                    # Test if this metric exists
                                    test_data = await metrics_client.get_metrics(
                                        metric_name=metric_query,
                                        start_time=start_time,
                                        end_time=end_time
                                    )
                                    
                                    if test_data.get('series') and len(test_data['series']) > 0:
                                        cost_metrics_discovered.append(metric_query)
                                        response += f"   ✅ Discovered: {metric_query}\n"
                                        break  # Found one for this service, move to next
                                        
                                except:
                                    # This metric doesn't exist, try next pattern
                                    continue
                
                response += f"\n📊 **Total Cost Metrics Found**: {len(cost_metrics_discovered)}\n\n"
                
                # Step 5: Query each discovered metric
                if cost_metrics_discovered:
                    response += "💰 **Querying Discovered Metrics**:\n\n"
                    
                    for i, metric_query in enumerate(cost_metrics_discovered, 1):
                        # Extract service name from metric
                        service_name = "unknown"
                        try:
                            # Try to extract service name from different metric patterns
                            metric_parts = metric_query.split(':')[1].split('.') if ':' in metric_query else metric_query.split('.')
                            if len(metric_parts) > 0:
                                service_name = metric_parts[0].split('{')[0]  # Remove tag filters
                        except:
                            service_name = f"service_{i}"
                        
                        response += f"**{i}. {service_name.title()}**\n"
                        response += f"   Query: {metric_query}\n"
                        
                        try:
                            metrics_data = await metrics_client.get_metrics(
                                metric_name=metric_query,
                                start_time=start_time,
                                end_time=end_time
                            )
                            
                            response += f"   📊 Got {len(metrics_data.get('series', []))} series\n"
                            
                            if metrics_data['series']:
                                for series in metrics_data['series']:
                                    response += f"   📈 Series: {series['metric']} with {len(series['points'])} points\n"
                                    if series['points']:
                                        # Parse points correctly (they may be Point objects)
                                        values = []
                                        for point in series['points']:
                                            if hasattr(point, 'value'):
                                                values.append(point.value)
                                            elif isinstance(point, dict) and 'value' in point:
                                                values.append(point['value'])
                                            elif isinstance(point, list) and len(point) >= 2:
                                                values.append(point[1])  # [timestamp, value]
                                            else:
                                                # Try to parse as string representation
                                                try:
                                                    point_str = str(point)
                                                    if '[' in point_str and ',' in point_str:
                                                        # Parse "[timestamp, value]" format
                                                        import ast
                                                        parsed = ast.literal_eval(point_str)
                                                        if isinstance(parsed, list) and len(parsed) >= 2:
                                                            values.append(parsed[1])
                                                except:
                                                    pass
                                        
                                        if values:
                                            latest = values[-1] if values else 0
                                            avg = sum(values) / len(values) if values else 0
                                            
                                            service_costs[service_name] = service_costs.get(service_name, 0) + latest
                                            total_cost += latest
                                            
                                            response += f"   💰 Latest: ${latest:.2f}, Avg: ${avg:.2f}\n"
                                            response += f"   📊 Data Points: {len(values)}\n"
                                        else:
                                            response += f"   📭 Could not parse data points\n"
                                    else:
                                        response += f"   📭 No data points in series\n"
                            else:
                                response += f"   📭 No series data found\n"
                                
                        except Exception as query_error:
                            response += f"   ⚠️ Query failed: {str(query_error)[:100]}...\n"
                        
                        response += "\n"
                else:
                    response += "📭 **No cost metrics discovered**. This dashboard may not contain cost data.\n\n"
                    response += "💡 **Suggestions**:\n"
                    response += "• Verify this dashboard contains cost/billing metrics\n" 
                    response += "• Check template variable filters - try different values\n"
                    response += "• Try a different time range\n"
                    response += "• Use datadog_discover_cost_metrics to find available cost metrics\n"
                    if available_filters:
                        response += "\n🎛️ **Available Template Variables to Try**:\n"
                        for var_name, var_info in available_filters.items():
                            if var_info['available_values']:
                                response += f"• {var_name}: {', '.join(var_info['available_values'][:5])}\n"
                    response += "\n"
                
            except Exception as discovery_error:
                response += f"❌ **Metric discovery failed**: {str(discovery_error)[:100]}...\n\n"
            
            # Summary
            response += f"📋 **COST SUMMARY**:\n"
            response += f"💰 **Total Cost**: ${total_cost:.2f}\n"
            if template_vars:
                response += f"🎛️ **Filters Applied**: {', '.join([f'{k}:{v}' for k, v in template_vars.items() if v and v != '*'])}\n"
            response += f"⏰ **Time Period**: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            if service_costs:
                response += f"📊 **Cost Breakdown by Service**:\n"
                sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
                for service, cost in sorted_services:
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    response += f"   {service}: ${cost:.2f} ({percentage:.1f}%)\n"
            else:
                response += "📭 No cost data found for the specified organization and time range.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to query DataDog cost metrics: {e}", "datadog")
            return f"❌ Error querying cost metrics: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_analyze_widget(
        dashboard_id: str,
        widget_index: Optional[int] = None,
        widget_title: Optional[str] = None,
        template_variable_filters: Optional[str] = None,
        time_range: str = "24h"
    ) -> str:
        """
        DataDog Dashboard: Intelligently analyze any dashboard widget to determine its purpose and extract data.
        
        This tool examines widget structure, queries, and content to automatically determine:
        - Widget type and visualization style
        - Data purpose (cost analysis, performance metrics, top lists, etc.)
        - Query patterns and metric types
        - Extract and format relevant data based on what it finds
        
        Args:
            dashboard_id: Dashboard ID to analyze
            widget_index: Optional widget index (0-based) to analyze specific widget
            widget_title: Optional widget title to find specific widget by name
            template_variable_filters: Optional template variable values as JSON string (e.g., '{"organization": "myorg"}')
            time_range: Time range for data extraction (1h, 24h, 7d, 30d)
        """
        logger.info(f"🔍 Intelligently analyzing dashboard {dashboard_id} widgets...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            
            # Get dashboard structure
            dashboard = await client.get_dashboard(dashboard_id)
            if not dashboard or 'widgets' not in dashboard:
                return f"❌ Dashboard {dashboard_id} not found or has no widgets"
            
            # Parse template variable filters
            template_vars = {}
            if template_variable_filters:
                try:
                    if isinstance(template_variable_filters, str):
                        template_vars = json.loads(template_variable_filters)
                    elif isinstance(template_variable_filters, dict):
                        template_vars = template_variable_filters
                except json.JSONDecodeError:
                    logger.warning("Invalid template variable filters JSON, ignoring")
            
            widgets = dashboard['widgets']
            response = f"🔍 **INTELLIGENT DASHBOARD WIDGET ANALYSIS**\n\n"
            response += f"📊 **Dashboard**: {dashboard.get('title', 'Unknown')} (ID: {dashboard_id})\n"
            response += f"📈 **Total Widgets**: {len(widgets)}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            if template_vars:
                response += f"🎯 **Filters**: {template_vars}\n"
            response += "\n"
            
            # If specific widget requested, analyze only that one
            target_widgets = []
            if widget_index is not None:
                if 0 <= widget_index < len(widgets):
                    target_widgets = [widgets[widget_index]]
                    response += f"🎯 **Analyzing Widget #{widget_index}**\n\n"
                else:
                    return f"❌ Widget index {widget_index} out of range (0-{len(widgets)-1})"
            elif widget_title:
                # Find widget by title
                for i, widget in enumerate(widgets):
                    widget_def = widget.get('definition', {})
                    title = widget_def.get('title', '').lower()
                    if widget_title.lower() in title:
                        target_widgets.append(widget)
                        response += f"🎯 **Found Widget**: '{widget_def.get('title', 'Untitled')}' (Index: {i})\n\n"
                        break
                if not target_widgets:
                    return f"❌ No widget found with title containing '{widget_title}'"
            else:
                # Analyze all widgets
                target_widgets = widgets
                response += "🔍 **Analyzing All Widgets**\n\n"
            
            # Analyze each widget
            for widget_idx, widget in enumerate(target_widgets):
                if len(target_widgets) > 1:
                    actual_idx = widgets.index(widget) if widget in widgets else widget_idx
                    response += f"## Widget {actual_idx}: "
                
                # Get widget details
                widget_def = widget.get('definition', {})
                widget_type = str(widget_def.get('type', 'unknown'))
                title = widget_def.get('title', 'Untitled Widget')
                
                analysis = f"**{title}**\n"
                analysis += f"📊 **Type**: {widget_type.replace('_', ' ').title()}\n"
                
                # Determine widget purpose based on title
                purpose_keywords = {
                    'cost': ['cost', 'billing', 'spend', 'expense', 'price', 'budget'],
                    'performance': ['latency', 'response time', 'throughput', 'cpu', 'memory', 'performance'],
                    'top_list': ['top', 'highest', 'most', 'largest', 'biggest', 'ranking'],
                    'error_tracking': ['error', 'exception', 'failure', 'alert', 'issue'],
                    'usage': ['usage', 'utilization', 'consumption', 'volume', 'count'],
                    'trend': ['trend', 'over time', 'historical', 'timeline', 'growth']
                }
                
                detected_purposes = []
                title_lower = title.lower()
                
                for purpose, keywords in purpose_keywords.items():
                    if any(keyword in title_lower for keyword in keywords):
                        detected_purposes.append(purpose)
                
                if detected_purposes:
                    analysis += f"🎯 **Detected Purpose**: {', '.join(detected_purposes)}\n"
                
                # Analyze widget structure and queries
                if widget_type == 'group':
                    nested_widgets = widget_def.get('widgets', [])
                    analysis += f"📦 **Group Widget** with {len(nested_widgets)} nested widgets\n"
                    
                    # If nested widgets are empty (common with DataDog API), try intelligent reconstruction
                    if len(nested_widgets) == 0:
                        analysis += f"   🧠 **Empty widget detected - using intelligent query reconstruction**\n"
                        
                        # Extract service name from widget title
                        service_name = None
                        title_words = title.lower().split()
                        # Common words to exclude when extracting service names
                        exclude_words = ['cost', 'costs', 'top', 'breakdown', 'by', 'service', 'tenant', 'organization', 
                                       'widget', 'dashboard', 'summary', 'total', 'overview', 'analysis', 'per', 'hours',
                                       'runtime', 'average', 'duration', 'number', 'historic', 'queue', 'trigger']
                        
                        for word in title_words:
                            if word not in exclude_words and len(word) > 2:  # Ignore very short words
                                service_name = word
                                break
                        
                        if service_name:
                            analysis += f"   🎯 **Detected Service**: {service_name}\n"
                            
                            # Intelligently build metric patterns based on widget title context
                            metric_patterns = []
                            title_lower = title.lower()
                            
                            # Extract breakdown dimension from title
                            breakdown_by = "organization"  # Default
                            if "trigger" in title_lower:
                                breakdown_by = "trigger"
                            elif "queue" in title_lower:
                                breakdown_by = "queue"
                            elif "tenant" in title_lower:
                                breakdown_by = "organization"
                            elif "host" in title_lower:
                                breakdown_by = "host"
                            elif "service" in title_lower:
                                breakdown_by = "service"
                            elif "endpoint" in title_lower:
                                breakdown_by = "endpoint"
                                
                            analysis += f"   📊 **Breakdown Dimension**: {breakdown_by}\n"
                            
                            # Build patterns based on title keywords using KNOWN WORKING PATTERNS
                            if "cost" in title_lower or not detected_purposes:  # Default to cost
                                if breakdown_by == "trigger":
                                    metric_patterns.extend([
                                        f"sum:{service_name}.trigger.cost{{*}} by {{trigger}}",
                                        f"avg:{service_name}.trigger.cost{{*}} by {{trigger}}",
                                        f"sum:{service_name}.cost{{*}} by {{trigger}}"
                                    ])
                                elif breakdown_by == "queue":
                                    metric_patterns.extend([
                                        f"sum:{service_name}.queue.cost{{*}} by {{queue}}",
                                        f"avg:{service_name}.queue.cost{{*}} by {{queue}}",
                                        f"sum:{service_name}.cost{{*}} by {{queue}}"
                                    ])
                                else:  # organization/tenant
                                    metric_patterns.extend([
                                        f"sum:{service_name}.trigger.cost{{*}} by {{organization}}",
                                        f"sum:{service_name}.organization.cost{{*}} by {{organization}}",
                                        f"sum:{service_name}.cost{{*}} by {{organization}}"
                                    ])
                            elif "runtime" in title_lower or "hours" in title_lower:
                                metric_patterns.extend([
                                    f"sum:{service_name}.runtime.hours{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.runtime{{*}} by {{{breakdown_by}}}",
                                    f"sum:{service_name}.hours{{*}} by {{{breakdown_by}}}"
                                ])
                            elif "duration" in title_lower or "average" in title_lower:
                                metric_patterns.extend([
                                    f"avg:{service_name}.duration{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.trigger.duration{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.trigger.avg_execution_time{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.avg_execution_time{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.execution_time{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.trigger.execution_time{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.trigger.avg_duration{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.avg_duration{{*}} by {{{breakdown_by}}}",
                                    f"max:{service_name}.duration{{*}} by {{{breakdown_by}}}",
                                    f"sum:{service_name}.duration{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.response_time{{*}} by {{{breakdown_by}}}",
                                    f"avg:{service_name}.processing_time{{*}} by {{{breakdown_by}}}"
                                ])
                            elif "number" in title_lower:
                                metric_patterns.extend([
                                    f"count:{service_name}.*{{*}} by {{{breakdown_by}}}",
                                    f"sum:{service_name}.count{{*}} by {{{breakdown_by}}}"
                                ])
                            else:
                                # Try the known working patterns as fallback
                                metric_patterns.extend([
                                    f"sum:{service_name}.trigger.cost{{*}} by {{organization}}",
                                    f"sum:{service_name}.organization.cost{{*}} by {{organization}}"
                                ])
                            
                            # Try each pattern to find working metrics
                            for pattern in metric_patterns:
                                try:
                                    analysis += f"      🔍 **Testing Pattern**: {pattern}\n"
                                    
                                    metrics_client = datadog_provider.get_client("metrics")
                                    end_time = datetime.now()
                                    start_time = end_time - timedelta(hours=24)
                                    
                                    result = await metrics_client.query_metrics(
                                        query=pattern,
                                        start_time=int(start_time.timestamp()),
                                        end_time=int(end_time.timestamp())
                                    )
                                    
                                    if result and 'series' in result and result['series']:
                                        series_count = len(result['series'])
                                        analysis += f"      ✅ **Found {series_count} tenant series!**\n"
                                        
                                        # Extract tenant costs using the same logic that worked in our test
                                        tenant_costs = []
                                        for series in result['series']:
                                            scope = series.get('scope', '')
                                            points = series.get('points', [])
                                            
                                            if points:
                                                latest_point = points[-1]
                                                value = None
                                                
                                                # Handle different point formats
                                                if isinstance(latest_point, dict):
                                                    value = latest_point.get('value')
                                                elif isinstance(latest_point, list) and len(latest_point) >= 2:
                                                    value = latest_point[1]
                                                
                                                if value is not None and scope:
                                                    tenant_costs.append((scope, value))
                                        
                                        analysis += f"      📋 **Debug**: Extracted {len(tenant_costs)} tenant costs from {len(result['series'])} series\n"
                                        
                                        if tenant_costs:
                                            # Sort by value and show top entries
                                            tenant_costs.sort(key=lambda x: x[1], reverse=True)
                                            
                                            # Determine data type and units for display
                                            data_type = "Value"
                                            currency_symbol = ""
                                            unit = ""
                                            
                                            if 'cost' in pattern.lower():
                                                data_type = "Cost"
                                                currency_symbol = "$"
                                            elif 'runtime' in pattern.lower() or 'hours' in pattern.lower():
                                                data_type = "Runtime Hours"
                                                unit = "h"
                                            elif 'duration' in pattern.lower():
                                                data_type = "Duration"
                                                unit = "s"
                                            elif 'count' in pattern.lower():
                                                data_type = "Count"
                                                unit = ""
                                            
                                            # Create breakdown title based on detected dimension
                                            breakdown_title = f"Top {service_name.title()} by {breakdown_by.title()}"
                                            analysis += f"      📊 **{breakdown_title}**:\n"
                                            
                                            for idx, (item, value) in enumerate(tenant_costs[:10]):
                                                # Clean up item name based on breakdown dimension
                                                display_name = item
                                                for prefix in [f'{breakdown_by}:', 'organization:', 'service:', 'host:', 'endpoint:', 'container:', 'trigger:', 'queue:']:
                                                    if prefix in item:
                                                        display_name = item.replace(prefix, '').strip()
                                                        break
                                                
                                                analysis += f"         {idx+1}. {display_name}: {currency_symbol}{value:.2f}{unit}\n"
                                            
                                            total_value = sum(value for _, value in tenant_costs)
                                            analysis += f"      📊 **Total {data_type}**: {currency_symbol}{total_value:.2f}{unit}\n"
                                            analysis += f"      🎯 **Successfully found {breakdown_by} breakdown data!**\n"
                                            break
                                        else:
                                            analysis += f"      ❌ **No cost data extracted from series**\n"
                                    else:
                                        analysis += f"      ❌ **No data found**\n"
                                except Exception as e:
                                    analysis += f"      ❌ **Error**: {str(e)[:50]}...\n"
                        else:
                            analysis += f"   ❌ **Could not determine service name from title**\n"
                    else:
                        # Analyze each nested widget (if available)
                        for i, nested_widget in enumerate(nested_widgets):
                            nested_def = nested_widget.get('definition', {})
                            nested_title = nested_def.get('title', f'Nested Widget {i+1}')
                            nested_type = str(nested_def.get('type', 'unknown'))
                            
                            analysis += f"   └── **{nested_title}** ({nested_type})\n"
                            
                            # Check for queries in nested widget
                            nested_requests = nested_def.get('requests', [])
                            if nested_requests:
                                for j, request in enumerate(nested_requests):
                                    query_text = ""
                                    if 'q' in request:
                                        query_text = request['q']
                                    elif 'queries' in request and request['queries']:
                                        query_text = request['queries'][0].get('query', '')
                                    
                                    if query_text:
                                        # Apply template variable substitution
                                        processed_query = query_text
                                        for var_name, var_value in template_vars.items():
                                            processed_query = processed_query.replace(f"${{{var_name}}}", var_value)
                                            processed_query = processed_query.replace(f"${var_name}", var_value)
                                        
                                        analysis += f"       📋 **Query {j+1}**: {processed_query}\n"
                                        
                                        # Try to extract and query the metric
                                        if 'cost' in detected_purposes and ':' in processed_query:
                                            try:
                                                # Attempt to query this metric for cost data
                                                metrics_client = datadog_provider.get_client("metrics")
                                                
                                                # Set time range
                                                end_time = datetime.now()
                                                start_time = end_time - timedelta(hours=24)
                                                
                                                result = await metrics_client.query_metrics(
                                                    query=processed_query,
                                                    start_time=int(start_time.timestamp()),
                                                    end_time=int(end_time.timestamp())
                                                )
                                                
                                                if result and 'series' in result and result['series']:
                                                    series = result['series'][0]
                                                    points = series.get('points', [])
                                                    
                                                    if points:
                                                        # Get latest value
                                                        latest_point = points[-1]
                                                        if isinstance(latest_point, list) and len(latest_point) >= 2:
                                                            value = latest_point[1]
                                                            analysis += f"       💰 **Latest Value**: ${value:.2f}\n"
                                            except Exception as e:
                                                analysis += f"       ❌ **Query Error**: {str(e)[:50]}...\n"
                else:
                    # Regular widget - analyze requests/queries
                    requests = widget_def.get('requests', [])
                    if requests:
                        analysis += f"📋 **Queries Found**: {len(requests)}\n"
                        
                        for i, request in enumerate(requests):
                            query_text = ""
                            if 'q' in request:
                                query_text = request['q']
                            elif 'queries' in request and request['queries']:
                                query_text = request['queries'][0].get('query', '')
                            
                            if query_text:
                                # Apply template variable substitution
                                processed_query = query_text
                                for var_name, var_value in template_vars.items():
                                    processed_query = processed_query.replace(f"${{{var_name}}}", var_value)
                                    processed_query = processed_query.replace(f"${var_name}", var_value)
                                
                                analysis += f"   {i+1}. **Query**: {processed_query}\n"
                                
                                # Try to extract and query the metric if it's cost-related
                                if 'cost' in detected_purposes and ':' in processed_query:
                                    try:
                                        metrics_client = datadog_provider.get_client("metrics")
                                        
                                        # Set time range
                                        end_time = datetime.now()
                                        start_time = end_time - timedelta(hours=24)
                                        
                                        result = await metrics_client.query_metrics(
                                            query=processed_query,
                                            start_time=int(start_time.timestamp()),
                                            end_time=int(end_time.timestamp())
                                        )
                                        
                                        if result and 'series' in result and result['series']:
                                            series = result['series'][0]
                                            points = series.get('points', [])
                                            
                                            if points:
                                                # Get latest value
                                                latest_point = points[-1]
                                                if isinstance(latest_point, list) and len(latest_point) >= 2:
                                                    value = latest_point[1]
                                                    analysis += f"      💰 **Latest Value**: ${value:.2f}\n"
                                    except Exception as e:
                                        analysis += f"      ❌ **Query Error**: {str(e)[:50]}...\n"
                    else:
                        analysis += "📋 **No queries found in widget**\n"
                
                response += analysis + "\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"DataDog dashboard widget analysis failed: {e}", provider="datadog")
            return f"❌ Error analyzing dashboard widgets: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_generic_analyzer(
        dashboard_id: str,
        widget_identifier: Optional[str] = None,
        time_range: str = "24h",
        debug_mode: bool = False
    ) -> str:
        """DataDog Generic Dashboard Analyzer: Step-by-step analysis of any dashboard to extract data.
        
        Args:
            dashboard_id: The DataDog dashboard ID
            widget_identifier: Optional widget title or index to analyze specific widget
            time_range: Time range for metrics (1h, 24h, 7d, 30d)
            debug_mode: Show detailed debug information
        """
        logger.info(f"🔍 Generic dashboard analysis for {dashboard_id}...")
        
        try:
            output = f"🔍 **GENERIC DASHBOARD ANALYZER**\n\n"
            output += f"📊 **Dashboard ID**: {dashboard_id}\n"
            output += f"⏰ **Time Range**: {time_range}\n"
            output += f"🐛 **Debug Mode**: {debug_mode}\n\n"
            
            # Step 1: Get dashboard structure
            output += "**Step 1: Getting Dashboard Structure**\n"
            client = datadog_provider.get_client("dashboards")
            
            try:
                dashboard = await client.get_dashboard(dashboard_id)
                output += f"✅ Dashboard found: {dashboard.get('title', 'Untitled')}\n"
                output += f"   Total widgets: {len(dashboard.get('widgets', []))}\n\n"
            except Exception as e:
                return f"❌ Failed to get dashboard: {str(e)}"
            
            # Step 2: Extract template variables
            output += "**Step 2: Extracting Template Variables**\n"
            template_vars = dashboard.get('template_variables', [])
            template_var_map = {}
            
            if template_vars:
                output += f"✅ Found {len(template_vars)} template variables:\n"
                for var in template_vars:
                    if isinstance(var, dict):
                        name = var.get('name', 'unknown')
                        prefix = var.get('prefix', name)
                        default = var.get('default', '*')
                        available = var.get('available_values', [])
                        
                        template_var_map[name] = {
                            'prefix': prefix,
                            'default': default,
                            'available': available
                        }
                        
                        output += f"   - {name}: prefix='{prefix}', default='{default}'\n"
                        if available and debug_mode:
                            output += f"     Available values: {available[:5]}\n"
            else:
                output += "📭 No template variables found\n"
            output += "\n"
            
            # Step 3: Find target widget(s)
            output += "**Step 3: Finding Target Widget(s)**\n"
            widgets = dashboard.get('widgets', [])
            target_widgets = []
            
            if widget_identifier:
                # Try to find by title or index
                if widget_identifier.isdigit():
                    idx = int(widget_identifier)
                    if 0 <= idx < len(widgets):
                        target_widgets = [widgets[idx]]
                        output += f"✅ Found widget at index {idx}\n"
                else:
                    # Search by title
                    for i, widget in enumerate(widgets):
                        widget_def = widget.get('definition', {})
                        title = widget_def.get('title', '')
                        if widget_identifier.lower() in title.lower():
                            target_widgets.append(widget)
                            output += f"✅ Found widget '{title}' at index {i}\n"
                
                if not target_widgets:
                    output += f"❌ No widget found matching '{widget_identifier}'\n"
                    output += f"Available widgets:\n"
                    for i, widget in enumerate(widgets):
                        widget_def = widget.get('definition', {})
                        title = widget_def.get('title', f'Widget {i}')
                        output += f"   {i}: {title}\n"
                    return output
            else:
                target_widgets = widgets
                output += f"✅ Analyzing all {len(widgets)} widgets\n"
            output += "\n"
            
            # Step 4: Analyze each widget
            metrics_client = datadog_provider.get_client("metrics")
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            for widget_idx, widget in enumerate(target_widgets):
                widget_def = widget.get('definition', {})
                widget_type = str(widget_def.get('type', 'unknown'))
                widget_title = widget_def.get('title', f'Widget {widget_idx}')
                
                output += f"**Widget: {widget_title}**\n"
                output += f"📊 Type: {widget_type}\n"
                
                if debug_mode:
                    output += f"   Definition keys: {list(widget_def.keys())}\n"
                
                # Handle different widget types
                if widget_type == 'group':
                    output += "📦 This is a group widget\n"
                    
                    # Check for nested widgets
                    nested_widgets = widget_def.get('widgets', [])
                    if nested_widgets:
                        output += f"   Contains {len(nested_widgets)} nested widgets\n"
                        # TODO: Recursively process nested widgets
                    else:
                        output += "   ⚠️ No nested widgets found (empty group)\n"
                        
                        # For empty groups, try to infer queries from widget title
                        output += "   🧠 Attempting intelligent query reconstruction...\n"
                        
                        # Extract service name from title
                        title_words = widget_title.lower().split()
                        service_name = None
                        for word in title_words:
                            if word not in ['cost', 'total', 'by', 'per', 'widget', 'summary']:
                                service_name = word
                                break
                        
                        if service_name:
                            output += f"   Detected service: {service_name}\n"
                            
                            # Try the known working pattern
                            test_query = f"sum:{service_name}.trigger.cost{{*}} by {{organization}}"
                            output += f"   Testing query: {test_query}\n"
                            
                            try:
                                result = await metrics_client.query_metrics(
                                    query=test_query,
                                    start_time=int(start_time.timestamp()),
                                    end_time=int(end_time.timestamp())
                                )
                                
                                if result and 'series' in result and result['series']:
                                    output += f"   ✅ Found {len(result['series'])} series!\n"
                                    
                                    # Show top 5 results
                                    data_points = []
                                    for series in result['series']:
                                        scope = series.get('scope', '')
                                        points = series.get('points', [])
                                        if points:
                                            latest_point = points[-1]
                                            value = latest_point[1] if isinstance(latest_point, list) and len(latest_point) >= 2 else 0
                                            data_points.append((scope, value))
                                    
                                    if data_points:
                                        data_points.sort(key=lambda x: x[1], reverse=True)
                                        output += "   Top 5 results:\n"
                                        for i, (scope, value) in enumerate(data_points[:5]):
                                            display_name = scope.replace('organization:', '') if 'organization:' in scope else scope
                                            output += f"      {i+1}. {display_name}: ${value:.2f}\n"
                                else:
                                    output += "   ❌ No data found\n"
                            except Exception as query_error:
                                output += f"   ❌ Query failed: {str(query_error)[:100]}\n"
                    
                else:
                    # Non-group widget - check for requests
                    requests = widget_def.get('requests', [])
                    if requests:
                        output += f"📊 Found {len(requests)} requests\n"
                        
                        for req_idx, request in enumerate(requests):
                            if isinstance(request, dict):
                                # Look for queries in various formats
                                query = None
                                if 'q' in request:
                                    query = request['q']
                                elif 'queries' in request and request['queries']:
                                    query = request['queries'][0].get('query', '')
                                
                                if query:
                                    output += f"   Request {req_idx + 1}: {query[:100]}...\n"
                                    
                                    # Apply template variable substitution
                                    processed_query = query
                                    for var_name, var_info in template_var_map.items():
                                        placeholder = f"${{{var_name}}}"
                                        if placeholder in processed_query:
                                            processed_query = processed_query.replace(placeholder, var_info['default'])
                                            output += f"      Substituted {placeholder} → {var_info['default']}\n"
                                    
                                    if debug_mode:
                                        output += f"      Processed: {processed_query[:100]}...\n"
                    else:
                        output += "📭 No requests found in widget\n"
                
                output += "\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Generic dashboard analyzer failed: {e}", "datadog")
            import traceback
            if debug_mode:
                return f"❌ Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            else:
                return f"❌ Error analyzing dashboard: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_deep_debug(
        dashboard_id: str,
        widget_index: Optional[int] = None
    ) -> str:
        """DataDog Deep Debug: Comprehensive exploration of dashboard structure to find hidden nested widgets.
        
        Args:
            dashboard_id: The DataDog dashboard ID
            widget_index: Optional specific widget index to deep dive into
        """
        logger.info(f"🔍 Deep debugging dashboard structure for {dashboard_id}...")
        
        try:
            output = f"🔍 **DATADOG DEEP DASHBOARD DEBUG**\n\n"
            output += f"📊 **Dashboard ID**: {dashboard_id}\n\n"
            
            client = datadog_provider.get_client("dashboards")
            
            # Get raw dashboard data
            dashboard = await client.get_dashboard(dashboard_id)
            
            output += f"✅ **Dashboard**: {dashboard.get('title', 'Untitled')}\n"
            output += f"📈 **Total Widgets**: {len(dashboard.get('widgets', []))}\n\n"
            
            # Show ALL top-level keys in dashboard
            output += "🔍 **Dashboard Structure**:\n"
            for key, value in dashboard.items():
                if isinstance(value, list):
                    output += f"   {key}: list[{len(value)}]\n"
                elif isinstance(value, dict):
                    output += f"   {key}: dict with {len(value)} keys = {list(value.keys())[:5]}\n"
                else:
                    output += f"   {key}: {type(value).__name__} = {str(value)[:50]}...\n"
            output += "\n"
            
            widgets = dashboard.get('widgets', [])
            
            # If specific widget requested, focus on that
            if widget_index is not None:
                if 0 <= widget_index < len(widgets):
                    widgets = [widgets[widget_index]]
                    output += f"🎯 **Focusing on Widget {widget_index}**\n\n"
                else:
                    return f"❌ Widget index {widget_index} out of range (0-{len(widgets)-1})"
            
            for i, widget in enumerate(widgets):
                if widget_index is None:
                    output += f"## **Widget {i}**\n"
                
                # Show ALL widget structure
                output += f"📊 **Raw Widget Keys**: {list(widget.keys())}\n"
                
                widget_def = widget.get('definition', {})
                widget_type = widget_def.get('type', 'unknown')
                widget_title = widget_def.get('title', f'Widget {i}')
                
                output += f"   Title: {widget_title}\n"
                output += f"   Type: {widget_type}\n"
                
                # Show ALL definition keys and their content
                output += f"   Definition keys: {list(widget_def.keys())}\n"
                
                for key, value in widget_def.items():
                    if key in ['type', 'title']:
                        continue
                        
                    output += f"   📋 **{key}**:\n"
                    
                    if isinstance(value, list):
                        output += f"      List with {len(value)} items:\n"
                        for j, item in enumerate(value[:3]):  # Show first 3 items
                            if isinstance(item, dict):
                                output += f"         {j}: dict with keys = {list(item.keys())}\n"
                                # If it looks like a widget, show more details
                                if 'definition' in item or 'type' in item:
                                    item_def = item.get('definition', item)
                                    item_type = item_def.get('type', 'unknown')
                                    item_title = item_def.get('title', f'Item {j}')
                                    output += f"            → {item_title} ({item_type})\n"
                                    
                                    # Check for requests in nested items
                                    requests = item_def.get('requests', [])
                                    if requests:
                                        output += f"            → Has {len(requests)} requests\n"
                                        for k, req in enumerate(requests[:2]):
                                            if isinstance(req, dict):
                                                query = req.get('q', req.get('query', ''))
                                                if query:
                                                    output += f"               Query {k}: {query[:80]}...\n"
                            else:
                                output += f"         {j}: {type(item).__name__} = {str(item)[:50]}...\n"
                                
                        if len(value) > 3:
                            output += f"         ... and {len(value) - 3} more items\n"
                            
                    elif isinstance(value, dict):
                        output += f"      Dict with {len(value)} keys:\n"
                        for sub_key, sub_value in list(value.items())[:5]:
                            if isinstance(sub_value, list):
                                output += f"         {sub_key}: list[{len(sub_value)}]\n"
                            elif isinstance(sub_value, dict):
                                output += f"         {sub_key}: dict[{len(sub_value)}]\n"
                            else:
                                output += f"         {sub_key}: {str(sub_value)[:30]}...\n"
                    else:
                        output += f"      {type(value).__name__}: {str(value)[:100]}...\n"
                
                # Special handling for group widgets
                if str(widget_type) == 'group':
                    output += f"\n🔍 **GROUP WIDGET DEEP DIVE**:\n"
                    
                    # Check all possible keys that might contain nested widgets
                    nested_keys = ['widgets', 'nested_widgets', 'children', 'layout', 'grid', 'items']
                    
                    for key in nested_keys:
                        if key in widget_def:
                            nested_value = widget_def[key]
                            output += f"   Found '{key}': {type(nested_value)} with {len(nested_value) if isinstance(nested_value, list) else 'N/A'} items\n"
                            
                            if isinstance(nested_value, list) and nested_value:
                                output += f"      First item keys: {list(nested_value[0].keys()) if isinstance(nested_value[0], dict) else type(nested_value[0])}\n"
                    
                    # Also check for layout or positioning information
                    layout_keys = ['layout', 'size', 'position', 'x', 'y', 'width', 'height']
                    layout_info = {}
                    for key in layout_keys:
                        if key in widget_def:
                            layout_info[key] = widget_def[key]
                    
                    if layout_info:
                        output += f"   Layout info: {layout_info}\n"
                
                output += "\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Deep dashboard debug failed: {e}", "datadog")
            import traceback
            return f"❌ Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"

    @mcp.tool()
    async def datadog_trigger_cost_analysis(
        service: str = "carma",
        time_range: str = "24h",
        organization: Optional[str] = None,
        debug_mode: bool = False
    ) -> str:
        """DataDog Trigger Cost Analysis: Direct query for individual trigger cost breakdown for any service.
        
        Args:
            service: Service name (e.g., carma, lambda, etc.)
            time_range: Time range (1h, 24h, 7d, 30d)
            organization: Optional organization filter
            debug_mode: Show detailed debugging information
        """
        logger.info(f"🔍 Querying {service} trigger costs for {organization or 'all'} over {time_range}...")
        
        try:
            output = f"💰 **{service.upper()} TRIGGER COST BREAKDOWN**\n\n"
            output += f"🏢 **Organization**: {organization or 'all'}\n"
            output += f"⏰ **Time Range**: {time_range}\n\n"
            
            metrics_client = datadog_provider.get_client("metrics")
            
            # Convert time range to hours
            time_hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(time_range, 24)
            
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_hours)
            
            # Build organization filter
            org_filter = f"organization:{organization}" if organization else "*"
            
            # Test multiple query patterns to find trigger-level data
            trigger_queries = [
                f"sum:{service}.trigger.cost{{{org_filter}}} by {{trigger}}",
                f"sum:{service}.trigger.cost{{{org_filter}}} by {{trigger_name}}",
                f"sum:{service}.trigger.cost{{{org_filter}}} by {{function}}",
                f"sum:{service}.trigger.cost{{{org_filter}}} by {{name}}",
                f"sum:{service}.trigger.cost{{{org_filter}}} by {{service}}",
                f"sum:{service}.trigger.cost{{{org_filter}}} by {{queue}}",
                f"avg:{service}.trigger.cost{{{org_filter}}} by {{trigger}}",
                f"max:{service}.trigger.cost{{{org_filter}}} by {{trigger}}",
                # Try different metric patterns
                f"sum:{service}.cost{{{org_filter}}} by {{trigger}}",
                f"sum:{service}.queue.cost{{{org_filter}}} by {{trigger}}",
                f"sum:trigger.cost{{{org_filter}}} by {{trigger}}",
                # Try broader patterns
                f"sum:{service}.*.cost{{{org_filter}}} by {{trigger}}",
                f"sum:*.{service}.cost{{{org_filter}}} by {{trigger}}",
            ]
            
            found_data = False
            
            for query in trigger_queries:
                try:
                    output += f"🔍 **Testing**: `{query}`\n"
                    
                    result = await metrics_client.query_metrics(
                        query=query,
                        start_time=int(start_time.timestamp()),
                        end_time=int(end_time.timestamp())
                    )
                    
                    if result and 'series' in result and result['series']:
                        series_count = len(result['series'])
                        output += f"   ✅ **Found {series_count} trigger series!**\n\n"
                        
                        # Extract trigger costs
                        trigger_costs = []
                        errors_count = 0
                        processed_count = 0
                        
                        for series in result['series']:
                            processed_count += 1
                            try:
                                scope = series.get('scope', '')
                                points = series.get('points', [])
                                
                                if not points:
                                    continue
                                
                                # Get the trigger name from scope
                                trigger_name = "unknown"
                                if scope:
                                    # Extract trigger name from scope like "trigger:trigger_name"
                                    for part in scope.split(','):
                                        if ':' in part:
                                            key, value = part.split(':', 1)
                                            if key.strip() in ['trigger', 'trigger_name', 'function', 'name']:
                                                trigger_name = value.strip()
                                                break
                                
                                # Calculate total cost from points - SAFER parsing
                                total_cost = 0
                                valid_points = 0
                                
                                for point in points:
                                    try:
                                        # Handle different point formats safely
                                        value = None
                                        
                                        if isinstance(point, dict):
                                            # Dictionary format: {'timestamp': ..., 'value': ...}
                                            value = float(point.get('value', 0))
                                        elif isinstance(point, (list, tuple)) and len(point) >= 2:
                                            # Standard [timestamp, value] format
                                            value = float(point[1])
                                        elif hasattr(point, '__getitem__'):
                                            # Try to access as indexable object
                                            try:
                                                value = float(point[1])
                                            except (IndexError, TypeError):
                                                # Try to convert to string and parse
                                                point_str = str(point)
                                                if '[' in point_str and ']' in point_str:
                                                    # Parse string representation like "[timestamp, value]"
                                                    import ast
                                                    try:
                                                        parsed = ast.literal_eval(point_str)
                                                        if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
                                                            value = float(parsed[1])
                                                    except (ValueError, SyntaxError):
                                                        pass
                                        elif isinstance(point, (int, float)):
                                            # Direct numeric value
                                            value = float(point)
                                        
                                        if value is not None and value >= 0:  # Accept zero costs too
                                            total_cost += value
                                            valid_points += 1
                                            
                                    except (ValueError, TypeError, AttributeError) as point_error:
                                        # Log individual point errors but continue
                                        continue
                                
                                if total_cost >= 0 and trigger_name != "unknown":  # Accept zero costs
                                    trigger_costs.append((trigger_name, total_cost, valid_points))
                                    
                            except Exception as series_error:
                                errors_count += 1
                                # Continue processing other series
                                continue
                        
                        output += f"   📊 **Processing Summary**: {processed_count} series processed, {errors_count} errors\n"
                        
                        # Debug mode: show sample data
                        if debug_mode and processed_count > 0:
                            output += f"   🐛 **DEBUG - Sample Series Data**:\n"
                            sample_series = result['series'][:3]  # Show first 3 series
                            for i, series in enumerate(sample_series):
                                scope = series.get('scope', 'No scope')
                                points = series.get('points', [])
                                output += f"      Series {i+1}: scope='{scope}'\n"
                                output += f"         Points count: {len(points)}\n"
                                if points:
                                    sample_point = points[0]
                                    output += f"         Sample point: {type(sample_point).__name__} = {repr(sample_point)}\n"
                                    if len(points) > 1:
                                        last_point = points[-1]
                                        output += f"         Last point: {type(last_point).__name__} = {repr(last_point)}\n"
                        
                        if trigger_costs:
                            # Sort by cost (highest first)
                            trigger_costs.sort(key=lambda x: x[1], reverse=True)
                            
                            output += f"   ✅ **Successfully extracted {len(trigger_costs)} triggers with cost data!**\n\n"
                            output += f"📊 **TOP TRIGGERS BY COST**:\n"
                            total_all = sum(cost for _, cost, _ in trigger_costs)
                            
                            for i, (trigger, cost, points) in enumerate(trigger_costs[:20], 1):  # Show top 20
                                percentage = (cost / total_all * 100) if total_all > 0 else 0
                                output += f"   {i:2d}. **{trigger}**: ${cost:.2f} ({percentage:.1f}%) [{points} points]\n"
                            
                            if len(trigger_costs) > 20:
                                output += f"   ... and {len(trigger_costs) - 20} more triggers\n"
                            
                            output += f"\n💰 **TOTAL COST**: ${total_all:.2f}\n"
                            output += f"🎯 **WORKING QUERY**: `{query}`\n"
                            output += f"🔥 **MOST EXPENSIVE TRIGGER**: {trigger_costs[0][0]} (${trigger_costs[0][1]:.2f})\n\n"
                            
                            found_data = True
                            break  # Found working query, stop testing others
                        else:
                            output += f"   ⚠️ **No valid triggers extracted** (processed {processed_count}, errors {errors_count})\n"
                        
                    else:
                        output += f"   ❌ No data\n"
                        
                except Exception as e:
                    output += f"   ❌ Error: {str(e)[:50]}...\n"
            
            if not found_data:
                output += "\n❌ **No trigger-level cost data found**\n"
                output += "The dashboard may be using:\n"
                output += "1. Calculated fields not available via API\n"
                output += "2. Custom metrics with different naming\n"
                output += "3. Data processing that aggregates from logs\n"
                output += "4. Template variables that modify the queries\n\n"
                
                # Fallback: try to get any service metrics
                output += f"🔄 **Fallback: Available {service} metrics**\n"
                try:
                    fallback_query = f"sum:{service}.*{{{org_filter}}}"
                    result = await metrics_client.query_metrics(
                        query=fallback_query,
                        start_time=int(start_time.timestamp()),
                        end_time=int(end_time.timestamp())
                    )
                    
                    if result and 'series' in result:
                        metrics_found = set()
                        for series in result['series']:
                            metric_name = series.get('metric', 'unknown')
                            metrics_found.add(metric_name)
                        
                        output += f"Found {len(metrics_found)} {service} metrics:\n"
                        for metric in sorted(metrics_found):
                            output += f"   - {metric}\n"
                    
                except Exception as e:
                    output += f"Fallback failed: {e}\n"
            
            return output
            
        except Exception as e:
            logger.error(f"{service} trigger cost query failed: {e}", "datadog")
            import traceback
            return f"❌ Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"

    @mcp.tool()
    async def datadog_trigger_duration_analysis(
        service: str = "carma",
        time_range: str = "24h",
        organization: Optional[str] = None,
        debug_mode: bool = False,
        top_n: int = 10
    ) -> str:
        """DataDog Trigger Duration Analysis: Direct query for individual trigger duration breakdown for any service.
        
        Args:
            service: Service name (e.g., carma, lambda, etc.)
            time_range: Time range (1h, 24h, 7d, 30d)
            organization: Optional organization filter
            debug_mode: Show detailed debugging information
            top_n: Number of top triggers to show by duration
        """
        logger.info(f"⏱️ Analyzing {service} trigger durations for {time_range}...")
        
        try:
            metrics_client = datadog_provider.get_client("metrics")
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            response = f"⏱️ **{service.upper()} TRIGGER DURATION BREAKDOWN**\n\n"
            response += f"🏢 **Organization**: {organization or 'all'}\n"
            response += f"⏰ **Time Range**: {time_range}\n\n"
            
            # Comprehensive list of duration metric patterns to try
            duration_patterns = [
                f"avg:{service}.duration{{*}} by {{trigger}}",
                f"avg:{service}.trigger.duration{{*}} by {{trigger}}",
                f"avg:{service}.trigger.avg_execution_time{{*}} by {{trigger}}",
                f"avg:{service}.avg_execution_time{{*}} by {{trigger}}",
                f"avg:{service}.execution_time{{*}} by {{trigger}}",
                f"avg:{service}.trigger.execution_time{{*}} by {{trigger}}",
                f"avg:{service}.trigger.avg_duration{{*}} by {{trigger}}",
                f"avg:{service}.avg_duration{{*}} by {{trigger}}",
                f"avg:{service}.response_time{{*}} by {{trigger}}",
                f"avg:{service}.processing_time{{*}} by {{trigger}}",
                f"avg:{service}.runtime{{*}} by {{trigger}}",
                f"avg:{service}.trigger.runtime{{*}} by {{trigger}}",
                f"max:{service}.duration{{*}} by {{trigger}}",
                f"max:{service}.trigger.duration{{*}} by {{trigger}}",
                f"sum:{service}.duration{{*}} by {{trigger}}",
                f"sum:{service}.trigger.duration{{*}} by {{trigger}}"
            ]
            
            # Add organization filter if specified
            if organization:
                duration_patterns = [pattern.replace("{*}", f"{{organization:{organization}}}") for pattern in duration_patterns]
            
            trigger_durations = {}
            working_query = None
            
            for pattern in duration_patterns:
                try:
                    response += f"🔍 **Testing**: `{pattern}`\n"
                    
                    metrics_data = await metrics_client.query_metrics(
                        query=pattern,
                        start_time=int(start_time.timestamp()),
                        end_time=int(end_time.timestamp())
                    )
                    
                    if metrics_data.get('series') and len(metrics_data['series']) > 0:
                        series_list = metrics_data['series']
                        response += f"   ✅ **Found {len(series_list)} trigger series!**\n\n"
                        working_query = pattern
                        
                        # Process each series
                        errors = 0
                        if debug_mode:
                            response += f"   🐛 **DEBUG - Sample Series Data**:\n"
                            for i, series in enumerate(series_list[:3]):  # Show first 3
                                scope = series.get('scope', 'unknown')
                                points = series.get('points', [])
                                response += f"      Series {i+1}: scope='{scope}'\n"
                                response += f"         Points count: {len(points)}\n"
                                if points:
                                    sample_point = points[-1]
                                    point_type = type(sample_point).__name__
                                    response += f"         Sample point: {point_type} = {sample_point}\n"
                        
                        for series in series_list:
                            try:
                                scope = series.get('scope', '')
                                points = series.get('points', [])
                                
                                # Extract trigger name from scope
                                trigger_name = "unknown"
                                if 'trigger:' in scope:
                                    trigger_part = [part for part in scope.split(',') if 'trigger:' in part]
                                    if trigger_part:
                                        trigger_name = trigger_part[0].replace('trigger:', '').strip()
                                
                                # Get duration value from the latest point
                                if points:
                                    latest_point = points[-1]
                                    duration_value = None
                                    
                                    if isinstance(latest_point, dict):
                                        duration_value = latest_point.get('value')
                                    elif isinstance(latest_point, list) and len(latest_point) >= 2:
                                        duration_value = latest_point[1]
                                    elif hasattr(latest_point, 'value'):
                                        duration_value = latest_point.value
                                    
                                    if duration_value is not None:
                                        trigger_durations[trigger_name] = float(duration_value)
                                
                            except Exception as parse_error:
                                errors += 1
                                if debug_mode:
                                    response += f"   ⚠️ **Parse Error**: {str(parse_error)}\n"
                        
                        response += f"   📊 **Processing Summary**: {len(series_list)} series processed, {errors} errors\n"
                        response += f"   ✅ **Successfully extracted {len(trigger_durations)} triggers with duration data!**\n\n"
                        break
                    else:
                        response += f"   📭 **No Data Found**\n"
                        
                except Exception as pattern_error:
                    response += f"   ❌ **Pattern Failed**: {str(pattern_error)[:100]}...\n"
            
            # Display results
            if trigger_durations:
                sorted_triggers = sorted(trigger_durations.items(), key=lambda x: x[1], reverse=True)
                total_duration = sum(trigger_durations.values())
                
                response += f"📊 **TOP TRIGGERS BY DURATION**:\n"
                for i, (trigger, duration) in enumerate(sorted_triggers[:top_n], 1):
                    percentage = (duration / total_duration * 100) if total_duration > 0 else 0
                    
                    # Format duration appropriately
                    if duration < 60:
                        duration_str = f"{duration:.2f}s"
                    elif duration < 3600:
                        duration_str = f"{duration/60:.2f}m"
                    else:
                        duration_str = f"{duration/3600:.2f}h"
                    
                    response += f"   {i:2d}. **{trigger}**: {duration_str} ({percentage:.1f}%) [avg]\n"
                
                # Add more triggers if requested
                if len(sorted_triggers) > top_n:
                    response += f"   ... and {len(sorted_triggers) - top_n} more triggers\n"
                
                response += f"\n⏱️ **TOTAL AVERAGE DURATION**: {total_duration:.2f}s\n"
                response += f"🎯 **WORKING QUERY**: `{working_query}`\n"
                
                # Find the slowest trigger
                if sorted_triggers:
                    slowest_trigger, slowest_duration = sorted_triggers[0]
                    response += f"🐌 **SLOWEST TRIGGER**: {slowest_trigger} ({slowest_duration:.2f}s)\n"
                
            else:
                response += "📭 **No duration data found**.\n\n"
                response += "💡 **Troubleshooting**:\n"
                response += "• Verify the service name is correct\n"
                response += "• Check if duration metrics exist for this service\n"
                response += "• Try different time ranges\n"
                response += "• Duration metrics might use different naming conventions\n"
                response += "• Some services might not have trigger-level duration tracking\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get trigger duration analysis: {e}", "datadog")
            return f"❌ Error getting trigger duration analysis: {str(e)}"

    @mcp.tool()
    async def datadog_dashboard_universal_analyzer(
        dashboard_id: str,
        widget_filter: Optional[str] = None,
        time_range: str = "24h",
        organization_filter: Optional[str] = None,
        max_results: int = 20
    ) -> str:
        """DataDog Universal Dashboard Analyzer: Generic pipeline to extract queries from any dashboard widget and execute them.
        
        This is the flexible, generic tool that:
        1. Gets dashboard structure
        2. Extracts widgets (all or filtered by name)
        3. Finds actual queries within widgets
        4. Executes those queries
        5. Returns formatted results
        
        Works with ANY dashboard structure, not specific to any company or use case.
        
        Args:
            dashboard_id: DataDog dashboard ID
            widget_filter: Optional widget title filter (partial match)
            time_range: Time range (1h, 24h, 7d, 30d)
            organization_filter: Optional organization filter to apply to queries
            max_results: Maximum number of results to show per query
        """
        logger.info(f"🔍 Universal analysis of dashboard {dashboard_id}...")
        
        try:
            output = f"🌐 **UNIVERSAL DASHBOARD ANALYZER**\n\n"
            output += f"📊 **Dashboard ID**: {dashboard_id}\n"
            output += f"🎯 **Widget Filter**: {widget_filter or 'All widgets'}\n"
            output += f"⏰ **Time Range**: {time_range}\n"
            output += f"🏢 **Organization Filter**: {organization_filter or 'None'}\n\n"
            
            # Step 1: Get dashboard structure
            dashboards_client = datadog_provider.get_client("dashboards")
            dashboard = await dashboards_client.get_dashboard(dashboard_id)
            
            output += f"✅ **Dashboard**: {dashboard.get('title', 'Untitled')}\n"
            widgets = dashboard.get('widgets', [])
            output += f"📈 **Total Widgets**: {len(widgets)}\n\n"
            
            # Step 2: Extract template variables for query modification
            template_vars = dashboard.get('template_variables', [])
            template_substitutions = {}
            
            if template_vars:
                output += f"🔧 **Template Variables Found**:\n"
                for var in template_vars:
                    var_name = var.get('name', '')
                    var_default = var.get('default', '*')
                    template_substitutions[var_name] = organization_filter if organization_filter and 'org' in var_name.lower() else var_default
                    output += f"   - {var_name}: {template_substitutions[var_name]}\n"
                output += "\n"
            
            # Step 3: Process widgets
            metrics_client = datadog_provider.get_client("metrics")
            
            # Convert time range
            time_hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(time_range, 24)
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_hours)
            
            total_queries_found = 0
            total_queries_executed = 0
            total_results_found = 0
            
            for widget_idx, widget in enumerate(widgets):
                widget_def = widget.get('definition', {})
                widget_title = widget_def.get('title', f'Widget {widget_idx}')
                widget_type = str(widget_def.get('type', 'unknown'))
                
                # Apply widget filter if specified
                if widget_filter and widget_filter.lower() not in widget_title.lower():
                    continue
                
                output += f"## **Widget {widget_idx}: {widget_title}**\n"
                output += f"📊 **Type**: {widget_type}\n"
                
                # Step 4: Extract queries from widget
                queries_found = []
                
                # Handle different widget types
                if widget_type == 'group':
                    # Group widgets might have nested widgets
                    nested_widgets = widget_def.get('widgets', [])
                    if nested_widgets:
                        output += f"📦 **Group with {len(nested_widgets)} nested widgets**\n"
                        for nested_idx, nested_widget in enumerate(nested_widgets):
                            nested_def = nested_widget.get('definition', {})
                            nested_requests = nested_def.get('requests', [])
                            for req in nested_requests:
                                query = req.get('q', req.get('query', ''))
                                if query:
                                    queries_found.append(f"nested[{nested_idx}]: {query}")
                    else:
                        output += f"📦 **Empty group widget - reconstructing likely queries**\n"
                        # Try to infer queries based on widget title
                        if any(keyword in widget_title.lower() for keyword in ['cost', 'trigger', 'expense']):
                            service_name = 'carma' if 'carma' in widget_title.lower() else 'unknown'
                            # Generate likely queries
                            inferred_queries = [
                                f"sum:{service_name}.trigger.cost{{*}} by {{trigger}}",
                                f"sum:{service_name}.trigger.cost{{*}} by {{organization}}",
                                f"avg:{service_name}.trigger.cost{{*}} by {{trigger}}",
                            ]
                            for query in inferred_queries:
                                queries_found.append(f"inferred: {query}")
                
                else:
                    # Regular widgets
                    requests = widget_def.get('requests', [])
                    if requests:
                        output += f"📋 **Found {len(requests)} requests**\n"
                        for req_idx, request in enumerate(requests):
                            query = request.get('q', request.get('query', ''))
                            if query:
                                queries_found.append(f"request[{req_idx}]: {query}")
                    else:
                        output += f"📭 **No requests found**\n"
                
                total_queries_found += len(queries_found)
                
                if not queries_found:
                    output += f"   ❌ No queries found\n\n"
                    continue
                
                # Step 5: Execute queries and format results
                output += f"🔍 **Found {len(queries_found)} queries:**\n"
                
                for query_info in queries_found:
                    query_source, query = query_info.split(': ', 1)
                    output += f"\n🎯 **Query** ({query_source}): `{query}`\n"
                    
                    try:
                        # Apply template variable substitutions
                        modified_query = query
                        for var_name, var_value in template_substitutions.items():
                            modified_query = modified_query.replace(f'${var_name}', var_value)
                            modified_query = modified_query.replace(f'{{{var_name}}}', var_value)
                        
                        # Apply organization filter if specified and not already in query
                        if organization_filter and 'organization:' not in modified_query:
                            # Add organization filter to query
                            if '{*}' in modified_query:
                                modified_query = modified_query.replace('{*}', f'{{organization:{organization_filter}}}')
                            elif '{' in modified_query and '}' in modified_query:
                                # Add to existing filter
                                bracket_start = modified_query.find('{')
                                bracket_end = modified_query.find('}', bracket_start)
                                existing_filter = modified_query[bracket_start+1:bracket_end]
                                if existing_filter == '*':
                                    new_filter = f'organization:{organization_filter}'
                                else:
                                    new_filter = f'{existing_filter},organization:{organization_filter}'
                                modified_query = modified_query[:bracket_start+1] + new_filter + modified_query[bracket_end:]
                        
                        if modified_query != query:
                            output += f"   📝 **Modified**: `{modified_query}`\n"
                        
                        # Execute query
                        result = await metrics_client.query_metrics(
                            query=modified_query,
                            start_time=int(start_time.timestamp()),
                            end_time=int(end_time.timestamp())
                        )
                        
                        total_queries_executed += 1
                        
                        if result and 'series' in result and result['series']:
                            series_count = len(result['series'])
                            output += f"   ✅ **{series_count} series found**\n"
                            
                            # Parse and display results
                            parsed_results = []
                            
                            for series in result['series'][:max_results]:
                                scope = series.get('scope', '')
                                points = series.get('points', [])
                                metric_name = series.get('metric', 'unknown')
                                
                                if points:
                                    total_value = 0
                                    point_count = 0
                                    
                                    for point in points:
                                        try:
                                            if isinstance(point, dict):
                                                value = float(point.get('value', 0))
                                            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                                                value = float(point[1])
                                            else:
                                                value = float(point)
                                            
                                            total_value += value
                                            point_count += 1
                                        except (ValueError, TypeError):
                                            continue
                                    
                                    if total_value >= 0:
                                        # Extract key from scope for grouping
                                        group_key = "unknown"
                                        if scope:
                                            # Parse scope like "trigger:name" or "organization:name"
                                            for part in scope.split(','):
                                                if ':' in part:
                                                    key, value = part.split(':', 1)
                                                    group_key = value.strip()
                                                    break
                                        
                                        parsed_results.append((group_key, total_value, point_count))
                            
                            if parsed_results:
                                # Sort by value (highest first)
                                parsed_results.sort(key=lambda x: x[1], reverse=True)
                                total_results_found += len(parsed_results)
                                
                                output += f"   📊 **Top Results**:\n"
                                for i, (name, value, points) in enumerate(parsed_results[:max_results], 1):
                                    output += f"      {i:2d}. **{name}**: ${value:.2f} [{points} points]\n"
                                
                                if len(parsed_results) > max_results:
                                    output += f"      ... and {len(parsed_results) - max_results} more\n"
                                
                                # Highlight top result
                                if parsed_results:
                                    top_name, top_value, _ = parsed_results[0]
                                    output += f"   🏆 **TOP RESULT**: {top_name} (${top_value:.2f})\n"
                        else:
                            output += f"   ❌ No data returned\n"
                        
                    except Exception as query_error:
                        output += f"   ❌ Query failed: {str(query_error)[:80]}...\n"
                
                output += "\n"
            
            # Summary
            output += f"📋 **ANALYSIS SUMMARY**:\n"
            output += f"   🔍 Queries found: {total_queries_found}\n"
            output += f"   ✅ Queries executed: {total_queries_executed}\n"
            output += f"   📊 Results found: {total_results_found}\n"
            
            if total_results_found == 0:
                output += f"\n💡 **Troubleshooting Tips**:\n"
                output += f"   • Try different widget_filter values\n"
                output += f"   • Check if organization_filter matches your data\n"
                output += f"   • Verify dashboard contains metric widgets\n"
                output += f"   • Some dashboards use log-based widgets (not supported)\n"
            
            return output
            
        except Exception as e:
            logger.error(f"Universal dashboard analysis failed: {e}", "datadog")
            import traceback
            return f"❌ Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"

    @mcp.tool()
    async def datadog_dashboard_comprehensive_extractor(
        dashboard_id: str,
        time_range: str = "24h",
        debug_mode: bool = False
    ) -> str:
        """DataDog Dashboard Comprehensive Extractor: Extract ALL types of metrics data from any dashboard.
        
        This tool systematically discovers and extracts ALL metrics from a dashboard including:
        - Cost metrics (trigger costs, organization costs)  
        - Duration metrics (average duration, execution time)
        - Runtime metrics (hours per trigger, runtime hours)
        - Usage metrics (counts, utilization)
        - Performance metrics (latency, throughput)
        
        Args:
            dashboard_id: Dashboard ID to analyze comprehensively
            time_range: Time range (1h, 24h, 7d, 30d)
            debug_mode: Show detailed debugging information
        """
        logger.info(f"🔍 Comprehensively extracting ALL metrics from dashboard {dashboard_id}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            metrics_client = datadog_provider.get_client("metrics")
            
            # Get dashboard structure
            dashboard = await client.get_dashboard(dashboard_id)
            if not dashboard or 'widgets' not in dashboard:
                return f"❌ Dashboard {dashboard_id} not found or has no widgets"
            
            # Parse time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)
            
            response = f"🔍 **COMPREHENSIVE DASHBOARD METRICS EXTRACTION**\n\n"
            response += f"📊 **Dashboard**: {dashboard.get('title', 'Unknown')} (ID: {dashboard_id})\n"
            response += f"📈 **Total Widgets**: {len(dashboard['widgets'])}\n"
            response += f"⏰ **Time Range**: {time_range}\n\n"
            
            # Comprehensive metric patterns to test
            all_metric_patterns = {
                'carma': [
                    # Cost patterns
                    "sum:carma.trigger.cost{*} by {trigger}",
                    "sum:carma.trigger.cost{*} by {organization}",
                    "sum:carma.organization.cost{*} by {organization}",
                    "sum:carma.cost{*} by {trigger}",
                    "sum:carma.cost{*} by {organization}",
                    "avg:carma.trigger.cost{*} by {trigger}",
                    
                    # Duration patterns  
                    "avg:carma.trigger.duration{*} by {trigger}",
                    "avg:carma.duration{*} by {trigger}",
                    "avg:carma.trigger.avg_execution_time{*} by {trigger}",
                    "avg:carma.avg_execution_time{*} by {trigger}",
                    "avg:carma.execution_time{*} by {trigger}",
                    "avg:carma.trigger.execution_time{*} by {trigger}",
                    "avg:carma.trigger.avg_duration{*} by {trigger}",
                    "avg:carma.avg_duration{*} by {trigger}",
                    "avg:carma.response_time{*} by {trigger}",
                    "avg:carma.processing_time{*} by {trigger}",
                    "max:carma.trigger.duration{*} by {trigger}",
                    "max:carma.duration{*} by {trigger}",
                    "sum:carma.trigger.duration{*} by {trigger}",
                    "sum:carma.duration{*} by {trigger}",
                    
                    # Runtime patterns
                    "sum:carma.runtime.hours{*} by {trigger}",
                    "sum:carma.runtime.hours{*} by {organization}",
                    "avg:carma.runtime{*} by {trigger}",
                    "avg:carma.runtime{*} by {organization}",
                    "sum:carma.hours{*} by {trigger}",
                    "sum:carma.hours{*} by {organization}",
                    "avg:carma.trigger.runtime{*} by {trigger}",
                    
                    # Usage/Count patterns
                    "count:carma.trigger{*} by {trigger}",
                    "count:carma.trigger{*} by {organization}",
                    "sum:carma.trigger.count{*} by {trigger}",
                    "sum:carma.count{*} by {trigger}",
                    "sum:carma.usage{*} by {trigger}",
                    "sum:carma.usage{*} by {organization}",
                    
                    # Tenant/Organization patterns
                    "count:carma.tenants{*}",
                    "count_nonzero:carma.trigger{*} by {organization}",
                    
                    # Performance patterns
                    "avg:carma.cpu.usage{*} by {trigger}",
                    "avg:carma.memory.usage{*} by {trigger}",
                    "avg:carma.latency{*} by {trigger}",
                    "avg:carma.throughput{*} by {trigger}"
                ]
            }
            
            all_results = {}
            working_queries = []
            
            # Test all patterns
            for service, patterns in all_metric_patterns.items():
                response += f"🔍 **Testing {service.upper()} Metrics**\n\n"
                
                for pattern in patterns:
                    try:
                        if debug_mode:
                            response += f"   🧪 Testing: `{pattern}`\n"
                        
                        metrics_data = await metrics_client.query_metrics(
                            query=pattern,
                            start_time=int(start_time.timestamp()),
                            end_time=int(end_time.timestamp())
                        )
                        
                        if metrics_data.get('series') and len(metrics_data['series']) > 0:
                            series_list = metrics_data['series']
                            
                            # Determine metric type from pattern
                            metric_type = "Unknown"
                            unit = ""
                            if 'cost' in pattern:
                                metric_type = "Cost"
                                unit = "$"
                            elif 'duration' in pattern or 'execution_time' in pattern:
                                metric_type = "Duration" 
                                unit = "s"
                            elif 'runtime' in pattern or 'hours' in pattern:
                                metric_type = "Runtime"
                                unit = "h"
                            elif 'count' in pattern or 'usage' in pattern:
                                metric_type = "Count/Usage"
                                unit = ""
                            elif 'cpu' in pattern or 'memory' in pattern:
                                metric_type = "Performance"
                                unit = "%"
                            elif 'latency' in pattern or 'response_time' in pattern:
                                metric_type = "Latency"
                                unit = "ms"
                                
                            # Determine breakdown dimension
                            breakdown_by = "organization"
                            if "by {trigger}" in pattern:
                                breakdown_by = "trigger"
                            elif "by {organization}" in pattern:
                                breakdown_by = "organization"
                            elif "by {host}" in pattern:
                                breakdown_by = "host"
                                
                            response += f"   ✅ **FOUND DATA**: {metric_type} by {breakdown_by} ({len(series_list)} series)\n"
                            working_queries.append(pattern)
                            
                            # Extract and format data
                            item_values = {}
                            for series in series_list:
                                scope = series.get('scope', '')
                                points = series.get('points', [])
                                
                                # Extract item name from scope
                                item_name = "unknown"
                                if f'{breakdown_by}:' in scope:
                                    for part in scope.split(','):
                                        if f'{breakdown_by}:' in part:
                                            item_name = part.replace(f'{breakdown_by}:', '').strip()
                                            break
                                
                                # Get latest value
                                if points:
                                    latest_point = points[-1]
                                    value = None
                                    
                                    if isinstance(latest_point, dict):
                                        value = latest_point.get('value')
                                    elif isinstance(latest_point, list) and len(latest_point) >= 2:
                                        value = latest_point[1]
                                    
                                    if value is not None:
                                        item_values[item_name] = float(value)
                            
                            # Store and display results
                            if item_values:
                                sorted_items = sorted(item_values.items(), key=lambda x: x[1], reverse=True)
                                total_value = sum(item_values.values())
                                
                                result_key = f"{metric_type}_{breakdown_by}"
                                all_results[result_key] = {
                                    'type': metric_type,
                                    'breakdown': breakdown_by,
                                    'unit': unit,
                                    'query': pattern,
                                    'data': sorted_items,
                                    'total': total_value
                                }
                                
                                response += f"      📊 **Top 10 {metric_type} by {breakdown_by.title()}**:\n"
                                for i, (item, value) in enumerate(sorted_items[:10], 1):
                                    if metric_type == "Duration":
                                        # Format duration appropriately
                                        if value < 60:
                                            value_str = f"{value:.2f}s"
                                        elif value < 3600:
                                            value_str = f"{value/60:.2f}m"
                                        else:
                                            value_str = f"{value/3600:.2f}h"
                                    else:
                                        value_str = f"{unit}{value:.2f}"
                                    
                                    response += f"         {i:2d}. {item}: {value_str}\n"
                                
                                response += f"      📈 **Total**: {unit}{total_value:.2f}\n"
                                response += "\n"
                        
                        elif debug_mode:
                            response += f"   📭 No data\n"
                            
                    except Exception as e:
                        if debug_mode:
                            response += f"   ❌ Error: {str(e)[:50]}...\n"
            
            # Summary of all findings
            response += f"📋 **EXTRACTION SUMMARY**\n\n"
            response += f"🔍 **Working Queries Found**: {len(working_queries)}\n"
            response += f"📊 **Data Types Extracted**: {len(all_results)}\n\n"
            
            if all_results:
                response += f"🎯 **Available Data Types**:\n"
                for key, result in all_results.items():
                    response += f"   ✅ {result['type']} by {result['breakdown'].title()}: {len(result['data'])} items\n"
                
                response += f"\n🔧 **Working Queries**:\n"
                for query in working_queries:
                    response += f"   • `{query}`\n"
            else:
                response += "❌ **No metric data found**. Dashboard may use log-based widgets or custom metrics.\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Dashboard comprehensive extraction failed: {e}", provider="datadog")
            return f"❌ Error in comprehensive extraction: {str(e)}"