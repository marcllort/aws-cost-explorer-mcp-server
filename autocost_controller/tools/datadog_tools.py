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