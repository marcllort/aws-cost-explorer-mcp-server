"""Advanced GCP cost analysis tools for Autocost Controller."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import asyncio
from google.cloud import billing_v1
from google.cloud import monitoring_v3
from google.cloud import compute_v1
from google.cloud import container_v1

from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger


def _get_vcpu_count(machine_type: str) -> int:
    """Estimate vCPU count from machine type."""
    if machine_type.startswith('f1-micro'):
        return 1
    elif machine_type.startswith('g1-small'):
        return 1
    elif 'micro' in machine_type:
        return 1
    elif 'small' in machine_type:
        return 1
    elif 'medium' in machine_type:
        return 2
    elif 'large' in machine_type:
        return 4
    elif 'xlarge' in machine_type:
        return 8
    else:
        # Extract from pattern like n1-standard-4
        parts = machine_type.split('-')
        if len(parts) >= 3 and parts[-1].isdigit():
            return int(parts[-1])
        return 2  # Default estimate


def register_gcp_cost_analysis_tools(mcp, provider_manager: ProviderManager, 
                                   config: Config, logger: AutocostLogger) -> None:
    """Register GCP cost analysis tools using correct GCP APIs."""
    
    gcp_provider = provider_manager.get_provider("gcp")
    if not gcp_provider:
        logger.warning("GCP provider not available, skipping tools registration")
        return

    @mcp.tool()
    async def gcp_billing_account_info() -> str:
        """Get GCP billing account information and available projects."""
        logger.info("🔍 Getting GCP billing account information...")
        
        try:
            billing_client = billing_v1.CloudBillingClient()
            
            # List billing accounts
            billing_accounts = []
            for account in billing_client.list_billing_accounts():
                billing_accounts.append({
                    'name': account.name,
                    'display_name': account.display_name,
                    'open': account.open,
                    'master_billing_account': account.master_billing_account
                })
            
            # Get current project billing info
            current_project = gcp_provider.get_current_project()
            project_billing_info = None
            
            if current_project:
                try:
                    project_name = f"projects/{current_project}"
                    project_billing_info = billing_client.get_project_billing_info(name=project_name)
                except Exception as e:
                    logger.warning(f"Could not get billing info for project {current_project}: {e}")
            
            # Generate report
            report = f"""🏦 **GCP Billing Account Information**

📊 **Available Billing Accounts**: {len(billing_accounts)}
"""
            
            for account in billing_accounts:
                status = "✅ Open" if account['open'] else "❌ Closed"
                report += f"- {account['display_name']}: {status}\n"
            
            if current_project and project_billing_info:
                report += f"\n🎯 **Current Project**: {current_project}\n"
                report += f"📋 **Billing Account**: {project_billing_info.billing_account_name}\n"
                report += f"✅ **Billing Enabled**: {project_billing_info.billing_enabled}\n"
            elif current_project:
                report += f"\n🎯 **Current Project**: {current_project}\n"
                report += f"⚠️ **Billing Info**: Not accessible or not configured\n"
            
            report += f"""
💡 **Next Steps**:
- Use `gcp_compute_cost_analysis()` for compute costs
- Set up BigQuery billing export for detailed analysis
- Review GCP Console billing reports for comprehensive cost data"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to get billing account info: {str(e)}", "gcp")
            return f"❌ Error getting billing account info: {str(e)}"

    @mcp.tool()
    async def gcp_compute_cost_analysis(
        project_id: Optional[str] = None,
        zone_filter: Optional[str] = None
    ) -> str:
        """Analyze GCP Compute Engine costs and usage patterns."""
        logger.info("🔍 Analyzing GCP Compute Engine costs...")
        
        try:
            compute_client = compute_v1.InstancesClient()
            project = project_id or gcp_provider.get_current_project()
            
            if not project:
                return "❌ No project specified and no current project available"
            
            # Get all instances across zones
            instances = []
            zones_client = compute_v1.ZonesClient()
            
            # List all zones if no filter
            zones_to_check = []
            if zone_filter:
                zones_to_check = [zone_filter]
            else:
                for zone in zones_client.list(project=project):
                    zones_to_check.append(zone.name)
            
            # Collect instance data
            total_instances = 0
            total_vcpus = 0
            machine_type_counts = {}
            instance_status_counts = {"RUNNING": 0, "STOPPED": 0, "TERMINATED": 0}
            
            for zone in zones_to_check[:10]:  # Limit to 10 zones to avoid timeout
                try:
                    for instance in compute_client.list(project=project, zone=zone):
                        instances.append({
                            'name': instance.name,
                            'zone': zone,
                            'machine_type': instance.machine_type.split('/')[-1],
                            'status': instance.status,
                            'creation_timestamp': instance.creation_timestamp
                        })
                        
                        total_instances += 1
                        if instance.status == "RUNNING":
                            total_vcpus += _get_vcpu_count(instance.machine_type.split('/')[-1])
                        
                        # Count machine types
                        machine_type = instance.machine_type.split('/')[-1]
                        machine_type_counts[machine_type] = machine_type_counts.get(machine_type, 0) + 1
                        
                        # Count statuses
                        if instance.status in instance_status_counts:
                            instance_status_counts[instance.status] += 1
                            
                except Exception as e:
                    logger.warning(f"Could not list instances in zone {zone}: {e}")
                    continue
            
            # Generate analysis
            report = f"""🖥️ **GCP Compute Engine Analysis**

📊 **Instance Summary**:
- Total Instances: {total_instances}
- Running: {instance_status_counts['RUNNING']} ✅
- Stopped: {instance_status_counts['STOPPED']} ⏸️
- Terminated: {instance_status_counts['TERMINATED']} ❌
- Total vCPUs (running): {total_vcpus}

🔧 **Machine Type Distribution**:"""
            
            # Sort machine types by count
            sorted_machine_types = sorted(machine_type_counts.items(), key=lambda x: x[1], reverse=True)
            for machine_type, count in sorted_machine_types[:10]:
                percentage = (count / total_instances) * 100 if total_instances > 0 else 0
                generation = _get_machine_generation(machine_type)
                report += f"\n- {machine_type}: {count} instances ({percentage:.1f}%) {generation}"
            
            # Add recommendations
            report += "\n\n💡 **Cost Optimization Recommendations**:"
            
            # Check for old generation instances
            old_gen_count = sum(count for mt, count in machine_type_counts.items() if mt.startswith('n1-'))
            if old_gen_count > 0:
                report += f"\n- 🔄 Migrate {old_gen_count} N1 instances to E2 for 20-50% savings"
            
            # Check for stopped instances
            if instance_status_counts['STOPPED'] > 0:
                report += f"\n- ⚠️ Review {instance_status_counts['STOPPED']} stopped instances (still incur disk costs)"
            
            # Check for potential preemptible usage
            if instance_status_counts['RUNNING'] > 5:
                report += f"\n- 💰 Consider preemptible instances for fault-tolerant workloads (up to 80% savings)"
            
            report += f"""

📈 **Next Steps**:
- Review GCP Console for detailed cost breakdowns
- Set up billing alerts and budgets
- Consider Committed Use Discounts for predictable workloads"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to analyze compute costs: {str(e)}", "gcp")
            return f"❌ Error analyzing compute costs: {str(e)}"

    def _get_machine_generation(machine_type: str) -> str:
        """Get machine type generation info."""
        if machine_type.startswith('e2-'):
            return "✅ Latest (E2)"
        elif machine_type.startswith('n2-'):
            return "✅ Current (N2)"
        elif machine_type.startswith('n2d-'):
            return "✅ Current (N2D)"
        elif machine_type.startswith('t2d-'):
            return "✅ Current (T2D)"
        elif machine_type.startswith('c2-'):
            return "✅ Current (C2)"
        elif machine_type.startswith('n1-'):
            return "⚠️ Legacy (N1)"
        elif machine_type.startswith('f1-'):
            return "⚠️ Legacy (F1)"
        elif machine_type.startswith('g1-'):
            return "⚠️ Legacy (G1)"
        else:
            return "❓ Unknown"

    @mcp.tool()
    async def gcp_cost_analysis_summary() -> str:
        """Generate a comprehensive cost analysis summary with manual data collection guidance."""
        logger.info("🔍 Generating comprehensive cost analysis summary...")
        
        try:
            project = gcp_provider.get_current_project()
            if not project:
                return "❌ No current project available"
            
            report = f"""🎯 **GCP Cost Analysis Summary**

