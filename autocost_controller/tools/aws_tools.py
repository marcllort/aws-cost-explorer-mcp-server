"""AWS-specific MCP tools for Autocost Controller."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP

from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger
from ..core.models import AWSParams, FlexibleAnalysisParams, PerformanceParams


def register_aws_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register all AWS-specific MCP tools."""
    
    aws_provider = provider_manager.get_provider("aws")
    if not aws_provider:
        logger.warning("AWS provider not available, skipping AWS tools registration")
        return
    
    logger.info("🔧 Registering AWS Cost Explorer tools...")
    
    @mcp.tool()
    async def aws_cost_explorer_discover_dimensions(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Cost Explorer: Discover all available dimensions for cost analysis."""
        import asyncio
        
        logger.info(f"🔍 Discovering AWS Cost Explorer dimensions for {days} days...")
        
        try:
            async def discover_dimensions_with_timeout():
                logger.info(f"🔍 Connecting to AWS Cost Explorer...")
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS Cost Explorer")
                
                # Get date range
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                logger.info(f"📅 Querying period: {start_date} to {end_date}")
                
                # Get all available dimensions
                dimensions = [
                    'AZ', 'INSTANCE_TYPE', 'LINKED_ACCOUNT', 'OPERATION', 'PURCHASE_TYPE',
                    'REGION', 'SERVICE', 'USAGE_TYPE', 'USAGE_TYPE_GROUP', 'RECORD_TYPE',
                    'OPERATING_SYSTEM', 'TENANCY', 'SCOPE', 'PLATFORM', 'SUBSCRIPTION_ID',
                    'LEGAL_ENTITY_NAME', 'DEPLOYMENT_OPTION', 'DATABASE_ENGINE',
                    'CACHE_ENGINE', 'INSTANCE_TYPE_FAMILY', 'BILLING_ENTITY', 'RESERVATION_ID',
                    'RESOURCE_ID', 'RIGHTSIZING_TYPE', 'SAVINGS_PLANS_TYPE', 'SAVINGS_PLAN_ARN',
                    'PAYMENT_OPTION', 'AGREEMENT_END_DATE_TIME_AFTER', 'AGREEMENT_END_DATE_TIME_BEFORE'
                ]
                
                output = ["🔍 **AWS COST EXPLORER DIMENSIONS**", "=" * 50]
                logger.info(f"🔄 Testing {len(dimensions)} dimensions...")
                
                successful_dimensions = 0
                for i, dimension in enumerate(dimensions, 1):
                    try:
                        logger.info(f"🔍 Testing dimension {i}/{len(dimensions)}: {dimension}")
                        response = ce_client.get_dimension_values(
                            TimePeriod={
                                'Start': start_date.strftime('%Y-%m-%d'),
                                'End': end_date.strftime('%Y-%m-%d')
                            },
                            Dimension=dimension,
                            Context='COST_AND_USAGE',
                            MaxResults=5
                        )
                        
                        values = [item['Value'] for item in response.get('DimensionValues', [])]
                        total_count = response.get('TotalSize', 0)
                        
                        if values:
                            output.append(f"\n📊 **{dimension}** ({total_count} total values)")
                            output.append(f"   Sample values: {', '.join(values[:3])}")
                            if total_count > 3:
                                output.append(f"   ... and {total_count - 3} more")
                            successful_dimensions += 1
                        
                    except Exception as e:
                        if "InvalidDimensionKey" not in str(e):
                            output.append(f"\n⚠️ **{dimension}**: Error - {str(e)}")
                            logger.warning(f"Dimension {dimension} failed: {e}")
                
                logger.info(f"✅ Successfully tested {successful_dimensions} dimensions")
                output.append(f"\n📈 **Analysis Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"🔧 **Usage**: Use `aws_cost_explorer_analyze_by_dimension(dimension_name)` to analyze any dimension")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (60 seconds for this more complex operation)
            result = await asyncio.wait_for(discover_dimensions_with_timeout(), timeout=60.0)
            logger.info(f"✅ Successfully completed dimension discovery")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS dimension discovery took longer than 60 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error discovering dimensions: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_cost_explorer_get_dimension_values(
        dimension: str,
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        max_results: int = 50
    ) -> str:
        """AWS Cost Explorer: Get all values for a specific dimension."""
        import asyncio
        
        logger.info(f"📋 Getting values for dimension: {dimension}")
        
        try:
            # Add timeout to prevent hanging
            async def get_dimension_values_with_timeout():
                logger.info(f"🔍 Connecting to AWS Cost Explorer...")
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS Cost Explorer")
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                logger.info(f"📅 Querying period: {start_date} to {end_date}")
                
                logger.info(f"🔄 Making API call for dimension: {dimension}")
                response = ce_client.get_dimension_values(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Dimension=dimension,
                    Context='COST_AND_USAGE',
                    MaxResults=max_results
                )
                logger.info(f"✅ API call completed successfully")
                
                values = response.get('DimensionValues', [])
                total_count = response.get('TotalSize', 0)
                logger.info(f"📊 Received {len(values)} values (total: {total_count})")
                
                output = [f"📋 **{dimension} VALUES**", "=" * 50]
                output.append(f"📊 **Total Count**: {total_count}")
                output.append(f"📅 **Period**: {start_date} to {end_date}")
                
                if values:
                    output.append(f"\n🔍 **Available Values** (showing {len(values)} of {total_count}):")
                    for i, item in enumerate(values, 1):
                        value = item['Value']
                        attributes = item.get('Attributes', {})
                        
                        output.append(f"{i:2d}. {value}")
                        if attributes:
                            for key, attr_value in attributes.items():
                                output.append(f"     {key}: {attr_value}")
                else:
                    output.append("\n⚠️ No values found for this dimension in the specified time period")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (30 seconds)
            result = await asyncio.wait_for(get_dimension_values_with_timeout(), timeout=30.0)
            logger.info(f"✅ Successfully completed dimension values query")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS Cost Explorer query for dimension '{dimension}' took longer than 30 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error getting dimension values: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_cost_explorer_analyze_by_dimension(
        dimension: str,
        group_by_dimensions: Optional[List[str]] = None,
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        services: Optional[List[str]] = None,
        top_n: int = 10
    ) -> str:
        """AWS Cost Explorer: Analyze costs by any dimension with optional grouping and filtering."""
        logger.info(f"📊 Analyzing costs by dimension: {dimension}")
        
        try:
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Build group by clause
            group_by = [{'Type': 'DIMENSION', 'Key': dimension}]
            if group_by_dimensions:
                for dim in group_by_dimensions:
                    group_by.append({'Type': 'DIMENSION', 'Key': dim})
            
            # Build filter if services specified
            filter_expr = None
            if services:
                filter_expr = {
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': services,
                        'MatchOptions': ['EQUALS']
                    }
                }
            
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost', 'UnblendedCost', 'UsageQuantity'],
                GroupBy=group_by,
                Filter=filter_expr
            )
            
            # Process results
            dimension_costs = {}
            total_cost = 0.0
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    keys = group.get('Keys', [])
                    if keys:
                        key = ' | '.join(keys)
                        cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                        
                        if key not in dimension_costs:
                            dimension_costs[key] = 0.0
                        dimension_costs[key] += cost
                        total_cost += cost
            
            # Sort by cost
            sorted_costs = sorted(dimension_costs.items(), key=lambda x: x[1], reverse=True)
            
            output = [f"📊 **COST ANALYSIS BY {dimension.upper()}**", "=" * 60]
            output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
            output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
            output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
            
            if services:
                output.append(f"🔍 **Filtered by Services**: {', '.join(services)}")
            
            if group_by_dimensions:
                output.append(f"📋 **Grouped by**: {dimension} + {', '.join(group_by_dimensions)}")
            
            output.append(f"\n🏆 **TOP {min(top_n, len(sorted_costs))} BY COST**:")
            
            for i, (key, cost) in enumerate(sorted_costs[:top_n], 1):
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                daily_avg = cost / days
                
                output.append(f"{i:2d}. **{key}**")
                output.append(f"     💰 ${cost:.2f} ({percentage:.1f}%)")
                output.append(f"     📈 ${daily_avg:.2f}/day")
            
            if len(sorted_costs) > top_n:
                remaining_cost = sum(cost for _, cost in sorted_costs[top_n:])
                remaining_percentage = (remaining_cost / total_cost * 100) if total_cost > 0 else 0
                output.append(f"\n📊 **Others**: ${remaining_cost:.2f} ({remaining_percentage:.1f}%)")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error analyzing by dimension: {str(e)}")
            return f"❌ Error analyzing by dimension: {str(e)}"
    
    # TAG ANALYSIS TOOLS
    @mcp.tool()
    async def aws_cost_explorer_list_tag_keys(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        max_results: int = 100
    ) -> str:
        """AWS Cost Explorer: List all available tag keys for cost analysis."""
        logger.info(f"🏷️ Listing AWS tag keys for {days} days...")
        
        try:
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            response = ce_client.get_dimension_values(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Dimension='TAG_KEY',
                Context='COST_AND_USAGE',
                MaxResults=max_results
            )
            
            tag_keys = [item['Value'] for item in response.get('DimensionValues', [])]
            total_count = response.get('TotalSize', 0)
            
            output = ["🏷️ **AVAILABLE TAG KEYS**", "=" * 40]
            output.append(f"📊 **Total Tag Keys**: {total_count}")
            output.append(f"📅 **Period**: {start_date} to {end_date}")
            
            if tag_keys:
                output.append(f"\n🔍 **Tag Keys** (showing {len(tag_keys)} of {total_count}):")
                
                # Group common tag patterns
                aws_tags = [key for key in tag_keys if key.startswith('aws:')]
                name_tags = [key for key in tag_keys if 'name' in key.lower()]
                env_tags = [key for key in tag_keys if any(env in key.lower() for env in ['env', 'environment', 'stage'])]
                cost_tags = [key for key in tag_keys if any(cost in key.lower() for cost in ['cost', 'billing', 'budget'])]
                other_tags = [key for key in tag_keys if key not in aws_tags + name_tags + env_tags + cost_tags]
                
                if name_tags:
                    output.append(f"\n📛 **Name Tags** ({len(name_tags)}):")
                    for tag in sorted(name_tags)[:10]:
                        output.append(f"   • {tag}")
                
                if env_tags:
                    output.append(f"\n🌍 **Environment Tags** ({len(env_tags)}):")
                    for tag in sorted(env_tags)[:10]:
                        output.append(f"   • {tag}")
                
                if cost_tags:
                    output.append(f"\n💰 **Cost/Billing Tags** ({len(cost_tags)}):")
                    for tag in sorted(cost_tags)[:10]:
                        output.append(f"   • {tag}")
                
                if aws_tags:
                    output.append(f"\n☁️ **AWS System Tags** ({len(aws_tags)}):")
                    for tag in sorted(aws_tags)[:5]:
                        output.append(f"   • {tag}")
                
                if other_tags:
                    output.append(f"\n📋 **Other Tags** ({len(other_tags)}):")
                    for tag in sorted(other_tags)[:10]:
                        output.append(f"   • {tag}")
                
                output.append(f"\n🔧 **Usage**: Use `aws_cost_explorer_analyze_by_tag('tag_key')` to analyze costs by any tag")
            else:
                output.append("\n⚠️ No tag keys found in the specified time period")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error listing tag keys: {str(e)}")
            return f"❌ Error listing tag keys: {str(e)}"

    @mcp.tool()
    async def aws_cost_explorer_analyze_by_name_tag(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        top_n: int = 15
    ) -> str:
        """AWS Cost Explorer: Analyze costs by Name tag values with detailed breakdown."""
        logger.info(f"📛 Analyzing costs by Name tag for {days} days...")
        
        try:
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Try common Name tag variations
            name_tags = ['Name', 'name', 'NAME']
            results_found = False
            
            for name_tag in name_tags:
                try:
                    response = ce_client.get_cost_and_usage(
                        TimePeriod={
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        Granularity='DAILY',
                        Metrics=['BlendedCost', 'UnblendedCost'],
                        GroupBy=[
                            {'Type': 'TAG', 'Key': name_tag},
                            {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                        ]
                    )
                    
                    if response.get('ResultsByTime'):
                        results_found = True
                        break
                        
                except Exception:
                    continue
            
            if not results_found:
                return f"❌ No results found for Name tags. Available tags: Use `aws_cost_explorer_list_tag_keys()` to see available tags."
            
            # Process results
            name_costs = {}
            service_breakdown = {}
            total_cost = 0.0
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    keys = group.get('Keys', [])
                    if len(keys) >= 2:
                        name_value = keys[0] if keys[0] != 'No tag' else 'Untagged'
                        service = keys[1]
                        cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                        
                        if name_value not in name_costs:
                            name_costs[name_value] = 0.0
                            service_breakdown[name_value] = {}
                        
                        name_costs[name_value] += cost
                        total_cost += cost
                        
                        if service not in service_breakdown[name_value]:
                            service_breakdown[name_value][service] = 0.0
                        service_breakdown[name_value][service] += cost
            
            # Sort by cost
            sorted_names = sorted(name_costs.items(), key=lambda x: x[1], reverse=True)
            
            output = [f"📛 **COST ANALYSIS BY NAME TAG** ({name_tag})", "=" * 60]
            output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
            output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
            output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
            output.append(f"🏷️ **Tagged Resources**: {len([n for n in sorted_names if n[0] != 'Untagged'])}")
            
            output.append(f"\n🏆 **TOP {min(top_n, len(sorted_names))} BY COST**:")
            
            for i, (name, cost) in enumerate(sorted_names[:top_n], 1):
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                output.append(f"\n{i:2d}. **{name}** - ${cost:.2f} ({percentage:.1f}%)")
                
                # Show top services for this name
                services = sorted(service_breakdown[name].items(), key=lambda x: x[1], reverse=True)[:3]
                output.append(f"    Top services: {', '.join([f'{svc} ${amt:.2f}' for svc, amt in services])}")
            
            # Add untagged resources summary
            untagged_cost = name_costs.get('Untagged', 0)
            if untagged_cost > 0:
                untagged_percentage = (untagged_cost / total_cost * 100) if total_cost > 0 else 0
                output.append(f"\n⚠️ **UNTAGGED RESOURCES**: ${untagged_cost:.2f} ({untagged_percentage:.1f}%)")
                output.append("   💡 Consider adding Name tags to untagged resources for better cost tracking")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error analyzing costs by name tag: {str(e)}")
            return f"❌ Error analyzing costs by name tag: {str(e)}"
    
    @mcp.tool()
    async def aws_cost_explorer_analyze_by_custom_tag(
        tag_key: str,
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        top_n: int = 15
    ) -> str:
        """AWS Cost Explorer: Analyze costs by any custom tag key with detailed breakdown."""
        logger.info(f"🏷️ Analyzing costs by {tag_key} tag for {days} days...")
        
        try:
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'TAG', 'Key': tag_key},
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                ]
            )
            
            # Process results
            tag_costs = {}
            service_breakdown = {}
            total_cost = 0.0
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    keys = group.get('Keys', [])
                    if len(keys) >= 2:
                        tag_value = keys[0] if keys[0] != 'No tag' else f'Untagged ({tag_key})'
                        service = keys[1]
                        cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                        
                        if tag_value not in tag_costs:
                            tag_costs[tag_value] = 0.0
                            service_breakdown[tag_value] = {}
                        
                        tag_costs[tag_value] += cost
                        total_cost += cost
                        
                        if service not in service_breakdown[tag_value]:
                            service_breakdown[tag_value][service] = 0.0
                        service_breakdown[tag_value][service] += cost
            
            if not tag_costs:
                return f"❌ No cost data found for tag '{tag_key}'. Use `aws_cost_explorer_list_tag_keys()` to see available tags."
            
            # Sort by cost
            sorted_tags = sorted(tag_costs.items(), key=lambda x: x[1], reverse=True)
            
            output = [f"🏷️ **COST ANALYSIS BY {tag_key.upper()} TAG**", "=" * 60]
            output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
            output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
            output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
            output.append(f"🏷️ **Tag Values Found**: {len(sorted_tags)}")
            
            output.append(f"\n🏆 **TOP {min(top_n, len(sorted_tags))} BY COST**:")
            
            for i, (tag_value, cost) in enumerate(sorted_tags[:top_n], 1):
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                output.append(f"\n{i:2d}. **{tag_value}** - ${cost:.2f} ({percentage:.1f}%)")
                
                # Show top services for this tag value
                services = sorted(service_breakdown[tag_value].items(), key=lambda x: x[1], reverse=True)[:3]
                output.append(f"    Top services: {', '.join([f'{svc} ${amt:.2f}' for svc, amt in services])}")
            
            # Add untagged resources summary if applicable
            untagged_key = f'Untagged ({tag_key})'
            untagged_cost = tag_costs.get(untagged_key, 0)
            if untagged_cost > 0:
                untagged_percentage = (untagged_cost / total_cost * 100) if total_cost > 0 else 0
                output.append(f"\n⚠️ **UNTAGGED RESOURCES**: ${untagged_cost:.2f} ({untagged_percentage:.1f}%)")
                output.append(f"   💡 Consider adding {tag_key} tags for better cost tracking")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error analyzing by {tag_key} tag: {str(e)}")
            return f"❌ Error analyzing by {tag_key} tag: {str(e)}"

    @mcp.tool()
    async def aws_cost_explorer_analyze_specific_resource(
        name_tag_value: str,
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Cost Explorer: Analyze costs for a specific resource by its Name tag value."""
        logger.info(f"🔍 Analyzing costs for resource: {name_tag_value}")
        
        try:
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Try different Name tag variations
            name_tags = ['Name', 'name', 'NAME']
            results_found = False
            response = None
            
            for name_tag in name_tags:
                try:
                    response = ce_client.get_cost_and_usage(
                        TimePeriod={
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        Granularity='DAILY',
                        Metrics=['BlendedCost', 'UnblendedCost', 'UsageQuantity'],
                        GroupBy=[
                            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                            {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                        ],
                        Filter={
                            'Tags': {
                                'Key': name_tag,
                                'Values': [name_tag_value],
                                'MatchOptions': ['EQUALS']
                            }
                        }
                    )
                    
                    if response.get('ResultsByTime'):
                        results_found = True
                        break
                        
                except Exception:
                    continue
            
            if not results_found or not response:
                return f"❌ No cost data found for resource '{name_tag_value}'. Check the name and try `aws_cost_explorer_analyze_by_name_tag()` to see available resources."
            
            # Process results
            daily_costs = []
            service_costs = {}
            usage_breakdown = {}
            total_cost = 0.0
            
            for result in response.get('ResultsByTime', []):
                day_date = result.get('TimePeriod', {}).get('Start', '')
                day_cost = 0.0
                
                for group in result.get('Groups', []):
                    keys = group.get('Keys', [])
                    if len(keys) >= 2:
                        service = keys[0]
                        usage_type = keys[1]
                        cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                        usage_qty = float(group.get('Metrics', {}).get('UsageQuantity', {}).get('Amount', 0))
                        
                        day_cost += cost
                        total_cost += cost
                        
                        if service not in service_costs:
                            service_costs[service] = 0.0
                        service_costs[service] += cost
                        
                        if service not in usage_breakdown:
                            usage_breakdown[service] = {}
                        if usage_type not in usage_breakdown[service]:
                            usage_breakdown[service][usage_type] = {'cost': 0.0, 'usage': 0.0}
                        
                        usage_breakdown[service][usage_type]['cost'] += cost
                        usage_breakdown[service][usage_type]['usage'] += usage_qty
                
                daily_costs.append((day_date, day_cost))
            
            # Sort services by cost
            sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
            
            output = [f"🔍 **DETAILED COST ANALYSIS: {name_tag_value}**", "=" * 70]
            output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
            output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
            output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
            
            # Daily cost trend
            if daily_costs:
                output.append(f"\n📊 **DAILY COST TREND**:")
                for date, cost in daily_costs[-7:]:  # Show last 7 days
                    output.append(f"   {date}: ${cost:.2f}")
            
            # Service breakdown
            output.append(f"\n🔧 **SERVICE BREAKDOWN**:")
            for i, (service, cost) in enumerate(sorted_services[:10], 1):
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                output.append(f"{i:2d}. **{service}** - ${cost:.2f} ({percentage:.1f}%)")
                
                # Show usage details for this service
                if service in usage_breakdown:
                    top_usage = sorted(
                        usage_breakdown[service].items(), 
                        key=lambda x: x[1]['cost'], 
                        reverse=True
                    )[:3]
                    for usage_type, data in top_usage:
                        output.append(f"    • {usage_type}: ${data['cost']:.2f}")
            
            output.append(f"\n💡 **OPTIMIZATION TIPS**:")
            
            # Check for common optimization opportunities
            if 'Amazon Elastic Compute Cloud - Compute' in service_costs:
                ec2_cost = service_costs['Amazon Elastic Compute Cloud - Compute']
                if ec2_cost > 10:  # If EC2 costs are significant
                    output.append("   • Consider Reserved Instances for steady-state workloads")
                    output.append("   • Evaluate Spot Instances for fault-tolerant workloads")
                    output.append("   • Check if ARM-based instances (Graviton) could reduce costs")
            
            if 'Amazon Simple Storage Service' in service_costs:
                s3_cost = service_costs['Amazon Simple Storage Service']
                if s3_cost > 5:
                    output.append("   • Review S3 storage classes and lifecycle policies")
                    output.append("   • Consider Intelligent Tiering for variable access patterns")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error analyzing specific resource: {str(e)}")
            return f"❌ Error analyzing specific resource: {str(e)}" 