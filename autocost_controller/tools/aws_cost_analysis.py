"""Advanced AWS Cost Analysis tools for Autocost Controller."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP

from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger


def register_aws_cost_analysis_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register advanced AWS cost analysis tools."""
    
    aws_provider = provider_manager.get_provider("aws")
    if not aws_provider:
        return
    
    @mcp.tool()
    async def aws_cost_rolling_average_analysis(
        days: int = 28,
        service_filter: Optional[str] = None,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Cost Analysis: Calculate rolling averages and detect cost trend changes."""
        import asyncio
        
        logger.info(f"📊 Analyzing {days}-day rolling cost averages...")
        
        try:
            async def analyze_rolling_costs_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                # Get extended period for rolling average
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days*2)  # Get double period for comparison
                
                # Build filter
                filters = {}
                if service_filter:
                    filters['Dimensions'] = {
                        'Key': 'SERVICE',
                        'Values': [service_filter],
                        'MatchOptions': ['EQUALS']
                    }
                
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}] if not service_filter else [],
                    **({'Filter': filters} if filters else {})
                )
                
                # Process daily costs
                daily_costs = {}
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    total_cost = 0.0
                    
                    if service_filter:
                        total_cost = float(result.get('Total', {}).get('BlendedCost', {}).get('Amount', 0))
                    else:
                        for group in result.get('Groups', []):
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            total_cost += cost
                    
                    daily_costs[date] = total_cost
                
                # Calculate rolling averages
                sorted_dates = sorted(daily_costs.keys())
                rolling_averages = []
                weekly_costs = []
                
                for i in range(days, len(sorted_dates)):
                    current_date = sorted_dates[i]
                    window_costs = [daily_costs[sorted_dates[j]] for j in range(i-days+1, i+1)]
                    rolling_avg = sum(window_costs) / days
                    rolling_averages.append((current_date, rolling_avg))
                
                # Calculate weekly costs for comparison
                for i in range(0, len(sorted_dates), 7):
                    week_dates = sorted_dates[i:i+7]
                    if len(week_dates) == 7:
                        week_cost = sum(daily_costs[date] for date in week_dates)
                        weekly_costs.append((week_dates[0], week_cost))
                
                # Analyze trends
                recent_avg = rolling_averages[-1][1] if rolling_averages else 0
                previous_avg = rolling_averages[-8][1] if len(rolling_averages) >= 8 else 0
                trend_change = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
                
                output = [f"📊 **{days}-DAY ROLLING COST ANALYSIS**", "=" * 60]
                if service_filter:
                    output.append(f"🔧 **Service**: {service_filter}")
                output.append(f"📅 **Analysis Period**: {start_date} to {end_date}")
                output.append(f"💰 **Current {days}-Day Average**: ${recent_avg:.2f}/day")
                
                if previous_avg > 0:
                    trend_emoji = "📈" if trend_change > 0 else "📉" if trend_change < 0 else "➡️"
                    output.append(f"{trend_emoji} **Week-over-Week Change**: {trend_change:+.1f}%")
                    
                    if abs(trend_change) > 10:
                        output.append(f"⚠️ **ALERT**: Significant cost trend change detected!")
                
                # Show recent weekly costs
                output.append(f"\n📈 **RECENT WEEKLY COSTS**:")
                for week_start, week_cost in weekly_costs[-4:]:
                    week_end = (datetime.strptime(week_start, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d')
                    daily_avg = week_cost / 7
                    output.append(f"   {week_start} to {week_end}: ${week_cost:.2f} (${daily_avg:.2f}/day)")
                
                # Identify anomalies
                if len(weekly_costs) >= 4:
                    recent_weeks = [cost for _, cost in weekly_costs[-4:]]
                    avg_cost = sum(recent_weeks[:-1]) / 3
                    latest_cost = recent_weeks[-1]
                    anomaly_threshold = 0.15  # 15% threshold
                    
                    if latest_cost > avg_cost * (1 + anomaly_threshold):
                        impact = latest_cost - avg_cost
                        output.append(f"\n🚨 **COST ANOMALY DETECTED**:")
                        output.append(f"   Latest week: ${latest_cost:.2f}")
                        output.append(f"   3-week average: ${avg_cost:.2f}")
                        output.append(f"   Impact: +${impact:.2f} ({(impact/avg_cost*100):.1f}% increase)")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_rolling_costs_with_timeout(), timeout=45.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Rolling average analysis took longer than 45 seconds"
        except Exception as e:
            return f"❌ Error analyzing rolling averages: {str(e)}"
    
    @mcp.tool()
    async def aws_ecs_cost_deep_dive(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS ECS: Deep dive cost analysis including Fargate vs EC2, container insights impact."""
        import asyncio
        
        logger.info(f"🐳 Deep diving into ECS costs for {days} days...")
        
        try:
            async def analyze_ecs_costs_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get ECS costs broken down by usage type (focuses on ECS-specific costs only)
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost', 'UsageQuantity'],
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                    ],
                    Filter={
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Elastic Container Service'],
                            'MatchOptions': ['EQUALS']
                        }
                    }
                )
                
                # Get ECS costs by tenant/organization for proper attribution
                tenant_response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'TAG', 'Key': 'Organization'}
                    ],
                    Filter={
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Elastic Container Service'],
                            'MatchOptions': ['EQUALS']
                        }
                    }
                )
                
                # Process ECS cost breakdown by usage type
                fargate_costs = {}
                ec2_costs = {}
                container_insights_costs = 0.0
                total_ecs_cost = 0.0
                usage_type_breakdown = {}
                
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            usage_type = keys[0]
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            total_ecs_cost += cost
                            
                            # Track usage type breakdown
                            if usage_type not in usage_type_breakdown:
                                usage_type_breakdown[usage_type] = 0.0
                            usage_type_breakdown[usage_type] += cost
                            
                            # Categorize costs by ECS type
                            if 'Fargate' in usage_type:
                                if date not in fargate_costs:
                                    fargate_costs[date] = 0.0
                                fargate_costs[date] += cost
                            elif 'EC2' in usage_type or 'Instance' in usage_type:
                                if date not in ec2_costs:
                                    ec2_costs[date] = 0.0
                                ec2_costs[date] += cost
                            elif 'ContainerInsights' in usage_type:
                                container_insights_costs += cost
                
                # Process ECS tenant attribution
                tenant_costs = {}
                for result in tenant_response.get('ResultsByTime', []):
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            tenant = keys[0] if keys[0] != 'No tag' else 'Untagged'
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            if tenant not in tenant_costs:
                                tenant_costs[tenant] = 0.0
                            tenant_costs[tenant] += cost
                
                # Calculate daily averages
                fargate_daily_avg = sum(fargate_costs.values()) / days if fargate_costs else 0
                ec2_daily_avg = sum(ec2_costs.values()) / days if ec2_costs else 0
                insights_daily_avg = container_insights_costs / days
                
                output = ["🐳 **ECS COST DEEP DIVE**", "=" * 50]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total ECS Cost**: ${total_ecs_cost:.2f}")
                output.append(f"📈 **Daily Average**: ${total_ecs_cost/days:.2f}")
                
                output.append(f"\n🔧 **ECS USAGE TYPE BREAKDOWN**:")
                sorted_usage_types = sorted(usage_type_breakdown.items(), key=lambda x: x[1], reverse=True)
                for usage_type, cost in sorted_usage_types[:10]:
                    percentage = (cost / total_ecs_cost * 100) if total_ecs_cost > 0 else 0
                    daily_avg = cost / days
                    # Clean up usage type names for readability
                    clean_name = usage_type.replace('ECS-Fargate-', '').replace('ECS-EC2-', '').replace('USW2-', '')
                    output.append(f"   • **{clean_name}**: ${cost:.2f} ({percentage:.1f}%) - ${daily_avg:.2f}/day")
                
                output.append(f"\n🚀 **COMPUTE TYPE BREAKDOWN**:")
                output.append(f"   🚀 **Fargate**: ${sum(fargate_costs.values()):.2f} (${fargate_daily_avg:.2f}/day)")
                output.append(f"   🖥️ **EC2**: ${sum(ec2_costs.values()):.2f} (${ec2_daily_avg:.2f}/day)")
                output.append(f"   📊 **Container Insights**: ${container_insights_costs:.2f} (${insights_daily_avg:.2f}/day)")
                
                # Calculate ratios
                total_compute = sum(fargate_costs.values()) + sum(ec2_costs.values())
                if total_compute > 0:
                    fargate_ratio = sum(fargate_costs.values()) / total_compute * 100
                    ec2_ratio = sum(ec2_costs.values()) / total_compute * 100
                    
                    output.append(f"\n📊 **COMPUTE SPLIT**:")
                    output.append(f"   🚀 Fargate: {fargate_ratio:.1f}%")
                    output.append(f"   🖥️ EC2: {ec2_ratio:.1f}%")
                
                # Show ECS tenant attribution
                if tenant_costs:
                    sorted_tenants = sorted(tenant_costs.items(), key=lambda x: x[1], reverse=True)
                    output.append(f"\n🏢 **ECS COSTS BY ORGANIZATION** (Top 10):")
                    for i, (tenant, cost) in enumerate(sorted_tenants[:10], 1):
                        percentage = (cost / total_ecs_cost * 100) if total_ecs_cost > 0 else 0
                        daily_avg = cost / days
                        output.append(f"{i:2d}. **{tenant}**: ${cost:.2f} ({percentage:.1f}%) - ${daily_avg:.2f}/day")
                
                # Analyze Container Insights impact
                if insights_daily_avg > 50:  # If significant Container Insights cost
                    output.append(f"\n📊 **CONTAINER INSIGHTS IMPACT**:")
                    output.append(f"   💰 Current cost: ${insights_daily_avg:.2f}/day")
                    output.append(f"   📅 Monthly projection: ${insights_daily_avg * 30:.2f}")
                    output.append(f"   💡 Consider: Selective monitoring for cost optimization")
                
                # Optimization recommendations
                output.append(f"\n💡 **OPTIMIZATION OPPORTUNITIES**:")
                
                if fargate_daily_avg > 100:
                    graviton_savings = fargate_daily_avg * 0.2
                    output.append(f"   🔄 **Graviton Fargate**: ${graviton_savings:.2f}/day savings (20%)")
                
                if ec2_daily_avg > 50:
                    spot_potential = ec2_daily_avg * 0.7
                    output.append(f"   💡 **Spot Instances**: Up to ${spot_potential:.2f}/day savings (70%)")
                
                if total_compute > 500:
                    rightsizing_savings = total_compute * 0.15 / days
                    output.append(f"   📏 **Right-sizing**: ~${rightsizing_savings:.2f}/day potential (15%)")
                
                untagged_cost = tenant_costs.get('Untagged', 0)
                if untagged_cost > total_ecs_cost * 0.1:
                    output.append(f"   🏷️ **Tagging**: ${untagged_cost:.2f} untagged ECS costs need organization tags")
                
                # Show daily cost trend
                if len(fargate_costs) >= 7:
                    output.append(f"\n📈 **DAILY ECS COST TREND**:")
                    all_daily_costs = {}
                    for date in fargate_costs:
                        all_daily_costs[date] = fargate_costs.get(date, 0) + ec2_costs.get(date, 0)
                    
                    sorted_dates = sorted(all_daily_costs.keys())[-7:]
                    for date in sorted_dates:
                        total_day_cost = all_daily_costs.get(date, 0)
                        output.append(f"   {date}: ${total_day_cost:.2f}")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_ecs_costs_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: ECS deep dive analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing ECS costs: {str(e)}"
    
    @mcp.tool()
    async def aws_spot_instance_cost_impact(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Spot Analysis: Analyze spot instance usage, interruptions, and cost impact."""
        import asyncio
        
        logger.info(f"💡 Analyzing spot instance cost impact for {days} days...")
        
        try:
            async def analyze_spot_impact_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get EC2 costs by purchase option
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost', 'UsageQuantity'],
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'PURCHASE_TYPE'},
                        {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}
                    ],
                    Filter={
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Elastic Compute Cloud - Compute'],
                            'MatchOptions': ['EQUALS']
                        }
                    }
                )
                
                # Process spot vs on-demand costs
                spot_costs = {}
                on_demand_costs = {}
                reserved_costs = {}
                
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 2:
                            purchase_type = keys[0]
                            instance_type = keys[1]
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            if 'Spot' in purchase_type:
                                if date not in spot_costs:
                                    spot_costs[date] = 0.0
                                spot_costs[date] += cost
                            elif 'On Demand' in purchase_type:
                                if date not in on_demand_costs:
                                    on_demand_costs[date] = 0.0
                                on_demand_costs[date] += cost
                            elif 'Reserved' in purchase_type:
                                if date not in reserved_costs:
                                    reserved_costs[date] = 0.0
                                reserved_costs[date] += cost
                
                # Calculate totals and averages
                total_spot = sum(spot_costs.values())
                total_on_demand = sum(on_demand_costs.values())
                total_reserved = sum(reserved_costs.values())
                total_ec2 = total_spot + total_on_demand + total_reserved
                
                spot_daily_avg = total_spot / days if days > 0 else 0
                on_demand_daily_avg = total_on_demand / days if days > 0 else 0
                
                output = ["💡 **SPOT INSTANCE COST IMPACT ANALYSIS**", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total EC2 Cost**: ${total_ec2:.2f}")
                
                output.append(f"\n🔧 **PURCHASE TYPE BREAKDOWN**:")
                if total_ec2 > 0:
                    spot_percentage = (total_spot / total_ec2) * 100
                    on_demand_percentage = (total_on_demand / total_ec2) * 100
                    reserved_percentage = (total_reserved / total_ec2) * 100
                    
                    output.append(f"   💡 **Spot**: ${total_spot:.2f} ({spot_percentage:.1f}%) - ${spot_daily_avg:.2f}/day")
                    output.append(f"   🔶 **On-Demand**: ${total_on_demand:.2f} ({on_demand_percentage:.1f}%) - ${on_demand_daily_avg:.2f}/day")
                    output.append(f"   📅 **Reserved**: ${total_reserved:.2f} ({reserved_percentage:.1f}%)")
                
                # Calculate potential savings if more spot was used
                if total_on_demand > 0:
                    potential_spot_savings = total_on_demand * 0.7  # 70% typical spot savings
                    output.append(f"\n💰 **SPOT OPTIMIZATION POTENTIAL**:")
                    output.append(f"   🎯 Current On-Demand: ${total_on_demand:.2f}")
                    output.append(f"   💡 If 70% moved to Spot: ${potential_spot_savings:.2f} savings")
                    output.append(f"   📈 Monthly impact: ${potential_spot_savings * 30 / days:.2f}")
                
                # Analyze spot cost volatility
                if len(spot_costs) >= 7:
                    spot_values = list(spot_costs.values())
                    spot_avg = sum(spot_values) / len(spot_values)
                    spot_max = max(spot_values)
                    spot_min = min(spot_values)
                    volatility = ((spot_max - spot_min) / spot_avg * 100) if spot_avg > 0 else 0
                    
                    output.append(f"\n📊 **SPOT COST VOLATILITY**:")
                    output.append(f"   📈 Daily average: ${spot_avg:.2f}")
                    output.append(f"   📊 Range: ${spot_min:.2f} - ${spot_max:.2f}")
                    output.append(f"   🌊 Volatility: {volatility:.1f}%")
                    
                    if volatility > 50:
                        output.append(f"   ⚠️ **HIGH VOLATILITY**: Possible capacity issues")
                        output.append(f"   💡 Consider: Multi-AZ strategy, instance type diversification")
                
                # Show daily spot costs
                output.append(f"\n📈 **DAILY SPOT COSTS**:")
                sorted_dates = sorted(spot_costs.keys())[-7:]
                for date in sorted_dates:
                    spot_cost = spot_costs.get(date, 0)
                    on_demand_cost = on_demand_costs.get(date, 0)
                    total_day = spot_cost + on_demand_cost
                    spot_ratio = (spot_cost / total_day * 100) if total_day > 0 else 0
                    output.append(f"   {date}: ${spot_cost:.2f} ({spot_ratio:.1f}% spot)")
                
                # Recommendations
                output.append(f"\n💡 **RECOMMENDATIONS**:")
                if spot_percentage < 30 and total_on_demand > 100:
                    output.append(f"   🎯 Increase spot usage: Current {spot_percentage:.1f}%, target 50%+")
                
                if volatility > 30:
                    output.append(f"   🔄 Diversify instance types to reduce interruption impact")
                    output.append(f"   📍 Consider multi-AZ spot deployment")
                
                output.append(f"   🔧 Implement spot interruption handling")
                output.append(f"   📊 Monitor capacity trends for proactive scaling")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_spot_impact_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Spot instance analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing spot instance costs: {str(e)}"
    
    @mcp.tool()
    async def aws_savings_plan_utilization_analysis(
        days: int = 30,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Savings Plans: Analyze utilization, coverage, and impact on costs."""
        import asyncio
        
        logger.info(f"📅 Analyzing Savings Plans utilization for {days} days...")
        
        try:
            async def analyze_savings_plans_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get Savings Plans utilization
                try:
                    utilization_response = ce_client.get_savings_plans_utilization(
                        TimePeriod={
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        Granularity='DAILY'
                    )
                except Exception as e:
                    if "AccessDenied" in str(e):
                        return "❌ Insufficient permissions for Savings Plans analysis. Need: ce:GetSavingsPlansUtilization"
                    raise e
                
                # Get Savings Plans coverage
                coverage_response = ce_client.get_savings_plans_coverage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY'
                )
                
                # Process utilization data
                utilization_data = []
                total_commitment = 0.0
                total_used = 0.0
                
                for result in utilization_response.get('SavingsPlansUtilizationsByTime', []):
                    date = result['TimePeriod']['Start']
                    util = result['Utilization']
                    
                    utilized_commitment = float(util.get('UtilizedCommitment', {}).get('Amount', 0))
                    unused_commitment = float(util.get('UnusedCommitment', {}).get('Amount', 0))
                    total_commitment_day = utilized_commitment + unused_commitment
                    
                    utilization_pct = float(util.get('UtilizationPercentage', 0))
                    
                    utilization_data.append({
                        'date': date,
                        'utilized': utilized_commitment,
                        'unused': unused_commitment,
                        'total': total_commitment_day,
                        'utilization_pct': utilization_pct
                    })
                    
                    total_commitment += total_commitment_day
                    total_used += utilized_commitment
                
                # Process coverage data
                coverage_data = []
                for result in coverage_response.get('SavingsPlansCoverages', []):
                    date = result['TimePeriod']['Start']
                    coverage = result['Coverage']
                    
                    coverage_pct = float(coverage.get('CoveragePercentage', 0))
                    on_demand_cost = float(coverage.get('OnDemandCost', {}).get('Amount', 0))
                    coverage_cost = float(coverage.get('CoverageCost', {}).get('Amount', 0))
                    
                    coverage_data.append({
                        'date': date,
                        'coverage_pct': coverage_pct,
                        'on_demand_cost': on_demand_cost,
                        'coverage_cost': coverage_cost
                    })
                
                # Calculate averages
                avg_utilization = (total_used / total_commitment * 100) if total_commitment > 0 else 0
                avg_coverage = sum(item['coverage_pct'] for item in coverage_data) / len(coverage_data) if coverage_data else 0
                
                output = ["📅 **SAVINGS PLANS UTILIZATION ANALYSIS**", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total Commitment**: ${total_commitment:.2f}")
                output.append(f"✅ **Total Utilized**: ${total_used:.2f}")
                output.append(f"📊 **Average Utilization**: {avg_utilization:.1f}%")
                output.append(f"🎯 **Average Coverage**: {avg_coverage:.1f}%")
                
                # Utilization health check
                if avg_utilization >= 95:
                    output.append(f"✅ **Utilization Status**: Excellent (≥95%)")
                elif avg_utilization >= 90:
                    output.append(f"🟡 **Utilization Status**: Good (90-95%)")
                elif avg_utilization >= 80:
                    output.append(f"🟠 **Utilization Status**: Fair (80-90%)")
                else:
                    output.append(f"🔴 **Utilization Status**: Poor (<80%)")
                
                # Calculate waste
                total_unused = total_commitment - total_used
                daily_waste = total_unused / days
                
                if total_unused > 0:
                    output.append(f"\n💸 **UNUSED COMMITMENT**:")
                    output.append(f"   Total unused: ${total_unused:.2f}")
                    output.append(f"   Daily average: ${daily_waste:.2f}")
                    output.append(f"   Monthly projection: ${daily_waste * 30:.2f}")
                
                # Show recent utilization trend
                if len(utilization_data) >= 7:
                    output.append(f"\n📈 **RECENT UTILIZATION TREND**:")
                    recent_data = utilization_data[-7:]
                    for item in recent_data:
                        output.append(f"   {item['date']}: {item['utilization_pct']:.1f}% (${item['unused']:.2f} unused)")
                
                # Identify patterns
                if len(utilization_data) >= 14:
                    recent_avg = sum(item['utilization_pct'] for item in utilization_data[-7:]) / 7
                    previous_avg = sum(item['utilization_pct'] for item in utilization_data[-14:-7]) / 7
                    trend = recent_avg - previous_avg
                    
                    output.append(f"\n📊 **UTILIZATION TREND**:")
                    trend_emoji = "📈" if trend > 0 else "📉" if trend < 0 else "➡️"
                    output.append(f"   {trend_emoji} Recent vs Previous week: {trend:+.1f}%")
                    
                    if trend < -5:
                        output.append(f"   ⚠️ **ALERT**: Utilization declining, investigate capacity changes")
                
                # Recommendations
                output.append(f"\n💡 **RECOMMENDATIONS**:")
                
                if avg_utilization < 85:
                    output.append(f"   🎯 Target >90% utilization for optimal savings")
                    output.append(f"   🔍 Review workload patterns and right-size commitment")
                
                if avg_coverage < 70:
                    output.append(f"   📊 Coverage low ({avg_coverage:.1f}%), consider additional Savings Plans")
                
                if daily_waste > 50:
                    output.append(f"   💸 High daily waste (${daily_waste:.2f}), review commitment size")
                
                output.append(f"   📅 Monitor utilization weekly for optimal management")
                output.append(f"   🔄 Consider Compute Savings Plans for flexibility")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_savings_plans_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Savings Plans analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing Savings Plans: {str(e)}"
    
    @mcp.tool()
    async def aws_tenant_cost_analysis(
        tag_key: str = "Organization",
        days: int = 7,
        top_n: int = 20,
        cost_threshold: float = 100.0,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Tenant Analysis: Track costs by tenant/environment tags, identify top spenders and anomalies."""
        import asyncio
        
        logger.info(f"🏢 Analyzing tenant costs by {tag_key} for {days} days...")
        
        try:
            async def analyze_tenant_costs_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get costs by tenant tag (primary grouping)
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'TAG', 'Key': tag_key}
                    ]
                )
                
                # Process tenant costs
                tenant_costs = {}
                daily_tenant_costs = {}
                
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            tenant = keys[0] if keys[0] != 'No tag' else 'Untagged'
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            # Total tenant costs
                            if tenant not in tenant_costs:
                                tenant_costs[tenant] = 0.0
                                daily_tenant_costs[tenant] = {}
                            
                            tenant_costs[tenant] += cost
                            
                            # Daily costs per tenant
                            if date not in daily_tenant_costs[tenant]:
                                daily_tenant_costs[tenant][date] = 0.0
                            daily_tenant_costs[tenant][date] += cost
                
                # Get service breakdown for top tenants
                top_tenants = sorted(tenant_costs.items(), key=lambda x: x[1], reverse=True)[:5]
                tenant_services = {}
                
                if top_tenants:
                    # Get service breakdown for top tenants
                    for tenant, _ in top_tenants:
                        if tenant != 'Untagged':
                            try:
                                service_response = ce_client.get_cost_and_usage(
                                    TimePeriod={
                                        'Start': start_date.strftime('%Y-%m-%d'),
                                        'End': end_date.strftime('%Y-%m-%d')
                                    },
                                    Granularity='DAILY',
                                    Metrics=['BlendedCost'],
                                    GroupBy=[
                                        {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                                    ],
                                    Filter={
                                        'Tags': {
                                            'Key': tag_key,
                                            'Values': [tenant],
                                            'MatchOptions': ['EQUALS']
                                        }
                                    }
                                )
                                
                                tenant_services[tenant] = {}
                                for svc_result in service_response.get('ResultsByTime', []):
                                    for svc_group in svc_result.get('Groups', []):
                                        svc_keys = svc_group.get('Keys', [])
                                        if len(svc_keys) >= 1:
                                            service = svc_keys[0]
                                            svc_cost = float(svc_group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                                            
                                            if service not in tenant_services[tenant]:
                                                tenant_services[tenant][service] = 0.0
                                            tenant_services[tenant][service] += svc_cost
                            except Exception as e:
                                logger.warning(f"Could not get service breakdown for {tenant}: {e}")
                                tenant_services[tenant] = {}
                
                # Sort tenants by cost
                sorted_tenants = sorted(tenant_costs.items(), key=lambda x: x[1], reverse=True)
                total_cost = sum(tenant_costs.values())
                
                output = [f"🏢 **TENANT COST ANALYSIS** ({tag_key})", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
                output.append(f"🏢 **Total Tenants**: {len(sorted_tenants)}")
                
                # Show top tenants
                output.append(f"\n🏆 **TOP {min(top_n, len(sorted_tenants))} TENANTS BY COST**:")
                
                for i, (tenant, cost) in enumerate(sorted_tenants[:top_n], 1):
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    daily_avg = cost / days
                    monthly_projection = daily_avg * 30
                    
                    # Highlight expensive tenants
                    cost_emoji = "🔴" if cost > cost_threshold * 5 else "🟠" if cost > cost_threshold else "🟢"
                    
                    output.append(f"\n{i:2d}. {cost_emoji} **{tenant}**")
                    output.append(f"     💰 ${cost:.2f} ({percentage:.1f}%)")
                    output.append(f"     📈 ${daily_avg:.2f}/day, ${monthly_projection:.2f}/month")
                    
                    # Show top services for this tenant if available
                    if tenant in tenant_services and tenant_services[tenant]:
                        services = sorted(tenant_services[tenant].items(), key=lambda x: x[1], reverse=True)[:3]
                        service_summary = []
                        for svc, svc_cost in services:
                            svc_name = svc.replace('Amazon ', '').replace('AWS ', '')[:15]
                            service_summary.append(f"{svc_name} ${svc_cost:.0f}")
                        if service_summary:
                            output.append(f"     🔧 Top: {', '.join(service_summary)}")
                
                # Identify cost anomalies
                anomalous_tenants = []
                for tenant, cost in sorted_tenants:
                    daily_avg = cost / days
                    if daily_avg > cost_threshold:
                        # Check if this is unusually high
                        tenant_daily_costs_list = list(daily_tenant_costs[tenant].values())
                        if len(tenant_daily_costs_list) >= 3:
                            recent_avg = sum(tenant_daily_costs_list[-3:]) / 3
                            if len(tenant_daily_costs_list) >= 6:
                                historical_avg = sum(tenant_daily_costs_list[:-3]) / (len(tenant_daily_costs_list) - 3)
                                if recent_avg > historical_avg * 1.5:  # 50% increase
                                    anomalous_tenants.append((tenant, recent_avg, historical_avg))
                
                if anomalous_tenants:
                    output.append(f"\n🚨 **COST ANOMALIES DETECTED**:")
                    for tenant, recent, historical in anomalous_tenants[:5]:
                        increase = ((recent - historical) / historical * 100)
                        output.append(f"   ⚠️ **{tenant}**: {increase:+.1f}% increase")
                        output.append(f"      Recent: ${recent:.2f}/day vs Historical: ${historical:.2f}/day")
                
                # Show tenants above threshold
                expensive_tenants = [(t, c) for t, c in sorted_tenants if c > cost_threshold]
                if expensive_tenants:
                    output.append(f"\n💸 **TENANTS ABOVE ${cost_threshold:.0f} THRESHOLD**:")
                    for tenant, cost in expensive_tenants[:10]:
                        daily_cost = cost / days
                        output.append(f"   • {tenant}: ${cost:.2f} (${daily_cost:.2f}/day)")
                
                # UAT/Test environment analysis
                uat_tenants = [(t, c) for t, c in sorted_tenants if any(env in t.upper() for env in ['UAT', 'TEST', 'DEV', 'STAGING'])]
                if uat_tenants:
                    total_uat_cost = sum(c for _, c in uat_tenants)
                    output.append(f"\n🧪 **UAT/TEST ENVIRONMENTS**:")
                    output.append(f"   Total UAT cost: ${total_uat_cost:.2f} ({total_uat_cost/total_cost*100:.1f}%)")
                    
                    expensive_uat = [(t, c) for t, c in uat_tenants if c > cost_threshold/2]
                    if expensive_uat:
                        output.append(f"   Expensive UAT tenants:")
                        for tenant, cost in expensive_uat[:5]:
                            output.append(f"     • {tenant}: ${cost:.2f}")
                
                # Organization-specific patterns (your company's patterns)
                problem_patterns = ['H11', 'A28', 'U14', 'D32', 'E17']
                pattern_tenants = []
                for pattern in problem_patterns:
                    matching = [(t, c) for t, c in sorted_tenants if pattern in t.upper()]
                    if matching:
                        pattern_tenants.extend(matching)
                
                if pattern_tenants:
                    output.append(f"\n🎯 **KNOWN PROBLEM PATTERNS**:")
                    for tenant, cost in pattern_tenants[:10]:
                        daily_cost = cost / days
                        output.append(f"   • {tenant}: ${cost:.2f} (${daily_cost:.2f}/day)")
                
                # Optimization recommendations
                output.append(f"\n💡 **OPTIMIZATION RECOMMENDATIONS**:")
                
                if len(expensive_tenants) > 0:
                    output.append(f"   🎯 Review top {len(expensive_tenants)} tenants above ${cost_threshold:.0f} threshold")
                
                if anomalous_tenants:
                    output.append(f"   🚨 Investigate {len(anomalous_tenants)} tenants with cost anomalies")
                
                if uat_tenants and total_uat_cost > total_cost * 0.1:
                    output.append(f"   🧪 UAT costs are {total_uat_cost/total_cost*100:.1f}% of total - review necessity")
                
                untagged_cost = tenant_costs.get('Untagged', 0)
                if untagged_cost > total_cost * 0.05:
                    output.append(f"   🏷️ ${untagged_cost:.2f} untagged - improve tagging strategy")
                
                output.append(f"   📊 Set up alerts for tenants exceeding ${cost_threshold:.0f}/week")
                output.append(f"   🔄 Regular tenant cost reviews with business owners")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_tenant_costs_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Tenant cost analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing tenant costs: {str(e)}"
    
    @mcp.tool()
    async def aws_redshift_cost_analysis(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Redshift: Analyze Redshift costs, identify expensive clusters and usage patterns."""
        import asyncio
        
        logger.info(f"🗄️ Analyzing Redshift costs for {days} days...")
        
        try:
            async def analyze_redshift_costs_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get Redshift costs broken down by usage type
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost', 'UsageQuantity'],
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'},
                        {'Type': 'DIMENSION', 'Key': 'RESOURCE_ID'}
                    ],
                    Filter={
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Redshift'],
                            'MatchOptions': ['EQUALS']
                        }
                    }
                )
                
                # Process Redshift costs
                daily_costs = {}
                cluster_costs = {}
                usage_type_costs = {}
                total_cost = 0.0
                
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    daily_cost = 0.0
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 2:
                            usage_type = keys[0]
                            resource_id = keys[1]
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            daily_cost += cost
                            total_cost += cost
                            
                            # Track cluster costs
                            if resource_id not in cluster_costs:
                                cluster_costs[resource_id] = 0.0
                            cluster_costs[resource_id] += cost
                            
                            # Track usage type costs
                            if usage_type not in usage_type_costs:
                                usage_type_costs[usage_type] = 0.0
                            usage_type_costs[usage_type] += cost
                    
                    daily_costs[date] = daily_cost
                
                # Calculate daily average and trend
                daily_avg = total_cost / days if days > 0 else 0
                
                # Check for cost trend
                recent_days = sorted(daily_costs.keys())[-7:] if len(daily_costs) >= 7 else sorted(daily_costs.keys())
                older_days = sorted(daily_costs.keys())[:-7] if len(daily_costs) >= 14 else []
                
                trend = 0.0
                if older_days and recent_days:
                    recent_avg = sum(daily_costs[d] for d in recent_days) / len(recent_days)
                    older_avg = sum(daily_costs[d] for d in older_days) / len(older_days)
                    trend = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
                
                output = ["🗄️ **REDSHIFT COST ANALYSIS**", "=" * 50]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total Cost**: ${total_cost:.2f}")
                output.append(f"📈 **Daily Average**: ${daily_avg:.2f}")
                output.append(f"📊 **Monthly Projection**: ${daily_avg * 30:.2f}")
                
                if trend != 0:
                    trend_emoji = "📈" if trend > 0 else "📉"
                    output.append(f"{trend_emoji} **Cost Trend**: {trend:+.1f}% vs previous period")
                    
                    if abs(trend) > 20:
                        output.append(f"⚠️ **ALERT**: Significant cost change detected!")
                
                # Show cluster breakdown
                sorted_clusters = sorted(cluster_costs.items(), key=lambda x: x[1], reverse=True)
                if sorted_clusters:
                    output.append(f"\n🗄️ **CLUSTER COST BREAKDOWN**:")
                    for i, (cluster, cost) in enumerate(sorted_clusters[:10], 1):
                        percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                        daily_cluster_cost = cost / days
                        
                        # Highlight expensive clusters
                        cluster_emoji = "🔴" if cost > total_cost * 0.3 else "🟠" if cost > total_cost * 0.1 else "🟢"
                        
                        output.append(f"{i:2d}. {cluster_emoji} **{cluster}**")
                        output.append(f"     💰 ${cost:.2f} ({percentage:.1f}%)")
                        output.append(f"     📈 ${daily_cluster_cost:.2f}/day")
                
                # Show usage type breakdown
                sorted_usage_types = sorted(usage_type_costs.items(), key=lambda x: x[1], reverse=True)
                if sorted_usage_types:
                    output.append(f"\n🔧 **USAGE TYPE BREAKDOWN**:")
                    for usage_type, cost in sorted_usage_types[:5]:
                        percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                        # Simplify usage type names
                        simple_name = usage_type.replace('RedshiftNode:', '').replace('USW2-', '')
                        output.append(f"   • **{simple_name}**: ${cost:.2f} ({percentage:.1f}%)")
                
                # Show daily cost trend
                if len(daily_costs) >= 7:
                    output.append(f"\n📈 **DAILY COST TREND**:")
                    recent_dates = sorted(daily_costs.keys())[-7:]
                    for date in recent_dates:
                        cost = daily_costs[date]
                        output.append(f"   {date}: ${cost:.2f}")
                
                # Cost anomaly detection
                if len(daily_costs) >= 7:
                    daily_values = list(daily_costs.values())
                    avg_cost = sum(daily_values) / len(daily_values)
                    max_cost = max(daily_values)
                    
                    if max_cost > avg_cost * 1.5:  # 50% above average
                        max_date = [date for date, cost in daily_costs.items() if cost == max_cost][0]
                        output.append(f"\n🚨 **COST ANOMALY DETECTED**:")
                        output.append(f"   📅 Date: {max_date}")
                        output.append(f"   💰 Cost: ${max_cost:.2f} ({(max_cost/avg_cost-1)*100:+.1f}% vs average)")
                        output.append(f"   💡 Investigate: Schema changes, data refreshes, query patterns")
                
                # Optimization recommendations
                output.append(f"\n💡 **OPTIMIZATION RECOMMENDATIONS**:")
                
                if daily_avg > 100:
                    output.append(f"   🎯 Review query performance and optimization")
                    output.append(f"   📊 Analyze table statistics and distribution keys")
                    output.append(f"   🔄 Consider workload management (WLM) tuning")
                
                if len(sorted_clusters) > 1:
                    expensive_clusters = [c for c, cost in sorted_clusters if cost > total_cost * 0.2]
                    if expensive_clusters:
                        output.append(f"   🗄️ Focus on top clusters: {', '.join(expensive_clusters[:3])}")
                
                if trend > 20:
                    output.append(f"   📈 Cost increasing {trend:.1f}% - investigate workload changes")
                    output.append(f"   🔍 Check for: new data loads, schema changes, query patterns")
                
                if 'dc2' in str(usage_type_costs).lower():
                    output.append(f"   🔄 Consider migrating DC2 to RA3 nodes for better performance/cost")
                
                output.append(f"   📅 Implement query monitoring and alerting")
                output.append(f"   💾 Review data retention and archiving policies")
                output.append(f"   🕒 Consider pause/resume for non-production clusters")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_redshift_costs_with_timeout(), timeout=45.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Redshift cost analysis took longer than 45 seconds"
        except Exception as e:
            return f"❌ Error analyzing Redshift costs: {str(e)}"
    
    @mcp.tool()
    async def aws_service_tenant_cost_analysis(
        service_name: str,
        tag_key: str = "Organization", 
        days: int = 7,
        top_n: int = 15,
        cost_threshold: float = 50.0,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """AWS Service-Specific Tenant Analysis: Analyze costs by tenant/organization for a specific AWS service."""
        import asyncio
        
        logger.info(f"🏢 Analyzing {service_name} costs by {tag_key} for {days} days...")
        
        try:
            async def analyze_service_tenant_costs_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get costs by tenant tag for the specific service
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'TAG', 'Key': tag_key}
                    ],
                    Filter={
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': [service_name],
                            'MatchOptions': ['EQUALS']
                        }
                    }
                )
                
                # Process tenant costs for this service
                tenant_costs = {}
                daily_tenant_costs = {}
                
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            tenant = keys[0] if keys[0] != 'No tag' else 'Untagged'
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            # Total tenant costs
                            if tenant not in tenant_costs:
                                tenant_costs[tenant] = 0.0
                                daily_tenant_costs[tenant] = {}
                            
                            tenant_costs[tenant] += cost
                            
                            # Daily costs per tenant
                            if date not in daily_tenant_costs[tenant]:
                                daily_tenant_costs[tenant][date] = 0.0
                            daily_tenant_costs[tenant][date] += cost
                
                # Sort tenants by cost
                sorted_tenants = sorted(tenant_costs.items(), key=lambda x: x[1], reverse=True)
                total_cost = sum(tenant_costs.values())
                
                output = [f"🏢 **{service_name.upper()} COSTS BY {tag_key.upper()}**", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total {service_name} Cost**: ${total_cost:.2f}")
                output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
                output.append(f"🏢 **Total Tenants**: {len(sorted_tenants)}")
                
                # Show top tenants
                output.append(f"\n🏆 **TOP {min(top_n, len(sorted_tenants))} TENANTS BY COST**:")
                
                for i, (tenant, cost) in enumerate(sorted_tenants[:top_n], 1):
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    daily_avg = cost / days
                    monthly_projection = daily_avg * 30
                    
                    # Highlight expensive tenants
                    cost_emoji = "🔴" if cost > cost_threshold * 4 else "🟠" if cost > cost_threshold else "🟢"
                    
                    output.append(f"\n{i:2d}. {cost_emoji} **{tenant}**")
                    output.append(f"     💰 ${cost:.2f} ({percentage:.1f}%)")
                    output.append(f"     📈 ${daily_avg:.2f}/day, ${monthly_projection:.2f}/month")
                
                # Identify cost anomalies for this service
                anomalous_tenants = []
                for tenant, cost in sorted_tenants:
                    daily_avg = cost / days
                    if daily_avg > cost_threshold/2:  # Lower threshold for service-specific analysis
                        # Check if this is unusually high
                        tenant_daily_costs_list = list(daily_tenant_costs[tenant].values())
                        if len(tenant_daily_costs_list) >= 3:
                            recent_avg = sum(tenant_daily_costs_list[-3:]) / 3
                            if len(tenant_daily_costs_list) >= 6:
                                historical_avg = sum(tenant_daily_costs_list[:-3]) / (len(tenant_daily_costs_list) - 3)
                                if recent_avg > historical_avg * 1.3:  # 30% increase for service-specific
                                    anomalous_tenants.append((tenant, recent_avg, historical_avg))
                
                if anomalous_tenants:
                    output.append(f"\n🚨 **{service_name.upper()} COST ANOMALIES**:")
                    for tenant, recent, historical in anomalous_tenants[:5]:
                        increase = ((recent - historical) / historical * 100)
                        output.append(f"   ⚠️ **{tenant}**: {increase:+.1f}% increase")
                        output.append(f"      Recent: ${recent:.2f}/day vs Historical: ${historical:.2f}/day")
                
                # Show tenants above threshold
                expensive_tenants = [(t, c) for t, c in sorted_tenants if c > cost_threshold]
                if expensive_tenants:
                    output.append(f"\n💸 **TENANTS ABOVE ${cost_threshold:.0f} THRESHOLD**:")
                    for tenant, cost in expensive_tenants[:10]:
                        daily_cost = cost / days
                        output.append(f"   • {tenant}: ${cost:.2f} (${daily_cost:.2f}/day)")
                
                # UAT/Test environment analysis for this service
                uat_tenants = [(t, c) for t, c in sorted_tenants if any(env in t.upper() for env in ['UAT', 'TEST', 'DEV', 'STAGING'])]
                if uat_tenants:
                    total_uat_cost = sum(c for _, c in uat_tenants)
                    output.append(f"\n🧪 **{service_name.upper()} UAT/TEST ENVIRONMENTS**:")
                    output.append(f"   Total UAT cost: ${total_uat_cost:.2f} ({total_uat_cost/total_cost*100:.1f}%)")
                    
                    expensive_uat = [(t, c) for t, c in uat_tenants if c > cost_threshold/3]
                    if expensive_uat:
                        output.append(f"   Expensive UAT tenants:")
                        for tenant, cost in expensive_uat[:5]:
                            daily_cost = cost / days
                            output.append(f"     • {tenant}: ${cost:.2f} (${daily_cost:.2f}/day)")
                
                # Show daily trend for top tenant
                if sorted_tenants and len(daily_tenant_costs[sorted_tenants[0][0]]) >= 5:
                    top_tenant = sorted_tenants[0][0]
                    output.append(f"\n📈 **DAILY TREND - {top_tenant}**:")
                    tenant_daily = daily_tenant_costs[top_tenant]
                    sorted_dates = sorted(tenant_daily.keys())[-7:]
                    for date in sorted_dates:
                        cost = tenant_daily.get(date, 0)
                        output.append(f"   {date}: ${cost:.2f}")
                
                # Service-specific recommendations
                output.append(f"\n💡 **{service_name.upper()} OPTIMIZATION RECOMMENDATIONS**:")
                
                untagged_cost = tenant_costs.get('Untagged', 0)
                if untagged_cost > total_cost * 0.05:
                    output.append(f"   🏷️ ${untagged_cost:.2f} untagged {service_name} costs need organization tags")
                
                if len(expensive_tenants) > 0:
                    output.append(f"   🎯 Review top {len(expensive_tenants)} tenants above ${cost_threshold:.0f} threshold")
                
                if anomalous_tenants:
                    output.append(f"   🚨 Investigate {len(anomalous_tenants)} tenants with recent cost increases")
                
                if uat_tenants and total_uat_cost > total_cost * 0.2:
                    output.append(f"   🧪 UAT costs are {total_uat_cost/total_cost*100:.1f}% of {service_name} total - review necessity")
                
                output.append(f"   📊 Set up {service_name}-specific cost alerts for tenant monitoring")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_service_tenant_costs_with_timeout(), timeout=45.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: {service_name} tenant analysis took longer than 45 seconds"
        except Exception as e:
            return f"❌ Error analyzing {service_name} tenant costs: {str(e)}" 