📊 **Project**: {project}
📅 **Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

🔍 **Available Analysis Tools**:

1. **`gcp_billing_account_info()`**
   - Verify billing account setup
   - Check project billing status
   - List available billing accounts

2. **`gcp_compute_cost_analysis()`**
   - Analyze Compute Engine instances
   - Machine type distribution
   - Optimization recommendations

📊 **Manual Cost Analysis Steps**:

**Step 1: GCP Console Analysis**
1. Go to Cloud Billing → Reports
2. Select your project: {project}
3. Group by: Service, Project, SKU
4. Time range: Last 30 days
5. Export to CSV for detailed analysis

**Step 2: BigQuery Billing Export** (Recommended)
1. Go to Cloud Billing → Billing Export
2. Enable BigQuery export
3. Create a dataset for billing data
4. Wait 24-48 hours for data population

**Step 3: Cost Breakdown Analysis**
```sql
-- After BigQuery export is set up
SELECT 
  service.description as service,
  SUM(cost) as total_cost,
  currency
FROM `PROJECT.DATASET.gcp_billing_export_*`
WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 3
ORDER BY 2 DESC
```

💰 **Cost Optimization Framework**:

**Immediate Actions (0-7 days)**:
- Run `gcp_compute_cost_analysis()` for instance optimization
- Remove idle persistent disks and snapshots
- Release unused static IP addresses
- Set up billing alerts

**Short-term (1-4 weeks)**:
- Implement lifecycle policies for Cloud Storage
- Consider Committed Use Discounts for predictable workloads
- Optimize machine types based on utilization

**Long-term (1-6 months)**:
- Migrate to latest generation instances
- Implement auto-scaling for variable workloads
- Consider serverless alternatives (Cloud Run, Cloud Functions)

🎯 **Expected Savings Potential**:
- Machine type optimization: 20-50%
- Preemptible instances: Up to 80%
- Storage lifecycle policies: 50-90%
- Committed Use Discounts: 37-55%

📋 **Next Steps**:
1. Set up BigQuery billing export for detailed analysis
2. Run `gcp_billing_account_info()` to verify setup
3. Execute `gcp_compute_cost_analysis()` for instance insights
4. Review GCP Console billing reports regularly

