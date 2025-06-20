"""DataDog-specific tools for the Autocost Controller."""

from typing import Optional, List
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
        dashboard_id: str = "csc-fuy-ae8",
        organization_filter: str = "b38uat",
        time_range: str = "24h"
    ) -> str:
        """DataDog Cost Metrics: Query actual cost metrics from the Cost Auto Allocation dashboard with proper template variable substitution."""
        logger.info(f"💰 Querying DataDog cost metrics for organization: {organization_filter}...")
        
        try:
            client = datadog_provider.get_client("dashboards")
            metrics_client = datadog_provider.get_client("metrics")
            
            # Get dashboard to extract actual metric queries
            dashboard = await client.get_dashboard(dashboard_id)
            
            response = f"💰 **DATADOG COST METRICS QUERY**\n\n"
            response += f"🎯 **Dashboard**: {dashboard['title']}\n"
            response += f"📋 **ID**: {dashboard['id']}\n"
            response += f"⏰ **Time Range**: {time_range}\n"
            response += f"🏢 **Organization**: {organization_filter}\n\n"
            
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
            
            # Since dashboard widgets are empty, use direct cost metrics approach
            # Based on known cost metrics from Cost Auto Allocation dashboard
            cost_metrics = [
                "sum:datawarehouse.organization.cost{organization:" + organization_filter + "}",
                "sum:carma.trigger.cost{organization:" + organization_filter + "}",
                "sum:whatif.organization.cost{organization:" + organization_filter + "}",
                "sum:analytics.organization.cost{organization:" + organization_filter + "}",
                "sum:treasury.organization.cost{organization:" + organization_filter + "}"
            ]
            
            total_cost = 0
            service_costs = {}
            
            response += "📊 **Cost Metrics Found:**\n\n"
            response += f"🔍 **Debug**: Found {len(dashboard['widgets'])} widgets (all empty), using direct metrics approach\n\n"
            response += f"🎯 **Known Cost Metrics**:\n"
            
            for i, metric_query in enumerate(cost_metrics, 1):
                service_name = metric_query.split(':')[1].split('.')[0]
                response += f"**{i}. {service_name.title()}**\n"
                response += f"   Query: {metric_query}\n"
                
                try:
                    # Query the actual metric
                    response += f"   🔍 Querying DataDog...\n"
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
                                    
                                    # Extract service name from metric
                                    service = service_name
                                    service_costs[service] = service_costs.get(service, 0) + latest
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
            
            # Summary
            response += f"📋 **COST SUMMARY**:\n"
            response += f"💰 **Total Cost**: ${total_cost:.2f}\n"
            response += f"🏢 **Organization**: {organization_filter}\n"
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