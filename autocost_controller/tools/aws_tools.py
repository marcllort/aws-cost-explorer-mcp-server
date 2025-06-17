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
    
    # Register advanced cost analysis tools
    from .aws_cost_analysis import register_aws_cost_analysis_tools
    register_aws_cost_analysis_tools(mcp, provider_manager, config, logger)
    
    # AWS PROFILE MANAGEMENT TOOLS
    @mcp.tool()
    async def aws_profile_list() -> str:
        """List all available AWS profiles configured on this system."""
        import asyncio
        
        logger.info("📋 Listing available AWS profiles...")
        
        try:
            async def list_profiles_with_timeout():
                profiles = aws_provider.list_available_profiles()
                current_profile = aws_provider.get_current_profile()
                
                output = ["📋 **AVAILABLE AWS PROFILES**", "=" * 40]
                
                if profiles:
                    output.append(f"🔧 **Total Profiles**: {len(profiles)}")
                    output.append(f"📍 **Current Profile**: {current_profile or 'default'}")
                    output.append("")
                    
                    for i, profile in enumerate(sorted(profiles), 1):
                        marker = "👉 " if profile == current_profile else "   "
                        output.append(f"{marker}{i}. **{profile}**")
                        
                        # Try to get profile info (fast version to avoid timeouts)
                        try:
                            info = aws_provider.get_profile_info_fast(profile)
                            if info:
                                output.append(f"      Region: {info.get('region', 'Unknown')}")
                                output.append(f"      Status: {info.get('status', 'Unknown')}")
                        except Exception:
                            output.append(f"      Status: ⚠️ Error accessing profile")
                    
                    output.append(f"\n🔧 **Usage**: Use `aws_profile_switch('profile_name')` to switch profiles")
                    output.append(f"📊 **Info**: Use `aws_profile_info()` for current profile details")
                else:
                    output.append("⚠️ No AWS profiles found")
                    output.append("💡 Configure AWS profiles using: `aws configure --profile <name>`")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (10 seconds for listing)
            result = await asyncio.wait_for(list_profiles_with_timeout(), timeout=10.0)
            logger.info(f"✅ Successfully listed AWS profiles")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS profile listing took longer than 10 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error listing AWS profiles: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_profile_switch(profile_name: str) -> str:
        """Switch to a different AWS profile for subsequent AWS operations."""
        import asyncio
        
        logger.info(f"🔄 Switching to AWS profile: {profile_name}")
        
        try:
            async def switch_profile_with_timeout():
                success = aws_provider.set_profile(profile_name)
                
                if success:
                    # Get profile info to show what we switched to (use fast version)
                    info = aws_provider.get_profile_info_fast()
                    
                    output = ["🔄 **AWS PROFILE SWITCHED**", "=" * 40]
                    output.append(f"✅ **Successfully switched to profile**: {profile_name}")
                    
                    if info:
                        output.append(f"🌍 **Region**: {info.get('region', 'Unknown')}")
                        output.append(f"📊 **Status**: {info.get('status', 'Unknown')}")
                    
                    output.append(f"\n💡 **Note**: All subsequent AWS operations will use this profile")
                    output.append(f"🔧 **Available Tools**: EC2 insights, ECS analysis, and cost optimization")
                    output.append(f"📋 **Check Status**: Use `get_provider_status()` to verify provider capabilities")
                    output.append(f"🔐 **Test Permissions**: Use `aws_test_permissions()` to check access")
                    
                    logger.info(f"✅ Successfully switched to AWS profile: {profile_name}")
                    return "\n".join(output)
                else:
                    error_msg = f"❌ Failed to switch to profile '{profile_name}'. Check if profile exists and has valid credentials."
                    logger.error(error_msg)
                    return error_msg
            
            # Use timeout to prevent hanging (15 seconds for switching)
            result = await asyncio.wait_for(switch_profile_with_timeout(), timeout=15.0)
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS profile switch took longer than 15 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error switching to profile '{profile_name}': {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_profile_info(profile_name: Optional[str] = None) -> str:
        """Get detailed information about an AWS profile (current profile if none specified)."""
        import asyncio
        
        target_profile = profile_name or aws_provider.get_current_profile() or "default"
        logger.info(f"ℹ️ Getting AWS profile info: {target_profile}")
        
        try:
            async def get_profile_info_with_timeout():
                info = aws_provider.get_profile_info(profile_name)
                
                if not info:
                    return f"❌ Could not get information for profile '{target_profile}'"
                
                output = [f"ℹ️ **AWS PROFILE INFO: {target_profile.upper()}**", "=" * 50]
                output.append(f"👤 **Profile Name**: {info.get('profile_name', 'Unknown')}")
                output.append(f"🌍 **Region**: {info.get('region', 'Unknown')}")
                
                # Show account info if available (might be "Unknown" if API timeout)
                account_id = info.get('account_id', 'Unknown')
                if account_id != 'Unknown (API timeout)':
                    output.append(f"📊 **Account ID**: {account_id}")
                    output.append(f"🔐 **User ARN**: {info.get('user_arn', 'Unknown')}")
                    output.append(f"🆔 **User ID**: {info.get('user_id', 'Unknown')}")
                else:
                    output.append(f"📊 **Account ID**: Unknown (API call timeout)")
                    output.append(f"💡 **Note**: Use `aws_test_permissions()` to verify access")
                
                # Check if this is the current profile
                current = aws_provider.get_current_profile()
                if (profile_name and profile_name == current) or (not profile_name and not current):
                    output.append(f"\n✅ **Status**: Currently active profile")
                else:
                    output.append(f"\n📍 **Status**: Available profile (not currently active)")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (20 seconds for profile info)
            result = await asyncio.wait_for(get_profile_info_with_timeout(), timeout=20.0)
            logger.info(f"✅ Successfully got profile info")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: Getting profile info took longer than 20 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error getting profile info: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_profile_reset() -> str:
        """Reset to default AWS credentials (no profile)."""
        import asyncio
        
        logger.info("🔄 Resetting to default AWS credentials")
        
        try:
            async def reset_profile_with_timeout():
                success = aws_provider.set_profile(None)
                
                if success:
                    info = aws_provider.get_profile_info_fast()
                    
                    output = ["🔄 **AWS PROFILE RESET**", "=" * 30]
                    output.append(f"✅ **Reset to default credentials**")
                    
                    if info:
                        output.append(f"🌍 **Region**: {info.get('region', 'Unknown')}")
                    
                    output.append(f"\n💡 **Note**: Now using default AWS credentials")
                    
                    return "\n".join(output)
                else:
                    return "❌ Failed to reset to default credentials"
            
            # Use timeout to prevent hanging (10 seconds for reset)
            result = await asyncio.wait_for(reset_profile_with_timeout(), timeout=10.0)
            logger.info(f"✅ Successfully reset to default profile")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: Profile reset took longer than 10 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error resetting profile: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    # COST EXPLORER DISCOVERY TOOLS
    @mcp.tool()
    async def ping_server() -> str:
        """Test server connectivity and basic AWS access."""
        logger.info("🏓 Testing server connectivity and AWS access...")
        
        try:
            output = ["🏓 **SERVER CONNECTIVITY TEST**", "=" * 40]
            
            # Test current profile info
            current_profile = aws_provider.get_current_profile()
            output.append(f"📍 **Current AWS Profile**: {current_profile or 'default'}")
            
            # Test AWS STS access
            try:
                info = aws_provider.get_profile_info()
                if info:
                    output.append(f"✅ **AWS STS**: Connected")
                    output.append(f"   Account: {info.get('account_id', 'Unknown')}")
                    output.append(f"   Region: {info.get('region', 'Unknown')}")
                else:
                    output.append(f"❌ **AWS STS**: No profile info available")
            except Exception as e:
                output.append(f"❌ **AWS STS**: {str(e)}")
            
            # Test Cost Explorer
            try:
                ce_client = aws_provider.get_client("ce")
                ce_client.get_dimension_values(
                    TimePeriod={'Start': '2024-01-01', 'End': '2024-01-02'},
                    Dimension='SERVICE',
                    Context='COST_AND_USAGE',
                    MaxResults=1
                )
                output.append(f"✅ **Cost Explorer**: Available")
            except Exception as e:
                output.append(f"❌ **Cost Explorer**: {str(e)[:100]}")
            
            output.append(f"\n🚀 **Server Status**: Ready for AWS operations")
            output.append(f"💡 **Use**: `aws_profile_list()` to see available profiles")
            
            return "\n".join(output)
            
        except Exception as e:
            error_msg = f"❌ Server connectivity test failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_test_permissions() -> str:
        """Test AWS permissions for various services with current profile."""
        import asyncio
        
        logger.info("🔐 Testing AWS permissions...")
        
        try:
            async def test_permissions_with_timeout():
                current_profile = aws_provider.get_current_profile()
                
                output = ["🔐 **AWS PERMISSIONS TEST**", "=" * 40]
                output.append(f"📍 **Profile**: {current_profile or 'default'}")
                
                # Get basic profile info (fast version)
                try:
                    info = aws_provider.get_profile_info_fast()
                    if info:
                        output.append(f"🌍 **Region**: {info.get('region', 'Unknown')}")
                except Exception:
                    pass
                
                output.append(f"\n🔧 **Service Permissions**:")
                
                # Test STS (should always work)
                try:
                    sts_client = aws_provider.get_client("sts")
                    # Quick test - just get the client, don't make API call yet
                    output.append(f"   ✅ **STS**: Client available")
                except Exception as e:
                    output.append(f"   ❌ **STS**: {str(e)[:50]}")
                
                # Test Cost Explorer with timeout
                try:
                    ce_client = aws_provider.get_client("ce")
                    # Quick API test with short timeout
                    ce_client.get_dimension_values(
                        TimePeriod={'Start': '2024-01-01', 'End': '2024-01-02'},
                        Dimension='SERVICE',
                        Context='COST_AND_USAGE',
                        MaxResults=1
                    )
                    output.append(f"   ✅ **Cost Explorer**: Full access")
                except Exception as e:
                    if "AccessDenied" in str(e):
                        output.append(f"   ❌ **Cost Explorer**: Access denied")
                    elif "InvalidDimensionKey" in str(e):
                        output.append(f"   ✅ **Cost Explorer**: Basic access (API working)")
                    else:
                        output.append(f"   ⚠️ **Cost Explorer**: {str(e)[:50]}")
                
                # Test EC2 (quick test)
                try:
                    ec2_client = aws_provider.get_client("ec2")
                    ec2_client.describe_instances(MaxResults=1)
                    output.append(f"   ✅ **EC2**: Describe instances available")
                except Exception as e:
                    if "UnauthorizedOperation" in str(e):
                        output.append(f"   ❌ **EC2**: Unauthorized operation")
                    else:
                        output.append(f"   ⚠️ **EC2**: {str(e)[:50]}")
                
                # Test CloudWatch (quick test)
                try:
                    cw_client = aws_provider.get_client("cloudwatch")
                    cw_client.list_metrics(MaxRecords=1)
                    output.append(f"   ✅ **CloudWatch**: Metrics available")
                except Exception as e:
                    if "AccessDenied" in str(e):
                        output.append(f"   ❌ **CloudWatch**: Access denied")
                    else:
                        output.append(f"   ⚠️ **CloudWatch**: {str(e)[:50]}")
                
                # Test ECS (quick test)
                try:
                    ecs_client = aws_provider.get_client("ecs")
                    ecs_client.list_clusters(maxResults=1)
                    output.append(f"   ✅ **ECS**: List clusters available")
                except Exception as e:
                    if "AccessDenied" in str(e):
                        output.append(f"   ❌ **ECS**: Access denied")
                    else:
                        output.append(f"   ⚠️ **ECS**: {str(e)[:50]}")
                
                output.append(f"\n💡 **Next Steps**:")
                output.append(f"   • ✅ permissions = Service fully available")
                output.append(f"   • ❌ permissions = Need additional IAM policies") 
                output.append(f"   • Use `aws_profile_switch('profile')` to try different profile")
                output.append(f"   • Use `aws_profile_list()` to see available profiles")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (30 seconds for permission testing)
            result = await asyncio.wait_for(test_permissions_with_timeout(), timeout=30.0)
            logger.info(f"✅ Successfully completed permissions test")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS permissions test took longer than 30 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error testing permissions: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
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
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        top_n: int = 10
    ) -> str:
        """AWS Cost Explorer: Analyze costs by any dimension with detailed breakdown."""
        import asyncio
        
        logger.info(f"📊 Analyzing costs by dimension: {dimension}")
        
        try:
            async def analyze_dimension_with_timeout():
                logger.info(f"🔍 Connecting to AWS Cost Explorer...")
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS Cost Explorer")
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                logger.info(f"📅 Querying period: {start_date} to {end_date}")
                
                # Build group by clause (simplified - just the main dimension)
                group_by = [{'Type': 'DIMENSION', 'Key': dimension}]
                
                logger.info(f"🔄 Making API call for dimension analysis...")
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost', 'UnblendedCost'],
                    GroupBy=group_by
                )
                logger.info(f"✅ API call completed successfully")
                
                # Process results
                dimension_costs = {}
                total_cost = 0.0
                
                logger.info(f"🔄 Processing results...")
                for result in response.get('ResultsByTime', []):
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if keys:
                            key = keys[0]  # Simplified - just use the first key
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            if key not in dimension_costs:
                                dimension_costs[key] = 0.0
                            dimension_costs[key] += cost
                            total_cost += cost
                
                # Sort by cost
                sorted_costs = sorted(dimension_costs.items(), key=lambda x: x[1], reverse=True)
                logger.info(f"📊 Found {len(sorted_costs)} dimension values with total cost: ${total_cost:.2f}")
                
                output = [f"📊 **COST ANALYSIS BY {dimension.upper()}**", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
                output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
                output.append(f"🔍 **Dimension Values Found**: {len(sorted_costs)}")
                
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
            
            # Use timeout to prevent hanging (45 seconds for this complex operation)
            result = await asyncio.wait_for(analyze_dimension_with_timeout(), timeout=45.0)
            logger.info(f"✅ Successfully completed dimension analysis")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS dimension analysis for '{dimension}' took longer than 45 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error analyzing by dimension: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def aws_cost_explorer_analyze_by_service(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        top_n: int = 15
    ) -> str:
        """AWS Cost Explorer: Analyze costs by AWS service - simplified version for quick service breakdown."""
        import asyncio
        
        logger.info(f"🔧 Analyzing costs by AWS service for {days} days...")
        
        try:
            async def analyze_service_with_timeout():
                logger.info(f"🔍 Connecting to AWS Cost Explorer...")
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS Cost Explorer")
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                logger.info(f"📅 Querying period: {start_date} to {end_date}")
                
                logger.info(f"🔄 Making API call for service analysis...")
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost', 'UnblendedCost'],
                    GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
                )
                logger.info(f"✅ API call completed successfully")
                
                # Process results
                service_costs = {}
                total_cost = 0.0
                
                logger.info(f"🔄 Processing results...")
                for result in response.get('ResultsByTime', []):
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if keys:
                            service = keys[0]
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            if service not in service_costs:
                                service_costs[service] = 0.0
                            service_costs[service] += cost
                            total_cost += cost
                
                # Sort by cost
                sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
                logger.info(f"🔧 Found {len(sorted_services)} services with total cost: ${total_cost:.2f}")
                
                output = [f"🔧 **AWS SERVICE COST ANALYSIS**", "=" * 50]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
                output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
                output.append(f"🔧 **Services Found**: {len(sorted_services)}")
                
                output.append(f"\n🏆 **TOP {min(top_n, len(sorted_services))} SERVICES BY COST**:")
                
                for i, (service, cost) in enumerate(sorted_services[:top_n], 1):
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    daily_avg = cost / days
                    
                    # Simplify service names for better readability
                    service_name = service
                    if service.startswith('Amazon '):
                        service_name = service[7:]  # Remove 'Amazon ' prefix
                    elif service.startswith('AWS '):
                        service_name = service[4:]   # Remove 'AWS ' prefix
                    
                    output.append(f"{i:2d}. **{service_name}**")
                    output.append(f"     💰 ${cost:.2f} ({percentage:.1f}%)")
                    output.append(f"     📈 ${daily_avg:.2f}/day")
                
                if len(sorted_services) > top_n:
                    remaining_cost = sum(cost for _, cost in sorted_services[top_n:])
                    remaining_percentage = (remaining_cost / total_cost * 100) if total_cost > 0 else 0
                    output.append(f"\n📊 **Other Services**: ${remaining_cost:.2f} ({remaining_percentage:.1f}%)")
                
                # Add quick optimization tips
                top_service = sorted_services[0] if sorted_services else None
                if top_service:
                    service_name, service_cost = top_service
                    output.append(f"\n💡 **Quick Tips**:")
                    
                    if 'Elastic Compute Cloud' in service_name and service_cost > 50:
                        output.append("   • EC2: Consider Reserved Instances or Spot instances")
                    elif 'Simple Storage Service' in service_name and service_cost > 20:
                        output.append("   • S3: Review storage classes and lifecycle policies")
                    elif 'Relational Database Service' in service_name and service_cost > 30:
                        output.append("   • RDS: Consider Reserved Instances for steady workloads")
                    elif 'Lambda' in service_name:
                        output.append("   • Lambda: Monitor memory allocation and execution time")
                    
                    output.append("   • Use aws_cost_explorer_analyze_by_dimension('SERVICE') for detailed breakdown")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (30 seconds)
            result = await asyncio.wait_for(analyze_service_with_timeout(), timeout=30.0)
            logger.info(f"✅ Successfully completed service analysis")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS service analysis took longer than 30 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error analyzing by service: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    # TAG ANALYSIS TOOLS
    @mcp.tool()
    async def aws_cost_explorer_list_tag_keys(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        max_results: int = 100
    ) -> str:
        """AWS Cost Explorer: List all available tag keys for cost analysis."""
        import asyncio
        
        logger.info(f"🏷️ Listing AWS tag keys for {days} days...")
        
        try:
            async def list_tag_keys_with_timeout():
                logger.info(f"🔍 Connecting to AWS Cost Explorer...")
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS Cost Explorer")
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                logger.info(f"📅 Querying period: {start_date} to {end_date}")
                
                # Try different contexts to avoid API validation errors
                contexts_to_try = ['COST_AND_USAGE', 'RESERVATIONS', 'SAVINGS_PLANS']
                tag_keys = []
                total_count = 0
                successful_context = None
                
                for context in contexts_to_try:
                    try:
                        logger.info(f"🔄 Trying context: {context}")
                        response = ce_client.get_dimension_values(
                            TimePeriod={
                                'Start': start_date.strftime('%Y-%m-%d'),
                                'End': end_date.strftime('%Y-%m-%d')
                            },
                            Dimension='TAG_KEY',
                            Context=context,
                            MaxResults=max_results
                        )
                        
                        tag_keys = [item['Value'] for item in response.get('DimensionValues', [])]
                        total_count = response.get('TotalSize', 0)
                        successful_context = context
                        logger.info(f"✅ Successfully retrieved {len(tag_keys)} tag keys using context: {context}")
                        break
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Context {context} failed: {str(e)[:100]}")
                        continue
                
                if not tag_keys and not successful_context:
                    # If all contexts fail, try a simpler approach using cost and usage API
                    logger.info(f"🔄 Trying alternative approach via cost and usage query...")
                    try:
                        response = ce_client.get_cost_and_usage(
                            TimePeriod={
                                'Start': start_date.strftime('%Y-%m-%d'),
                                'End': end_date.strftime('%Y-%m-%d')
                            },
                            Granularity='DAILY',
                            Metrics=['BlendedCost'],
                            GroupBy=[{'Type': 'TAG', 'Key': '*'}]
                        )
                        
                        # Extract unique tag keys from the response
                        tag_keys_set = set()
                        for result in response.get('ResultsByTime', []):
                            for group in result.get('Groups', []):
                                keys = group.get('Keys', [])
                                if keys:
                                    # Tag keys are in format "tag_key$tag_value"
                                    for key in keys:
                                        if '$' in key:
                                            tag_key = key.split('$')[0]
                                            tag_keys_set.add(tag_key)
                        
                        tag_keys = sorted(list(tag_keys_set))
                        total_count = len(tag_keys)
                        successful_context = "COST_AND_USAGE_QUERY"
                        logger.info(f"✅ Alternative approach found {len(tag_keys)} tag keys")
                        
                    except Exception as e:
                        logger.error(f"❌ Alternative approach also failed: {str(e)}")
                        return f"❌ Unable to retrieve tag keys: All approaches failed. This might indicate no tagged resources in the time period or insufficient permissions."
                
                output = ["🏷️ **AVAILABLE TAG KEYS**", "=" * 40]
                output.append(f"📊 **Total Tag Keys**: {total_count}")
                output.append(f"📅 **Period**: {start_date} to {end_date}")
                output.append(f"🔧 **Context Used**: {successful_context}")
                
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
                    
                    output.append(f"\n🔧 **Usage**: Use `aws_cost_explorer_analyze_by_custom_tag('tag_key')` to analyze costs by any tag")
                else:
                    output.append("\n⚠️ No tag keys found in the specified time period")
                    output.append("💡 This could mean:")
                    output.append("   • No resources have tags in this time period")
                    output.append("   • Resources were created outside the specified date range")
                    output.append("   • Try increasing the 'days' parameter")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (30 seconds)
            result = await asyncio.wait_for(list_tag_keys_with_timeout(), timeout=30.0)
            logger.info(f"✅ Successfully completed tag keys listing")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: AWS tag keys listing took longer than 30 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error listing tag keys: {str(e)}"
            logger.error(error_msg)
            return error_msg

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