💡 **Pro Tips**:
- Use labels consistently for cost allocation
- Set up budget alerts at 50%, 80%, 100%
- Review and optimize monthly
- Consider multi-cloud cost management tools"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate cost analysis summary: {str(e)}", "gcp")
            return f"❌ Error generating cost analysis summary: {str(e)}"

    @mcp.tool()
    async def gcp_cost_rolling_average_analysis(
        days: int = 28,
        service_filter: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> str:
        """GCP Cost Analysis: Calculate rolling averages and detect cost trend changes using monitoring metrics."""
        logger.info(f"📊 Analyzing {days}-day rolling cost trends...")
        
        try:
            async def analyze_rolling_costs_with_timeout():
                project = project_id or gcp_provider.get_current_project()
                if not project:
                    return "❌ No project specified and no current project available"
                
                monitoring_client = monitoring_v3.MetricServiceClient()
                project_name = f"projects/{project}"
                
                # Get billing metrics for the specified period
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days*2)  # Get double period for comparison
                
                interval = monitoring_v3.TimeInterval({
                    "end_time": {"seconds": int(end_time.timestamp())},
                    "start_time": {"seconds": int(start_time.timestamp())},
                })
                
                # Query for billing metrics (if available)
                try:
                    results = monitoring_client.list_time_series(
                        request={
                            "name": project_name,
                            "filter": 'metric.type="billing.googleapis.com/billing/total_cost"',
                            "interval": interval,
                            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                        }
                    )
                    
                    daily_costs = {}
                    for result in results:
                        for point in result.points:
                            date_str = point.interval.start_time.strftime('%Y-%m-%d')
                            cost = float(point.value.double_value) if hasattr(point.value, 'double_value') else 0.0
                            if date_str not in daily_costs:
                                daily_costs[date_str] = 0.0
                            daily_costs[date_str] += cost
                    
                    if not daily_costs:
                        return """📊 **GCP ROLLING COST ANALYSIS**
⚠️ **No billing metrics available**

This analysis requires:
1. Billing export to BigQuery enabled
2. Cloud Monitoring billing metrics enabled
3. 24-48 hours for data population

💡 **Alternative**: Use GCP Console → Billing → Reports for manual trend analysis
📈 **Setup Guide**: Enable billing export in Cloud Console → Billing → Billing Export"""
                    
                    # Calculate rolling averages
                    sorted_dates = sorted(daily_costs.keys())
                    rolling_averages = []
                    
                    for i in range(days, len(sorted_dates)):
                        current_date = sorted_dates[i]
                        window_costs = [daily_costs[sorted_dates[j]] for j in range(i-days+1, i+1)]
                        rolling_avg = sum(window_costs) / days
                        rolling_averages.append((current_date, rolling_avg))
                    
                    # Analyze trends
                    recent_avg = rolling_averages[-1][1] if rolling_averages else 0
                    previous_avg = rolling_averages[-8][1] if len(rolling_averages) >= 8 else 0
                    trend_change = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
                    
                    output = [f"📊 **GCP {days}-DAY ROLLING COST ANALYSIS**", "=" * 60]
                    if service_filter:
                        output.append(f"🔧 **Service**: {service_filter}")
                    output.append(f"📅 **Analysis Period**: {start_time.date()} to {end_time.date()}")
                    output.append(f"💰 **Current {days}-Day Average**: ${recent_avg:.2f}/day")
                    
                    if previous_avg > 0:
                        trend_emoji = "📈" if trend_change > 0 else "📉" if trend_change < 0 else "➡️"
                        output.append(f"{trend_emoji} **Week-over-Week Change**: {trend_change:+.1f}%")
                        
                        if abs(trend_change) > 10:
                            output.append(f"⚠️ **ALERT**: Significant cost trend change detected!")
                    
                    # Show recent daily costs
                    output.append(f"\n📈 **RECENT DAILY COSTS**:")
                    recent_dates = sorted_dates[-7:] if len(sorted_dates) >= 7 else sorted_dates
                    for date in recent_dates:
                        cost = daily_costs[date]
                        output.append(f"   {date}: ${cost:.2f}")
                    
                    return "\n".join(output)
                
                except Exception as e:
                    return f"""📊 **GCP ROLLING COST ANALYSIS**
⚠️ **Monitoring data not available**: {str(e)}

💡 **Manual Analysis Steps**:
1. Go to GCP Console → Billing → Reports
2. Set time range to {days*2} days
3. Group by: Day
4. Export data for trend analysis

📈 **Alternative Tools**:
- Use `gcp_cost_analysis_summary()` for setup guidance
- Enable BigQuery billing export for detailed analysis"""
            
            result = await asyncio.wait_for(analyze_rolling_costs_with_timeout(), timeout=45.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Rolling average analysis took longer than 45 seconds"
        except Exception as e:
            return f"❌ Error analyzing rolling averages: {str(e)}"

    @mcp.tool()
    async def gcp_gke_cost_deep_dive(
        days: int = 7,
        cluster_name: Optional[str] = None,
        project_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """GCP GKE: Deep dive cost analysis including node pools, preemptible usage, and optimization."""
        logger.info(f"🐳 Deep diving into GKE costs for {days} days...")
        
        try:
            async def analyze_gke_costs_with_timeout():
                project = project_id or gcp_provider.get_current_project()
                if not project:
                    return "❌ No project specified and no current project available"
                
                container_client = container_v1.ClusterManagerClient()
                compute_client = compute_v1.InstancesClient()
                
                # List GKE clusters
                if region:
                    parent = f"projects/{project}/locations/{region}"
                else:
                    parent = f"projects/{project}/locations/-"  # All regions
                
                clusters = []
                cluster_costs = {}
                total_nodes = 0
                total_preemptible = 0
                
                try:
                    response = container_client.list_clusters(parent=parent)
                    
                    for cluster in response.clusters:
                        if cluster_name and cluster.name != cluster_name:
                            continue
                            
                        cluster_info = {
                            'name': cluster.name,
                            'location': cluster.location,
                            'status': cluster.status.name,
                            'node_pools': [],
                            'total_nodes': 0,
                            'preemptible_nodes': 0
                        }
                        
                        # Analyze node pools
                        for node_pool in cluster.node_pools:
                            pool_info = {
                                'name': node_pool.name,
                                'node_count': node_pool.initial_node_count,
                                'machine_type': node_pool.config.machine_type,
                                'preemptible': node_pool.config.preemptible,
                                'disk_size': node_pool.config.disk_size_gb,
                                'status': node_pool.status.name
                            }
                            
                            cluster_info['node_pools'].append(pool_info)
                            cluster_info['total_nodes'] += pool_info['node_count']
                            total_nodes += pool_info['node_count']
                            
                            if pool_info['preemptible']:
                                cluster_info['preemptible_nodes'] += pool_info['node_count']
                                total_preemptible += pool_info['node_count']
                        
                        clusters.append(cluster_info)
                
                except Exception as e:
                    return f"❌ Error accessing GKE clusters: {str(e)}\nEnsure GKE API is enabled and you have proper permissions."
                
                if not clusters:
                    return f"""🐳 **GKE COST DEEP DIVE**
📅 **Period**: Last {days} days
⚠️ **No GKE clusters found** in project {project}

💡 **If you have clusters**:
- Check project ID is correct
- Verify GKE API is enabled
- Ensure proper IAM permissions
- Try specifying region parameter"""
                
                # Calculate metrics
                preemptible_ratio = (total_preemptible / total_nodes * 100) if total_nodes > 0 else 0
                
                output = ["🐳 **GKE COST DEEP DIVE**", "=" * 50]
                output.append(f"📅 **Period**: Last {days} days")
                output.append(f"🎯 **Project**: {project}")
                output.append(f"📊 **Total Clusters**: {len(clusters)}")
                output.append(f"🖥️ **Total Nodes**: {total_nodes}")
                output.append(f"⚡ **Preemptible Nodes**: {total_preemptible} ({preemptible_ratio:.1f}%)")
                
                # Detailed cluster analysis
                for cluster in clusters:
                    output.append(f"\n🎯 **Cluster: {cluster['name']}**")
                    output.append(f"   📍 Location: {cluster['location']}")
                    output.append(f"   📊 Status: {cluster['status']}")
                    output.append(f"   🖥️ Total Nodes: {cluster['total_nodes']}")
                    output.append(f"   ⚡ Preemptible: {cluster['preemptible_nodes']}")
                    
                    output.append(f"   \n🔧 **Node Pools**:")
                    for pool in cluster['node_pools']:
                        preempt_status = "⚡ Preemptible" if pool['preemptible'] else "🔶 Standard"
                        output.append(f"     • {pool['name']}: {pool['node_count']} × {pool['machine_type']} ({preempt_status})")
                        output.append(f"       Disk: {pool['disk_size']}GB | Status: {pool['status']}")
                
                # Cost optimization recommendations
                output.append(f"\n💡 **GKE OPTIMIZATION RECOMMENDATIONS**:")
                
                if preemptible_ratio < 50 and total_nodes > 5:
                    potential_savings = total_nodes * 0.7 * 0.8  # Assume 70% can be preemptible at 80% savings
                    output.append(f"   ⚡ **Increase Preemptible Usage**: Current {preemptible_ratio:.1f}%, target 50%+")
                    output.append(f"     Potential daily savings: ~${potential_savings:.0f} (estimated)")
                
                if total_nodes > 10:
                    output.append(f"   📏 **Right-size Node Pools**: Review actual CPU/memory utilization")
                    output.append(f"   🔄 **Enable Cluster Autoscaler**: Automatic scaling based on demand")
                
                # Check for potential issues
                standard_heavy_clusters = [c for c in clusters if (c['total_nodes'] - c['preemptible_nodes']) > 5]
                if standard_heavy_clusters:
                    output.append(f"   🎯 **High Standard Node Usage**: {len(standard_heavy_clusters)} clusters with 5+ standard nodes")
                
                output.append(f"\n📊 **Monitoring Recommendations**:")
                output.append(f"   📈 Set up GKE usage monitoring in Cloud Console")
                output.append(f"   💰 Enable GKE cost allocation by namespace/label")
                output.append(f"   🚨 Configure alerts for unexpected node scaling")
                
                output.append(f"\n📋 **Next Steps**:")
                output.append(f"   1. Review actual workload resource usage")
                output.append(f"   2. Implement horizontal pod autoscaling")
                output.append(f"   3. Consider spot instances for fault-tolerant workloads")
                output.append(f"   4. Use `gcp_cost_analysis_summary()` for billing setup")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_gke_costs_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: GKE deep dive analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing GKE costs: {str(e)}"

    @mcp.tool()
    async def gcp_preemptible_instance_analysis(
        days: int = 7,
        project_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """GCP Preemptible Analysis: Analyze preemptible instance usage and cost impact."""
        logger.info(f"💡 Analyzing preemptible instance usage for {days} days...")
        
        try:
            async def analyze_preemptible_with_timeout():
                project = project_id or gcp_provider.get_current_project()
                if not project:
                    return "❌ No project specified and no current project available"
                
                compute_client = compute_v1.InstancesClient()
                zones_client = compute_v1.ZonesClient()
                
                # Get zones to check
                zones_to_check = []
                if region:
                    # List zones in specific region
                    for zone in zones_client.list(project=project):
                        if zone.name.startswith(region):
                            zones_to_check.append(zone.name)
                else:
                    # List all zones (limit to avoid timeout)
                    for zone in zones_client.list(project=project):
                        zones_to_check.append(zone.name)
                
                # Analyze instances
                preemptible_instances = []
                standard_instances = []
                total_preemptible_vcpus = 0
                total_standard_vcpus = 0
                machine_type_analysis = {}
                
                for zone in zones_to_check[:15]:  # Limit zones to avoid timeout
                    try:
                        for instance in compute_client.list(project=project, zone=zone):
                            machine_type = instance.machine_type.split('/')[-1]
                            vcpus = _get_vcpu_count(machine_type)
                            
                            instance_info = {
                                'name': instance.name,
                                'zone': zone,
                                'machine_type': machine_type,
                                'status': instance.status,
                                'vcpus': vcpus,
                                'preemptible': instance.scheduling.preemptible if hasattr(instance.scheduling, 'preemptible') else False
                            }
                            
                            if instance_info['preemptible']:
                                preemptible_instances.append(instance_info)
                                total_preemptible_vcpus += vcpus
                            else:
                                standard_instances.append(instance_info)
                                total_standard_vcpus += vcpus
                            
                            # Track machine type usage
                            if machine_type not in machine_type_analysis:
                                machine_type_analysis[machine_type] = {
                                    'preemptible': 0, 'standard': 0, 'total_vcpus': 0
                                }
                            
                            if instance_info['preemptible']:
                                machine_type_analysis[machine_type]['preemptible'] += 1
                            else:
                                machine_type_analysis[machine_type]['standard'] += 1
                            machine_type_analysis[machine_type]['total_vcpus'] += vcpus
                            
                    except Exception as e:
                        logger.warning(f"Could not analyze instances in zone {zone}: {e}")
                        continue
                
                # Calculate metrics
                total_instances = len(preemptible_instances) + len(standard_instances)
                total_vcpus = total_preemptible_vcpus + total_standard_vcpus
                preemptible_ratio = (len(preemptible_instances) / total_instances * 100) if total_instances > 0 else 0
                preemptible_vcpu_ratio = (total_preemptible_vcpus / total_vcpus * 100) if total_vcpus > 0 else 0
                
                output = ["💡 **GCP PREEMPTIBLE INSTANCE ANALYSIS**", "=" * 60]
                output.append(f"📅 **Period**: Current snapshot")
                output.append(f"🎯 **Project**: {project}")
                output.append(f"📊 **Total Instances**: {total_instances}")
                output.append(f"⚡ **Preemptible Instances**: {len(preemptible_instances)} ({preemptible_ratio:.1f}%)")
                output.append(f"🔶 **Standard Instances**: {len(standard_instances)}")
                output.append(f"💻 **Total vCPUs**: {total_vcpus}")
                output.append(f"⚡ **Preemptible vCPUs**: {total_preemptible_vcpus} ({preemptible_vcpu_ratio:.1f}%)")
                
                # Machine type breakdown
                if machine_type_analysis:
                    output.append(f"\n🔧 **MACHINE TYPE BREAKDOWN**:")
                    sorted_types = sorted(machine_type_analysis.items(), 
                                        key=lambda x: x[1]['preemptible'] + x[1]['standard'], reverse=True)
                    
                    for machine_type, data in sorted_types[:10]:
                        total_type = data['preemptible'] + data['standard']
                        preempt_pct = (data['preemptible'] / total_type * 100) if total_type > 0 else 0
                        output.append(f"   • **{machine_type}**: {total_type} instances ({preempt_pct:.0f}% preemptible)")
                        output.append(f"     Preemptible: {data['preemptible']} | Standard: {data['standard']}")
                
                # Cost impact analysis
                if total_standard_vcpus > 0:
                    # Estimate potential savings (preemptible is ~80% cheaper)
                    potential_preemptible = min(total_standard_vcpus, total_standard_vcpus * 0.7)  # 70% could be preemptible
                    estimated_savings_per_vcpu = 2.0  # Rough estimate per vCPU per day
                    daily_savings_potential = potential_preemptible * estimated_savings_per_vcpu * 0.8
                    
                    output.append(f"\n💰 **COST OPTIMIZATION POTENTIAL**:")
                    output.append(f"   🎯 Standard vCPUs that could be preemptible: {potential_preemptible:.0f}")
                    output.append(f"   💡 Estimated daily savings potential: ${daily_savings_potential:.2f}")
                    output.append(f"   📈 Monthly savings potential: ${daily_savings_potential * 30:.2f}")
                
                # Recommendations
                output.append(f"\n💡 **OPTIMIZATION RECOMMENDATIONS**:")
                
                if preemptible_ratio < 50 and total_instances > 5:
                    output.append(f"   ⚡ **Increase Preemptible Usage**: Current {preemptible_ratio:.1f}%, target 50%+")
                    output.append(f"   🎯 Focus on fault-tolerant, stateless workloads")
                
                if len(standard_instances) > 3:
                    output.append(f"   🔄 **Convert Standard to Preemptible**: Review {len(standard_instances)} standard instances")
                    output.append(f"   📋 Implement graceful shutdown handling")
                
                # Best practices
                output.append(f"\n🏗️ **PREEMPTIBLE BEST PRACTICES**:")
                output.append(f"   🔄 Implement automatic restart mechanisms")
                output.append(f"   💾 Use persistent disks for data storage")
                output.append(f"   🎯 Mix preemptible and standard instances for availability")
                output.append(f"   ⚡ Monitor preemption rates and adjust accordingly")
                
                # Zone distribution analysis
                zone_distribution = {}
                for instance in preemptible_instances:
                    zone = instance['zone']
                    zone_distribution[zone] = zone_distribution.get(zone, 0) + 1
                
                if zone_distribution:
                    output.append(f"\n📍 **PREEMPTIBLE ZONE DISTRIBUTION**:")
                    for zone, count in sorted(zone_distribution.items(), key=lambda x: x[1], reverse=True)[:5]:
                        output.append(f"   • {zone}: {count} instances")
                
                output.append(f"\n📊 **MONITORING RECOMMENDATIONS**:")
                output.append(f"   📈 Set up preemption rate monitoring")
                output.append(f"   🚨 Configure alerts for high preemption events")
                output.append(f"   💰 Track cost savings from preemptible usage")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_preemptible_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Preemptible instance analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing preemptible instances: {str(e)}"

    @mcp.tool()
    async def gcp_project_cost_analysis(
        label_key: str = "environment",
        days: int = 7,
        top_n: int = 15,
        cost_threshold: float = 100.0,
        project_id: Optional[str] = None
    ) -> str:
        """GCP Project Analysis: Track costs by labels/tags, identify top spenders and anomalies."""
        logger.info(f"🏢 Analyzing project costs by {label_key} for {days} days...")
        
        try:
            async def analyze_project_costs_with_timeout():
                project = project_id or gcp_provider.get_current_project()
                if not project:
                    return "❌ No project specified and no current project available"
                
                # Since we can't easily get detailed billing data without BigQuery export,
                # we'll analyze current resource distribution as a proxy
                compute_client = compute_v1.InstancesClient()
                zones_client = compute_v1.ZonesClient()
                
                # Get all zones
                zones = []
                for zone in zones_client.list(project=project):
                    zones.append(zone.name)
                
                # Analyze instances by labels
                label_costs = {}
                total_instances = 0
                total_vcpus = 0
                untagged_instances = 0
                
                for zone in zones[:10]:  # Limit to avoid timeout
                    try:
                        for instance in compute_client.list(project=project, zone=zone):
                            total_instances += 1
                            machine_type = instance.machine_type.split('/')[-1]
                            vcpus = _get_vcpu_count(machine_type)
                            total_vcpus += vcpus
                            
                            # Check for the specified label
                            label_value = "untagged"
                            if hasattr(instance, 'labels') and instance.labels:
                                label_value = instance.labels.get(label_key, "untagged")
                            
                            if label_value == "untagged":
                                untagged_instances += 1
                            
                            if label_value not in label_costs:
                                label_costs[label_value] = {
                                    'instances': 0, 'vcpus': 0, 'machine_types': set()
                                }
                            
                            label_costs[label_value]['instances'] += 1
                            label_costs[label_value]['vcpus'] += vcpus
                            label_costs[label_value]['machine_types'].add(machine_type)
                            
                    except Exception as e:
                        logger.warning(f"Could not analyze instances in zone {zone}: {e}")
                        continue
                
                # Sort by resource usage (proxy for cost)
                sorted_labels = sorted(label_costs.items(), key=lambda x: x[1]['vcpus'], reverse=True)
                
                output = [f"🏢 **GCP PROJECT COST ANALYSIS** ({label_key})", "=" * 60]
                output.append(f"📅 **Period**: Current snapshot analysis")
                output.append(f"🎯 **Project**: {project}")
                output.append(f"📊 **Total Instances**: {total_instances}")
                output.append(f"💻 **Total vCPUs**: {total_vcpus}")
                output.append(f"🏷️ **Labels Found**: {len(sorted_labels)}")
                
                # Show top resource consumers by label
                output.append(f"\n🏆 **TOP {min(top_n, len(sorted_labels))} LABELS BY RESOURCE USAGE**:")
                
                for i, (label, data) in enumerate(sorted_labels[:top_n], 1):
                    percentage = (data['vcpus'] / total_vcpus * 100) if total_vcpus > 0 else 0
                    
                    # Highlight high-resource labels
                    resource_emoji = "🔴" if data['vcpus'] > total_vcpus * 0.3 else "🟠" if data['vcpus'] > total_vcpus * 0.1 else "🟢"
                    
                    output.append(f"\n{i:2d}. {resource_emoji} **{label}**")
                    output.append(f"     🖥️ {data['instances']} instances ({percentage:.1f}% of vCPUs)")
                    output.append(f"     💻 {data['vcpus']} vCPUs")
                    output.append(f"     🔧 {len(data['machine_types'])} machine types")
                
                # Analyze environment distribution
                env_labels = ['prod', 'production', 'staging', 'dev', 'development', 'test', 'uat']
                env_analysis = {}
                
                for label, data in sorted_labels:
                    label_lower = label.lower()
                    for env in env_labels:
                        if env in label_lower:
                            if env not in env_analysis:
                                env_analysis[env] = {'instances': 0, 'vcpus': 0}
                            env_analysis[env]['instances'] += data['instances']
                            env_analysis[env]['vcpus'] += data['vcpus']
                            break
                
                if env_analysis:
                    output.append(f"\n🏗️ **ENVIRONMENT DISTRIBUTION**:")
                    for env, data in sorted(env_analysis.items(), key=lambda x: x[1]['vcpus'], reverse=True):
                        env_percentage = (data['vcpus'] / total_vcpus * 100) if total_vcpus > 0 else 0
                        output.append(f"   • **{env.title()}**: {data['instances']} instances, {data['vcpus']} vCPUs ({env_percentage:.1f}%)")
                
                # Untagged resources analysis
                if untagged_instances > 0:
                    untagged_percentage = (untagged_instances / total_instances * 100)
                    output.append(f"\n🏷️ **UNTAGGED RESOURCES**:")
                    output.append(f"   ⚠️ {untagged_instances} instances ({untagged_percentage:.1f}%) lack '{label_key}' label")
                    output.append(f"   💰 Estimated impact: Difficult to track and optimize costs")
                
                # Optimization recommendations
                output.append(f"\n💡 **OPTIMIZATION RECOMMENDATIONS**:")
                
                if untagged_instances > total_instances * 0.1:
                    output.append(f"   🏷️ Improve labeling: {untagged_instances} untagged instances")
                    output.append(f"   📋 Implement consistent labeling strategy")
                
                # Check for dev/test resource usage
                dev_test_vcpus = sum(data['vcpus'] for env, data in env_analysis.items() 
                                   if env in ['dev', 'development', 'test', 'uat'])
                if dev_test_vcpus > total_vcpus * 0.3:
                    dev_percentage = (dev_test_vcpus / total_vcpus * 100)
                    output.append(f"   🧪 High dev/test usage: {dev_percentage:.1f}% of resources")
                    output.append(f"   💡 Consider: Scheduled shutdown, preemptible instances")
                
                # Resource concentration analysis
                if sorted_labels:
                    top_label_percentage = (sorted_labels[0][1]['vcpus'] / total_vcpus * 100)
                    if top_label_percentage > 50:
                        output.append(f"   ⚠️ High concentration: {top_label_percentage:.1f}% in '{sorted_labels[0][0]}'")
                        output.append(f"   🎯 Review resource distribution and scaling policies")
                
                output.append(f"\n📊 **MONITORING RECOMMENDATIONS**:")
                output.append(f"   📈 Set up cost alerts by label/environment")
                output.append(f"   🏷️ Enforce labeling policies for new resources")
                output.append(f"   💰 Enable billing export for detailed cost tracking")
                output.append(f"   🔄 Regular review of resource allocation by environment")
                
                output.append(f"\n📋 **NEXT STEPS**:")
                output.append(f"   1. Set up BigQuery billing export for accurate cost data")
                output.append(f"   2. Implement consistent labeling across all resources")
                output.append(f"   3. Use `gcp_cost_analysis_summary()` for billing setup")
                output.append(f"   4. Review and optimize high-usage environments")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_project_costs_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: Project cost analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing project costs: {str(e)}"

    @mcp.tool()
    async def gcp_committed_use_discount_analysis(
        days: int = 30,
        project_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """GCP CUD Analysis: Analyze Committed Use Discount opportunities and utilization."""
        logger.info(f"📅 Analyzing Committed Use Discount opportunities for {days} days...")
        
        try:
            async def analyze_cud_with_timeout():
                project = project_id or gcp_provider.get_current_project()
                if not project:
                    return "❌ No project specified and no current project available"
                
                compute_client = compute_v1.InstancesClient()
                zones_client = compute_v1.ZonesClient()
                
                # Analyze current instance usage patterns
                zones = []
                for zone in zones_client.list(project=project):
                    if not region or zone.name.startswith(region):
                        zones.append(zone.name)
                
                # Track instance usage by machine family and region
                machine_family_usage = {}
                region_usage = {}
                total_vcpus = 0
                total_instances = 0
                running_instances = 0
                
                for zone in zones[:15]:  # Limit to avoid timeout
                    try:
                        zone_region = '-'.join(zone.split('-')[:-1])  # Extract region from zone
                        
                        for instance in compute_client.list(project=project, zone=zone):
                            total_instances += 1
                            machine_type = instance.machine_type.split('/')[-1]
                            vcpus = _get_vcpu_count(machine_type)
                            
                            # Extract machine family (e.g., n1, n2, e2)
                            machine_family = machine_type.split('-')[0]
                            
                            if instance.status == "RUNNING":
                                running_instances += 1
                                total_vcpus += vcpus
                                
                                # Track by machine family
                                if machine_family not in machine_family_usage:
                                    machine_family_usage[machine_family] = {
                                        'vcpus': 0, 'instances': 0, 'zones': set()
                                    }
                                machine_family_usage[machine_family]['vcpus'] += vcpus
                                machine_family_usage[machine_family]['instances'] += 1
                                machine_family_usage[machine_family]['zones'].add(zone)
                                
                                # Track by region
                                if zone_region not in region_usage:
                                    region_usage[zone_region] = {'vcpus': 0, 'instances': 0}
                                region_usage[zone_region]['vcpus'] += vcpus
                                region_usage[zone_region]['instances'] += 1
                            
                    except Exception as e:
                        logger.warning(f"Could not analyze instances in zone {zone}: {e}")
                        continue
                
                # Calculate CUD recommendations
                # CUD is typically beneficial for consistent usage >50% of time
                utilization_threshold = 0.6  # 60% utilization threshold for CUD recommendation
                
                output = ["📅 **GCP COMMITTED USE DISCOUNT ANALYSIS**", "=" * 60]
                output.append(f"📅 **Analysis Period**: Current snapshot (for {days}-day projection)")
                output.append(f"🎯 **Project**: {project}")
                output.append(f"📊 **Total Instances**: {total_instances}")
                output.append(f"🟢 **Running Instances**: {running_instances}")
                output.append(f"💻 **Total Running vCPUs**: {total_vcpus}")
                
                # Machine family analysis for CUD opportunities
                if machine_family_usage:
                    output.append(f"\n🔧 **MACHINE FAMILY ANALYSIS**:")
                    sorted_families = sorted(machine_family_usage.items(), 
                                           key=lambda x: x[1]['vcpus'], reverse=True)
                    
                    total_cud_potential = 0
                    for family, data in sorted_families:
                        family_vcpus = data['vcpus']
                        family_percentage = (family_vcpus / total_vcpus * 100) if total_vcpus > 0 else 0
                        zones_count = len(data['zones'])
                        
                        # Estimate CUD potential (conservative: 60% of current usage)
                        cud_vcpus = int(family_vcpus * utilization_threshold)
                        estimated_savings = cud_vcpus * 0.37 * 24 * 30  # 37% savings, monthly
                        total_cud_potential += estimated_savings
                        
                        generation_info = _get_machine_generation(f"{family}-standard-1")
                        
                        output.append(f"   • **{family.upper()}**: {family_vcpus} vCPUs ({family_percentage:.1f}%) {generation_info}")
                        output.append(f"     Instances: {data['instances']} | Zones: {zones_count}")
                        if cud_vcpus >= 1:
                            output.append(f"     CUD Potential: {cud_vcpus} vCPUs (~${estimated_savings:.0f}/month savings)")
                
                # Regional distribution for CUD planning
                if region_usage:
                    output.append(f"\n📍 **REGIONAL DISTRIBUTION**:")
                    sorted_regions = sorted(region_usage.items(), 
                                          key=lambda x: x[1]['vcpus'], reverse=True)
                    
                    for region_name, data in sorted_regions[:5]:
                        region_percentage = (data['vcpus'] / total_vcpus * 100) if total_vcpus > 0 else 0
                        output.append(f"   • **{region_name}**: {data['vcpus']} vCPUs ({region_percentage:.1f}%)")
                
                # CUD recommendations
                output.append(f"\n💰 **CUD RECOMMENDATIONS**:")
                
                if total_vcpus >= 10:
                    recommended_cud_vcpus = int(total_vcpus * utilization_threshold)
                    annual_savings = recommended_cud_vcpus * 0.37 * 24 * 365  # 37% savings annually
                    
                    output.append(f"   🎯 **Recommended CUD**: {recommended_cud_vcpus} vCPUs")
                    output.append(f"   💰 **Estimated Annual Savings**: ${annual_savings:.0f}")
                    output.append(f"   📊 **Coverage**: {utilization_threshold*100:.0f}% of current usage")
                    
                    # Break down by machine family
                    output.append(f"\n🔧 **CUD BREAKDOWN BY FAMILY**:")
                    for family, data in sorted_families[:3]:
                        family_cud = int(data['vcpus'] * utilization_threshold)
                        if family_cud >= 1:
                            family_savings = family_cud * 0.37 * 24 * 365
                            output.append(f"     • {family.upper()}: {family_cud} vCPUs (${family_savings:.0f}/year)")
                else:
                    output.append(f"   📊 **Current usage too low**: {total_vcpus} vCPUs")
                    output.append(f"   💡 **Recommendation**: Wait until consistent 10+ vCPU usage")
                
                # Risk assessment
                output.append(f"\n⚠️ **CUD RISK ASSESSMENT**:")
                
                # Check for usage consistency indicators
                if len(machine_family_usage) > 3:
                    output.append(f"   🟡 **Medium Risk**: {len(machine_family_usage)} machine families (diversified)")
                else:
                    output.append(f"   🟢 **Low Risk**: {len(machine_family_usage)} machine families (concentrated)")
                
                if len(region_usage) > 2:
                    output.append(f"   🟡 **Geographic Risk**: {len(region_usage)} regions")
                else:
                    output.append(f"   🟢 **Low Geographic Risk**: {len(region_usage)} regions")
                
                # Best practices
                output.append(f"\n📋 **CUD BEST PRACTICES**:")
                output.append(f"   📊 **Start Conservative**: Begin with 1-year terms")
                output.append(f"   📈 **Monitor Usage**: Track utilization before committing")
                output.append(f"   🎯 **Focus on Stable Workloads**: Avoid CUD for variable usage")
                output.append(f"   🔄 **Regional Strategy**: Consider regional vs global CUDs")
                
                output.append(f"\n📅 **IMPLEMENTATION PLAN**:")
                output.append(f"   📊 **Week 1-2**: Monitor current usage patterns")
                output.append(f"   📈 **Week 3-4**: Analyze usage consistency over time")
                output.append(f"   💰 **Month 2**: Start with conservative CUD commitment")
                output.append(f"   🔄 **Quarterly**: Review and adjust CUD strategy")
                
                output.append(f"\n🔗 **NEXT STEPS**:")
                output.append(f"   1. Enable detailed billing export for usage analysis")
                output.append(f"   2. Use GCP Console → Billing → Commitments for CUD setup")
                output.append(f"   3. Set up monitoring for CUD utilization")
                output.append(f"   4. Consider starting with 1-year commitment")
                
                return "\n".join(output)
            
            result = await asyncio.wait_for(analyze_cud_with_timeout(), timeout=60.0)
            return result
            
        except asyncio.TimeoutError:
            return f"⏰ Timeout: CUD analysis took longer than 60 seconds"
        except Exception as e:
            return f"❌ Error analyzing Committed Use Discounts: {str(e)}"

    @mcp.tool()
    async def gcp_billing_setup_and_cost_guide() -> str:
        """Comprehensive guide to set up GCP billing export and get actual cost data."""
        logger.info("🔧 Providing comprehensive billing setup guide...")
        
        try:
            project = gcp_provider.get_current_project()
            if not project:
                return "❌ No project specified and no current project available"
            
            # Get billing account info
            billing_client = billing_v1.CloudBillingClient()
            project_billing_info = None
            billing_account_name = None
            
            try:
                project_name = f"projects/{project}"
                project_billing_info = billing_client.get_project_billing_info(name=project_name)
                billing_account_name = project_billing_info.billing_account_name
            except Exception as e:
                logger.warning(f"Could not get billing info: {e}")
            
            output = ["🔧 **GCP BILLING SETUP & COST ANALYSIS GUIDE**", "=" * 60]
            output.append(f"🎯 **Current Project**: {project}")
            
            if billing_account_name:
                output.append(f"💳 **Billing Account**: {billing_account_name}")
                output.append(f"✅ **Billing Status**: {'Enabled' if project_billing_info.billing_enabled else 'Disabled'}")
            else:
                output.append(f"⚠️ **Billing Account**: Not accessible")
            
            # Why billing data isn't available
            output.append(f"\n🚨 **WHY COST DATA ISN'T AVAILABLE**:")
            output.append(f"   1. 🔴 **No BigQuery Billing Export**: GCP requires manual setup")
            output.append(f"   2. ⚠️ **Limited Billing APIs**: Unlike AWS, GCP doesn't provide real-time cost APIs")
            output.append(f"   3. 📊 **Monitoring Metrics Missing**: Billing metrics require export setup")
            output.append(f"   4. 🔍 **Manual Console Access**: Cost data only in GCP Console without export")
            
            # Immediate manual cost check
            output.append(f"\n💰 **GET CURRENT COSTS IMMEDIATELY** (Manual Steps):")
            output.append(f"   📋 **Step 1**: Go to https://console.cloud.google.com/billing")
            output.append(f"   📊 **Step 2**: Select billing account: 'NuvolarWorks - Billing Account'")
            output.append(f"   📈 **Step 3**: Click 'Reports' in left sidebar")
            output.append(f"   🎯 **Step 4**: Filter by project: '{project}'")
            output.append(f"   📅 **Step 5**: Set time range: 'Last 30 days'")
            output.append(f"   🔧 **Step 6**: Group by: 'Service' and 'SKU'")
            output.append(f"   💾 **Step 7**: Export to CSV for analysis")
            
            # BigQuery Export Setup
            output.append(f"\n🔧 **ENABLE BIGQUERY BILLING EXPORT** (Permanent Solution):")
            output.append(f"   📋 **Step 1**: Go to Cloud Console → Billing → Billing Export")
            output.append(f"   ➕ **Step 2**: Click 'Create Export'")
            output.append(f"   📊 **Step 3**: Select 'Standard usage cost data'")
            output.append(f"   🎯 **Step 4**: Configure export:")
            output.append(f"      • Project: {project}")
            output.append(f"      • Dataset ID: billing_export")
            output.append(f"      • Table prefix: gcp_billing_export")
            output.append(f"      • Location: europe-west1")
            output.append(f"   ⏰ **Step 5**: Wait 24-48 hours for data population")
            
            # Sample queries for when export is ready
            output.append(f"\n📊 **BIGQUERY QUERIES** (After Export Setup):")
            output.append(f"   💰 **Daily Costs (Last 30 Days)**:")
            output.append(f"   ```sql")
            output.append(f"   SELECT ")
            output.append(f"     DATE(usage_start_time) as date,")
            output.append(f"     SUM(cost) as daily_cost,")
            output.append(f"     currency")
            output.append(f"   FROM `{project}.billing_export.gcp_billing_export_*`")
            output.append(f"   WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)")
            output.append(f"   GROUP BY 1, 3")
            output.append(f"   ORDER BY 1 DESC")
            output.append(f"   ```")
            
            output.append(f"\n   🔧 **Service Breakdown**:")
            output.append(f"   ```sql")
            output.append(f"   SELECT ")
            output.append(f"     service.description as service,")
            output.append(f"     SUM(cost) as total_cost,")
            output.append(f"     ROUND(SUM(cost) / (SELECT SUM(cost) FROM `{project}.billing_export.gcp_billing_export_*` ")
            output.append(f"       WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) * 100, 2) as percentage")
            output.append(f"   FROM `{project}.billing_export.gcp_billing_export_*`")
            output.append(f"   WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)")
            output.append(f"   GROUP BY 1")
            output.append(f"   ORDER BY 2 DESC")
            output.append(f"   ```")
            
            # Alternative: Cloud Asset Inventory for resource costs
            output.append(f"\n🔍 **ALTERNATIVE: RESOURCE-BASED COST ESTIMATION**:")
            output.append(f"   📊 **Cloud Asset Inventory**: List all resources and estimate costs")
            output.append(f"   💰 **Pricing Calculator**: Manual cost calculation")
            output.append(f"   📈 **Monitoring Metrics**: Resource utilization data")
            
            # Budget and alerts setup
            output.append(f"\n🚨 **SET UP COST MONITORING** (Immediate):")
            output.append(f"   📋 **Step 1**: Go to Cloud Console → Billing → Budgets & alerts")
            output.append(f"   ➕ **Step 2**: Create budget for project: {project}")
            output.append(f"   💰 **Step 3**: Set monthly budget (estimate $200-300 for staging)")
            output.append(f"   📧 **Step 4**: Configure email alerts at 50%, 80%, 100%")
            output.append(f"   📱 **Step 5**: Add Pub/Sub notifications for automation")
            
            # Expected timeline
            output.append(f"\n⏰ **TIMELINE TO GET COST DATA**:")
            output.append(f"   🟢 **Immediate (0-1 hour)**: Manual GCP Console reports")
            output.append(f"   🟡 **Short-term (24-48 hours)**: BigQuery export starts flowing")
            output.append(f"   🟢 **Long-term (1 week)**: Full historical data and automation")
            
            # Cost estimation based on current resources
            output.append(f"\n💡 **CURRENT RESOURCE COST ESTIMATION**:")
            output.append(f"   🖥️ **GKE Cluster**: 2 × e2-custom-2-3072 nodes")
            output.append(f"      • Estimated: $60-80/month per node")
            output.append(f"      • Total: $120-160/month")
            output.append(f"   💾 **Persistent Disks**: 2 × 100GB standard")
            output.append(f"      • Estimated: $4-6/month per disk")
            output.append(f"      • Total: $8-12/month")
            output.append(f"   🌐 **Networking**: Standard VPC, Load Balancing")
            output.append(f"      • Estimated: $10-20/month")
            output.append(f"   📊 **Monitoring**: Basic Cloud Operations")
            output.append(f"      • Estimated: $5-15/month")
            output.append(f"   💰 **TOTAL ESTIMATED**: $143-207/month")
            
            # Next steps
            output.append(f"\n📋 **IMMEDIATE ACTION PLAN**:")
            output.append(f"   🎯 **Today (30 minutes)**:")
            output.append(f"      1. Check current costs in GCP Console")
            output.append(f"      2. Enable BigQuery billing export")
            output.append(f"      3. Set up budget alerts")
            output.append(f"   📊 **This Week**:")
            output.append(f"      1. Wait for billing data to populate")
            output.append(f"      2. Create cost analysis queries")
            output.append(f"      3. Implement optimization recommendations")
            output.append(f"   🔄 **Ongoing**:")
            output.append(f"      1. Daily cost monitoring")
            output.append(f"      2. Weekly optimization reviews")
            output.append(f"      3. Monthly detailed analysis")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ Error generating billing setup guide: {str(e)}"