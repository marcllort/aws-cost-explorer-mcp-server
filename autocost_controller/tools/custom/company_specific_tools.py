"""Company-specific cost analysis tools for advanced monitoring."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP

from ...core.provider_manager import ProviderManager
from ...core.config import Config
from ...core.logger import AutocostLogger


def register_company_specific_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register company-specific advanced cost analysis tools."""
    
    aws_provider = provider_manager.get_provider("aws")
    if not aws_provider:
        return
    
    @mcp.tool()
    async def aws_tenant_anomaly_detector(
        days: int = 7,
        baseline_weeks: int = 4,
        anomaly_threshold: float = 30.0,
        tenant_tag_key: str = "Organization",
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """Company-Specific: Detect unusual tenant spending patterns and cost anomalies."""
        import asyncio
        
        logger.info(f"🚨 Detecting tenant anomalies for {days} days with {baseline_weeks}-week baseline...")
        
        try:
            async def detect_anomalies_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                baseline_start = end_date - timedelta(weeks=baseline_weeks)
                
                # Get current period costs by tenant
                current_response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'TAG', 'Key': tenant_tag_key}
                    ]
                )
                
                # Get baseline period costs by tenant
                baseline_response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': baseline_start.strftime('%Y-%m-%d'),
                        'End': start_date.strftime('%Y-%m-%d')
                    },
                    Granularity='WEEKLY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'TAG', 'Key': tenant_tag_key}
                    ]
                )
                
                # Process current period data
                current_tenant_costs = {}
                current_daily_costs = {}
                
                for result in current_response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            tenant = keys[0] if keys[0] != 'No tag' else 'Untagged'
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            if tenant not in current_tenant_costs:
                                current_tenant_costs[tenant] = 0.0
                                current_daily_costs[tenant] = {}
                            
                            current_tenant_costs[tenant] += cost
                            current_daily_costs[tenant][date] = current_daily_costs[tenant].get(date, 0) + cost
                
                # Process baseline period data
                baseline_tenant_costs = {}
                baseline_weeks_data = {}
                
                for result in baseline_response.get('ResultsByTime', []):
                    week_start = result['TimePeriod']['Start']
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            tenant = keys[0] if keys[0] != 'No tag' else 'Untagged'
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            if tenant not in baseline_tenant_costs:
                                baseline_tenant_costs[tenant] = []
                                baseline_weeks_data[tenant] = {}
                            
                            baseline_tenant_costs[tenant].append(cost)
                            baseline_weeks_data[tenant][week_start] = cost
                
                # Calculate anomalies
                anomalous_tenants = []
                investigation_priorities = []
                
                for tenant in current_tenant_costs:
                    current_cost = current_tenant_costs[tenant]
                    current_daily_avg = current_cost / days
                    
                    if tenant in baseline_tenant_costs and baseline_tenant_costs[tenant]:
                        baseline_weekly_costs = baseline_tenant_costs[tenant]
                        baseline_avg_weekly = sum(baseline_weekly_costs) / len(baseline_weekly_costs)
                        baseline_daily_avg = baseline_avg_weekly / 7
                        
                        if baseline_daily_avg > 0:
                            change_pct = ((current_daily_avg - baseline_daily_avg) / baseline_daily_avg) * 100
                            
                            if abs(change_pct) >= anomaly_threshold:
                                severity = "🔴 CRITICAL" if abs(change_pct) >= 50 else "🟠 HIGH" if abs(change_pct) >= anomaly_threshold else "🟡 MODERATE"
                                
                                anomaly_data = {
                                    'tenant': tenant,
                                    'current_daily': current_daily_avg,
                                    'baseline_daily': baseline_daily_avg,
                                    'change_pct': change_pct,
                                    'change_amount': current_daily_avg - baseline_daily_avg,
                                    'severity': severity,
                                    'total_impact': (current_daily_avg - baseline_daily_avg) * days
                                }
                                anomalous_tenants.append(anomaly_data)
                                
                                # Prioritize for investigation
                                if abs(change_pct) >= 50 or abs(anomaly_data['change_amount']) >= 50:
                                    investigation_priorities.append(anomaly_data)
                
                # Sort by impact
                anomalous_tenants.sort(key=lambda x: abs(x['change_amount']), reverse=True)
                investigation_priorities.sort(key=lambda x: abs(x['total_impact']), reverse=True)
                
                output = ["🚨 **TENANT ANOMALY DETECTION REPORT**", "=" * 60]
                output.append(f"📅 **Analysis Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"📊 **Baseline Period**: {baseline_weeks} weeks ({baseline_start} to {start_date})")
                output.append(f"⚠️ **Anomaly Threshold**: {anomaly_threshold}% change")
                output.append(f"🔍 **Anomalies Detected**: {len(anomalous_tenants)}")
                
                # Show critical investigation priorities
                if investigation_priorities:
                    output.append(f"\n🚨 **IMMEDIATE INVESTIGATION REQUIRED** ({len(investigation_priorities)} tenants):")
                    for i, anomaly in enumerate(investigation_priorities[:5], 1):
                        output.append(f"\n{i}. {anomaly['severity']} **{anomaly['tenant']}**")
                        output.append(f"     Current: ${anomaly['current_daily']:.2f}/day")
                        output.append(f"     Baseline: ${anomaly['baseline_daily']:.2f}/day")
                        output.append(f"     Change: {anomaly['change_pct']:+.1f}% (${anomaly['change_amount']:+.2f}/day)")
                        output.append(f"     Total impact: ${anomaly['total_impact']:+.2f}")
                
                # Show all anomalies
                if anomalous_tenants:
                    output.append(f"\n📊 **ALL DETECTED ANOMALIES**:")
                    for i, anomaly in enumerate(anomalous_tenants[:15], 1):
                        change_emoji = "📈" if anomaly['change_pct'] > 0 else "📉"
                        output.append(f"{i:2d}. {change_emoji} **{anomaly['tenant']}**: {anomaly['change_pct']:+.1f}% (${anomaly['change_amount']:+.2f}/day)")
                
                # Company-specific pattern analysis
                problem_patterns = ['H11', 'A28', 'U14', 'D32', 'E17', 'B38', 'T24', 'R10']
                pattern_anomalies = [a for a in anomalous_tenants if any(pattern in a['tenant'].upper() for pattern in problem_patterns)]
                
                if pattern_anomalies:
                    output.append(f"\n🎯 **KNOWN PROBLEM PATTERN ANOMALIES**:")
                    for anomaly in pattern_anomalies:
                        output.append(f"   • {anomaly['tenant']}: {anomaly['change_pct']:+.1f}% (${anomaly['change_amount']:+.2f}/day)")
                
                # UAT environment anomalies
                uat_anomalies = [a for a in anomalous_tenants if any(env in a['tenant'].upper() for env in ['UAT', 'TEST', 'DEV', 'STAGING'])]
                if uat_anomalies:
                    output.append(f"\n🧪 **UAT ENVIRONMENT ANOMALIES**:")
                    total_uat_impact = sum(a['total_impact'] for a in uat_anomalies)
                    output.append(f"   Total UAT impact: ${total_uat_impact:+.2f}")
                    for anomaly in uat_anomalies[:5]:
                        output.append(f"   • {anomaly['tenant']}: {anomaly['change_pct']:+.1f}% (${anomaly['change_amount']:+.2f}/day)")
                
                # Trend analysis
                if len(anomalous_tenants) > 0:
                    increases = [a for a in anomalous_tenants if a['change_pct'] > 0]
                    decreases = [a for a in anomalous_tenants if a['change_pct'] < 0]
                    
                    output.append(f"\n📈 **TREND SUMMARY**:")
                    output.append(f"   Cost increases: {len(increases)} tenants")
                    output.append(f"   Cost decreases: {len(decreases)} tenants")
                    
                    if increases:
                        total_increase_impact = sum(a['total_impact'] for a in increases)
                        output.append(f"   Total increase impact: ${total_increase_impact:.2f}")
                    
                    if decreases:
                        total_decrease_impact = sum(abs(a['total_impact']) for a in decreases)
                        output.append(f"   Total decrease savings: ${total_decrease_impact:.2f}")
                
                # Action recommendations
                output.append(f"\n💡 **INVESTIGATION ACTIONS**:")
                
                if investigation_priorities:
                    output.append(f"   🚨 Immediate: Investigate {len(investigation_priorities)} critical anomalies")
                    top_tenant = investigation_priorities[0]['tenant']
                    output.append(f"   🎯 Start with: {top_tenant} (highest impact)")
                
                if uat_anomalies:
                    output.append(f"   🧪 Review UAT environments: {len(uat_anomalies)} showing anomalies")
                
                if pattern_anomalies:
                    output.append(f"   🔍 Check known problem patterns: {len(pattern_anomalies)} tenants affected")
                
                output.append(f"   📊 Set up automated anomaly alerts for >25% changes")
                output.append(f"   📅 Weekly anomaly review with business owners")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(detect_anomalies_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Tenant anomaly detection took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error detecting tenant anomalies: {str(e)}"
    
    @mcp.tool()
    async def aws_uat_environment_cost_monitor(
        days: int = 7,
        uat_patterns: Optional[List[str]] = None,
        prod_comparison: bool = True,
        cost_thresholds: Optional[Dict[str, float]] = None,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """Company-Specific: Monitor UAT vs Production cost ratios and detect excessive UAT usage."""
        import asyncio
        
        if uat_patterns is None:
            uat_patterns = ['UAT', 'TEST', 'DEV', 'STAGING']
        
        if cost_thresholds is None:
            cost_thresholds = {'daily': 100.0, 'ratio': 0.3}  # 30% of prod costs
        
        logger.info(f"🧪 Monitoring UAT environment costs for {days} days...")
        
        try:
            async def monitor_uat_costs_with_timeout():
                ce_client = aws_provider.get_client("ce", account_id, region)
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                
                # Get costs by Organization tag
                response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'TAG', 'Key': 'Organization'}
                    ]
                )
                
                # Process UAT vs Production costs
                uat_costs = {}
                prod_costs = {}
                daily_uat_costs = {}
                daily_prod_costs = {}
                total_uat = 0.0
                total_prod = 0.0
                
                for result in response.get('ResultsByTime', []):
                    date = result['TimePeriod']['Start']
                    daily_uat_costs[date] = 0.0
                    daily_prod_costs[date] = 0.0
                    
                    for group in result.get('Groups', []):
                        keys = group.get('Keys', [])
                        if len(keys) >= 1:
                            tenant = keys[0] if keys[0] != 'No tag' else 'Untagged'
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            
                            # Classify as UAT or Production
                            is_uat = any(pattern in tenant.upper() for pattern in uat_patterns)
                            
                            if is_uat:
                                if tenant not in uat_costs:
                                    uat_costs[tenant] = 0.0
                                uat_costs[tenant] += cost
                                daily_uat_costs[date] += cost
                                total_uat += cost
                            else:
                                if tenant not in prod_costs:
                                    prod_costs[tenant] = 0.0
                                prod_costs[tenant] += cost
                                daily_prod_costs[date] += cost
                                total_prod += cost
                
                # Calculate metrics
                daily_uat_avg = total_uat / days if days > 0 else 0
                daily_prod_avg = total_prod / days if days > 0 else 0
                uat_to_prod_ratio = (total_uat / total_prod) if total_prod > 0 else 0
                
                output = ["🧪 **UAT ENVIRONMENT COST MONITOR**", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"🎯 **UAT Patterns**: {', '.join(uat_patterns)}")
                output.append(f"💰 **Total UAT Cost**: ${total_uat:.2f}")
                output.append(f"🏭 **Total Production Cost**: ${total_prod:.2f}")
                output.append(f"📊 **UAT/Prod Ratio**: {uat_to_prod_ratio:.1%}")
                output.append(f"📈 **Daily UAT Average**: ${daily_uat_avg:.2f}")
                
                # UAT cost health assessment
                threshold_ratio = cost_thresholds.get('ratio', 0.3)
                if uat_to_prod_ratio > threshold_ratio:
                    output.append(f"🔴 **UAT COST ALERT**: {uat_to_prod_ratio:.1%} exceeds {threshold_ratio:.1%} threshold")
                elif uat_to_prod_ratio > threshold_ratio * 0.8:
                    output.append(f"🟡 **UAT COST WARNING**: {uat_to_prod_ratio:.1%} approaching {threshold_ratio:.1%} threshold")
                else:
                    output.append(f"🟢 **UAT COST HEALTHY**: {uat_to_prod_ratio:.1%} within acceptable range")
                
                # Show expensive UAT environments
                sorted_uat = sorted(uat_costs.items(), key=lambda x: x[1], reverse=True)
                threshold_daily = cost_thresholds.get('daily', 100.0)
                expensive_uat = [(t, c) for t, c in sorted_uat if c > threshold_daily]
                
                if expensive_uat:
                    output.append(f"\n💸 **EXPENSIVE UAT ENVIRONMENTS** (>{threshold_daily:.0f}/week):")
                    for i, (tenant, cost) in enumerate(expensive_uat[:10], 1):
                        daily_cost = cost / days
                        monthly_proj = daily_cost * 30
                        cost_emoji = "🔴" if daily_cost > threshold_daily * 2 else "🟠"
                        
                        output.append(f"{i:2d}. {cost_emoji} **{tenant}**")
                        output.append(f"     Weekly: ${cost:.2f} (${daily_cost:.2f}/day)")
                        output.append(f"     Monthly projection: ${monthly_proj:.2f}")
                
                # Daily cost trends
                output.append(f"\n📈 **DAILY UAT vs PRODUCTION TRENDS**:")
                sorted_dates = sorted(daily_uat_costs.keys())[-7:]
                for date in sorted_dates:
                    uat_cost = daily_uat_costs[date]
                    prod_cost = daily_prod_costs[date]
                    daily_ratio = (uat_cost / prod_cost) if prod_cost > 0 else 0
                    ratio_emoji = "🔴" if daily_ratio > threshold_ratio else "🟡" if daily_ratio > threshold_ratio * 0.8 else "🟢"
                    
                    output.append(f"   {date}: UAT ${uat_cost:.2f} | Prod ${prod_cost:.2f} | Ratio {daily_ratio:.1%} {ratio_emoji}")
                
                # Company-specific UAT analysis
                company_uat_patterns = ['H11UAT', 'A28UAT', 'U14UAT', 'B38UAT', 'T24UAT']
                company_uat_costs = {pattern: 0 for pattern in company_uat_patterns}
                
                for tenant, cost in uat_costs.items():
                    for pattern in company_uat_patterns:
                        if pattern in tenant.upper():
                            company_uat_costs[pattern] += cost
                
                active_company_uat = {k: v for k, v in company_uat_costs.items() if v > 0}
                if active_company_uat:
                    output.append(f"\n🏢 **COMPANY-SPECIFIC UAT ENVIRONMENTS**:")
                    for pattern, cost in sorted(active_company_uat.items(), key=lambda x: x[1], reverse=True):
                        daily_cost = cost / days
                        monthly_proj = daily_cost * 30
                        output.append(f"   • {pattern}: ${cost:.2f} (${daily_cost:.2f}/day, ${monthly_proj:.2f}/month)")
                
                # Shutdown candidates
                shutdown_candidates = []
                for tenant, cost in sorted_uat:
                    daily_cost = cost / days
                    if daily_cost > 20:  # More than $20/day for UAT
                        # Check if it's been consistently high
                        high_days = 0
                        for date in sorted_dates:
                            # Estimate daily cost for this tenant (simplified)
                            if daily_uat_costs[date] > 0:
                                estimated_tenant_daily = (cost / days) * (daily_uat_costs[date] / daily_uat_avg) if daily_uat_avg > 0 else 0
                                if estimated_tenant_daily > 15:
                                    high_days += 1
                        
                        if high_days >= len(sorted_dates) * 0.7:  # High for 70%+ of days
                            shutdown_candidates.append((tenant, cost, daily_cost))
                
                if shutdown_candidates:
                    output.append(f"\n🛑 **UAT SHUTDOWN CANDIDATES** ({len(shutdown_candidates)} environments):")
                    total_shutdown_savings = sum(daily_cost for _, _, daily_cost in shutdown_candidates)
                    output.append(f"   Potential daily savings: ${total_shutdown_savings:.2f}")
                    output.append(f"   Potential monthly savings: ${total_shutdown_savings * 30:.2f}")
                    
                    for i, (tenant, total_cost, daily_cost) in enumerate(shutdown_candidates[:5], 1):
                        output.append(f"{i:2d}. {tenant}: ${daily_cost:.2f}/day (${total_cost:.2f} total)")
                
                # Right-sizing recommendations
                output.append(f"\n💡 **UAT OPTIMIZATION RECOMMENDATIONS**:")
                
                if uat_to_prod_ratio > threshold_ratio:
                    excess_ratio = uat_to_prod_ratio - threshold_ratio
                    excess_cost = excess_ratio * total_prod
                    output.append(f"   🎯 Reduce UAT costs by ${excess_cost:.2f} to reach {threshold_ratio:.1%} target")
                
                if expensive_uat:
                    output.append(f"   🧪 Review {len(expensive_uat)} expensive UAT environments")
                
                if shutdown_candidates:
                    output.append(f"   🛑 Consider shutting down {len(shutdown_candidates)} consistently high UAT environments")
                
                output.append(f"   ⏰ Implement auto-shutdown schedules (evenings, weekends)")
                output.append(f"   📏 Right-size UAT instances (smaller than production)")
                output.append(f"   🔄 Share UAT environments across teams where possible")
                output.append(f"   📊 Set up UAT cost alerts at ${threshold_daily:.0f}/day threshold")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(monitor_uat_costs_with_timeout(), timeout=45.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: UAT environment monitoring took longer than 45 seconds"
        except Exception as e:
            return f"❌ Error monitoring UAT environments: {str(e)}" 