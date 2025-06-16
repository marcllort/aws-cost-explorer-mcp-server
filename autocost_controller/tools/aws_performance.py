"""AWS Performance and Optimization tools for Autocost Controller."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP

from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger


def register_aws_performance_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register AWS performance and optimization tools."""
    
    aws_provider = provider_manager.get_provider("aws")
    if not aws_provider:
        return
    
    @mcp.tool()
    async def aws_performance_ec2_insights(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        instance_ids: Optional[List[str]] = None
    ) -> str:
        """AWS Performance: Get EC2 performance insights with cost correlation and optimization recommendations."""
        logger.info(f"📊 Getting EC2 performance insights for {days} days...")
        
        try:
            # Get EC2 and CloudWatch clients
            ec2_client = aws_provider.get_client("ec2", account_id, region)
            cloudwatch_client = aws_provider.get_client("cloudwatch", account_id, region)
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            # Get EC2 instances
            if instance_ids:
                response = ec2_client.describe_instances(InstanceIds=instance_ids)
            else:
                response = ec2_client.describe_instances()
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] in ['running', 'stopped']:
                        instances.append(instance)
            
            if not instances:
                return "❌ No EC2 instances found in the specified region."
            
            # Analyze each instance
            instance_analysis = []
            total_cost = 0.0
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            for instance in instances[:10]:  # Limit to first 10 instances for performance
                instance_id = instance['InstanceId']
                instance_type = instance['InstanceType']
                state = instance['State']['Name']
                
                # Get instance costs
                try:
                    cost_response = ce_client.get_cost_and_usage(
                        TimePeriod={
                            'Start': start_date.strftime('%Y-%m-%d'),
                            'End': end_date.strftime('%Y-%m-%d')
                        },
                        Granularity='DAILY',
                        Metrics=['BlendedCost'],
                        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
                        Filter={
                            'Dimensions': {
                                'Key': 'RESOURCE_ID',
                                'Values': [instance_id],
                                'MatchOptions': ['EQUALS']
                            }
                        }
                    )
                    
                    instance_cost = 0.0
                    for result in cost_response.get('ResultsByTime', []):
                        for group in result.get('Groups', []):
                            cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                            instance_cost += cost
                    
                    total_cost += instance_cost
                    
                except Exception as e:
                    logger.warning(f"Could not get cost for {instance_id}: {e}")
                    instance_cost = 0.0
                
                # Get CloudWatch metrics for running instances
                metrics = {}
                if state == 'running':
                    try:
                        # CPU Utilization
                        cpu_response = cloudwatch_client.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUUtilization',
                            Dimensions=[
                                {'Name': 'InstanceId', 'Value': instance_id}
                            ],
                            StartTime=start_date,
                            EndTime=end_date,
                            Period=3600,  # 1 hour periods
                            Statistics=['Average', 'Maximum']
                        )
                        
                        if cpu_response['Datapoints']:
                            cpu_avg = sum(dp['Average'] for dp in cpu_response['Datapoints']) / len(cpu_response['Datapoints'])
                            cpu_max = max(dp['Maximum'] for dp in cpu_response['Datapoints'])
                            metrics['cpu'] = {'avg': cpu_avg, 'max': cpu_max}
                        
                        # Network metrics
                        network_in_response = cloudwatch_client.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='NetworkIn',
                            Dimensions=[
                                {'Name': 'InstanceId', 'Value': instance_id}
                            ],
                            StartTime=start_date,
                            EndTime=end_date,
                            Period=3600,
                            Statistics=['Sum']
                        )
                        
                        if network_in_response['Datapoints']:
                            network_in = sum(dp['Sum'] for dp in network_in_response['Datapoints']) / (1024 * 1024)  # Convert to MB
                            metrics['network_in_mb'] = network_in
                        
                    except Exception as e:
                        logger.warning(f"Could not get metrics for {instance_id}: {e}")
                
                # Get instance name from tags
                instance_name = instance_id
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break
                
                instance_analysis.append({
                    'id': instance_id,
                    'name': instance_name,
                    'type': instance_type,
                    'state': state,
                    'cost': instance_cost,
                    'metrics': metrics
                })
            
            # Sort by cost
            instance_analysis.sort(key=lambda x: x['cost'], reverse=True)
            
            output = ["📊 **AWS EC2 PERFORMANCE INSIGHTS**", "=" * 60]
            output.append(f"📅 **Period**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days} days)")
            output.append(f"💰 **Total EC2 Cost**: ${total_cost:.2f}")
            output.append(f"🖥️ **Instances Analyzed**: {len(instance_analysis)}")
            
            output.append("\n🏆 **TOP INSTANCES BY COST**:")
            
            for i, instance in enumerate(instance_analysis[:5], 1):
                cost_per_day = instance['cost'] / days if days > 0 else 0
                output.append(f"\n{i}. **{instance['name']}** ({instance['id']})")
                output.append(f"   💰 Cost: ${instance['cost']:.2f} (${cost_per_day:.2f}/day)")
                output.append(f"   🖥️ Type: {instance['type']}")
                output.append(f"   🔄 State: {instance['state']}")
                
                if instance['metrics']:
                    if 'cpu' in instance['metrics']:
                        cpu_data = instance['metrics']['cpu']
                        output.append(f"   📊 CPU: Avg {cpu_data['avg']:.1f}%, Max {cpu_data['max']:.1f}%")
                        
                        # CPU-based recommendations
                        if cpu_data['avg'] < 10:
                            output.append("   💡 Consider downsizing - very low CPU utilization")
                        elif cpu_data['avg'] > 80:
                            output.append("   ⚠️ Consider upsizing - high CPU utilization")
                    
                    if 'network_in_mb' in instance['metrics']:
                        network_mb = instance['metrics']['network_in_mb']
                        output.append(f"   🌐 Network In: {network_mb:.1f} MB total")
            
            # Overall recommendations
            output.append("\n💡 **OPTIMIZATION RECOMMENDATIONS**:")
            
            # Identify underutilized instances
            underutilized = [i for i in instance_analysis if i['metrics'] and 
                           'cpu' in i['metrics'] and i['metrics']['cpu']['avg'] < 15]
            
            if underutilized:
                output.append(f"🔋 **{len(underutilized)} underutilized instances** (< 15% CPU avg):")
                for instance in underutilized[:3]:
                    output.append(f"   • {instance['name']}: {instance['metrics']['cpu']['avg']:.1f}% CPU avg")
                output.append("   💡 Consider downsizing or using Spot instances")
            
            # Check for stopped instances with costs
            stopped_with_costs = [i for i in instance_analysis if i['state'] == 'stopped' and i['cost'] > 0]
            if stopped_with_costs:
                output.append(f"⏹️ **{len(stopped_with_costs)} stopped instances** still incurring costs:")
                for instance in stopped_with_costs:
                    output.append(f"   • {instance['name']}: ${instance['cost']:.2f}")
                output.append("   💡 Check for attached EBS volumes or Elastic IPs")
            
            # General recommendations
            output.append("\n🚀 **GENERAL OPTIMIZATION TIPS**:")
            output.append("   • Consider Reserved Instances for steady workloads (up to 75% savings)")
            output.append("   • Use Spot Instances for fault-tolerant workloads (up to 90% savings)")
            output.append("   • Migrate to ARM-based Graviton instances for up to 40% better price/performance")
            output.append("   • Implement auto-scaling to match capacity with demand")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error getting EC2 performance insights: {str(e)}")
            return f"❌ Error getting EC2 performance insights: {str(e)}"
    
    @mcp.tool()
    async def get_ecs_performance_insights(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        cluster_names: Optional[List[str]] = None
    ) -> str:
        """Get ECS performance insights with cost correlation and optimization recommendations."""
        logger.info(f"📊 Getting ECS performance insights for {days} days...")
        
        try:
            ecs_client = aws_provider.get_client("ecs", account_id, region)
            cloudwatch_client = aws_provider.get_client("cloudwatch", account_id, region)
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            # Get ECS clusters
            if cluster_names:
                clusters_response = ecs_client.describe_clusters(clusters=cluster_names)
            else:
                clusters_response = ecs_client.list_clusters()
                cluster_arns = clusters_response.get('clusterArns', [])
                if cluster_arns:
                    clusters_response = ecs_client.describe_clusters(clusters=cluster_arns)
                else:
                    return "⚠️ No ECS clusters found"
            
            clusters = clusters_response.get('clusters', [])
            if not clusters:
                return "⚠️ No ECS clusters found"
            
            output = ["📊 **ECS PERFORMANCE INSIGHTS**", "=" * 50]
            output.append(f"📅 **Period**: Last {days} days")
            output.append(f"🐳 **Clusters Analyzed**: {len(clusters)}")
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            total_optimization_potential = 0.0
            
            for cluster in clusters:
                cluster_name = cluster['clusterName']
                
                # Get services in cluster
                services_response = ecs_client.list_services(cluster=cluster_name)
                service_arns = services_response.get('serviceArns', [])
                
                if not service_arns:
                    continue
                
                # Limit services for performance
                service_arns = service_arns[:config.max_services_per_cluster]
                
                services_detail = ecs_client.describe_services(
                    cluster=cluster_name,
                    services=service_arns
                )
                
                output.append(f"\n🐳 **Cluster: {cluster_name}**")
                output.append(f"   📊 Active Services: {len(service_arns)}")
                
                cluster_cost = 0.0
                cluster_recommendations = []
                
                for service in services_detail.get('services', []):
                    service_name = service['serviceName']
                    
                    try:
                        # Get CPU and memory utilization
                        cpu_response = cloudwatch_client.get_metric_statistics(
                            Namespace='AWS/ECS',
                            MetricName='CPUUtilization',
                            Dimensions=[
                                {'Name': 'ServiceName', 'Value': service_name},
                                {'Name': 'ClusterName', 'Value': cluster_name}
                            ],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,
                            Statistics=['Average', 'Maximum']
                        )
                        
                        memory_response = cloudwatch_client.get_metric_statistics(
                            Namespace='AWS/ECS',
                            MetricName='MemoryUtilization',
                            Dimensions=[
                                {'Name': 'ServiceName', 'Value': service_name},
                                {'Name': 'ClusterName', 'Value': cluster_name}
                            ],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=3600,
                            Statistics=['Average', 'Maximum']
                        )
                        
                        cpu_datapoints = cpu_response.get('Datapoints', [])
                        memory_datapoints = memory_response.get('Datapoints', [])
                        
                        avg_cpu = sum(dp['Average'] for dp in cpu_datapoints) / len(cpu_datapoints) if cpu_datapoints else 0
                        max_cpu = max(dp['Maximum'] for dp in cpu_datapoints) if cpu_datapoints else 0
                        avg_memory = sum(dp['Average'] for dp in memory_datapoints) / len(memory_datapoints) if memory_datapoints else 0
                        max_memory = max(dp['Maximum'] for dp in memory_datapoints) if memory_datapoints else 0
                        
                        output.append(f"\n   📦 **{service_name}**")
                        output.append(f"      📊 CPU: {avg_cpu:.1f}% avg, {max_cpu:.1f}% max")
                        output.append(f"      🧠 Memory: {avg_memory:.1f}% avg, {max_memory:.1f}% max")
                        
                        # Generate recommendations
                        service_recommendations = []
                        
                        if avg_cpu < config.cpu_underutilization_threshold:
                            service_recommendations.append("🔄 Consider ARM/Graviton Fargate for 20% cost savings")
                        
                        if avg_memory < config.memory_underutilization_threshold:
                            service_recommendations.append("📉 Memory over-provisioned - consider reducing allocation")
                        
                        if avg_cpu > config.cpu_overutilization_threshold:
                            service_recommendations.append("📈 CPU under-provisioned - consider increasing allocation")
                        
                        if service_recommendations:
                            output.append(f"      💡 Recommendations:")
                            for rec in service_recommendations:
                                output.append(f"         • {rec}")
                        else:
                            output.append(f"      ✅ Well optimized")
                        
                    except Exception as e:
                        output.append(f"\n   📦 **{service_name}**")
                        output.append(f"      ⚠️ Error getting metrics: {str(e)}")
                
                # Get cluster cost
                try:
                    cost_response = ce_client.get_cost_and_usage(
                        TimePeriod={
                            'Start': start_time.strftime('%Y-%m-%d'),
                            'End': end_time.strftime('%Y-%m-%d')
                        },
                        Granularity='DAILY',
                        Metrics=['BlendedCost'],
                        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
                        Filter={
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Elastic Container Service'],
                                'MatchOptions': ['EQUALS']
                            }
                        }
                    )
                    
                    for result in cost_response.get('ResultsByTime', []):
                        for group in result.get('Groups', []):
                            cluster_cost += float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                    
                    daily_cost = cluster_cost / days if days > 0 else 0
                    output.append(f"\n   💰 **Cluster Cost**: ${cluster_cost:.2f} total (${daily_cost:.2f}/day)")
                    
                except Exception as e:
                    output.append(f"\n   ⚠️ Error getting cost data: {str(e)}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error getting ECS performance insights: {str(e)}")
            return f"❌ Error getting ECS performance insights: {str(e)}"
    
    @mcp.tool()
    async def get_cost_optimization_recommendations(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        services: Optional[List[str]] = None
    ) -> str:
        """Get comprehensive cost optimization recommendations across all AWS services."""
        logger.info(f"💡 Generating cost optimization recommendations for {days} days...")
        
        try:
            ce_client = aws_provider.get_client("ce", account_id, region)
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Get cost by service
            service_filter = None
            if services:
                service_filter = {
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
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                ],
                Filter=service_filter
            )
            
            # Process results
            service_costs = {}
            total_cost = 0.0
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    keys = group.get('Keys', [])
                    if len(keys) >= 2:
                        service = keys[0]
                        usage_type = keys[1]
                        cost = float(group.get('Metrics', {}).get('BlendedCost', {}).get('Amount', 0))
                        
                        if service not in service_costs:
                            service_costs[service] = {'total': 0.0, 'usage_types': {}}
                        
                        service_costs[service]['total'] += cost
                        service_costs[service]['usage_types'][usage_type] = service_costs[service]['usage_types'].get(usage_type, 0) + cost
                        total_cost += cost
            
            # Sort services by cost
            sorted_services = sorted(service_costs.items(), key=lambda x: x[1]['total'], reverse=True)
            
            output = ["💡 **COST OPTIMIZATION RECOMMENDATIONS**", "=" * 60]
            output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
            output.append(f"💰 **Total Cost Analyzed**: ${total_cost:.2f}")
            output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
            
            total_potential_savings = 0.0
            recommendations = []
            
            # Analyze top services
            for service, data in sorted_services[:10]:  # Top 10 services
                service_cost = data['total']
                daily_cost = service_cost / days
                
                if service_cost < 1.0:  # Skip very low cost services
                    continue
                
                service_recommendations = []
                service_savings = 0.0
                
                # EC2 specific recommendations
                if 'EC2' in service or 'Elastic Compute Cloud' in service:
                    # ARM migration opportunity
                    arm_savings = daily_cost * (config.arm_savings_percentage / 100)
                    service_savings += arm_savings
                    service_recommendations.append(f"🔄 ARM/Graviton migration: ${arm_savings:.2f}/day")
                    
                    # Spot instance opportunity
                    spot_savings = daily_cost * (config.spot_savings_percentage / 100)
                    service_savings += spot_savings
                    service_recommendations.append(f"💡 Spot instances: ${spot_savings:.2f}/day")
                    
                    # Reserved instance opportunity
                    ri_savings = daily_cost * (config.reserved_instance_savings / 100)
                    service_savings += ri_savings
                    service_recommendations.append(f"📅 Reserved Instances: ${ri_savings:.2f}/day")
                
                # ECS/Fargate specific recommendations
                elif 'Container' in service or 'ECS' in service:
                    # ARM Fargate
                    arm_savings = daily_cost * 0.2  # 20% savings
                    service_savings += arm_savings
                    service_recommendations.append(f"🔄 ARM Fargate: ${arm_savings:.2f}/day")
                    
                    # Right-sizing
                    rightsizing_savings = daily_cost * 0.15  # 15% savings
                    service_savings += rightsizing_savings
                    service_recommendations.append(f"📏 Right-sizing: ${rightsizing_savings:.2f}/day")
                
                # Lambda specific recommendations
                elif 'Lambda' in service:
                    # ARM Lambda
                    arm_savings = daily_cost * 0.2  # 20% savings
                    service_savings += arm_savings
                    service_recommendations.append(f"🔄 ARM Lambda: ${arm_savings:.2f}/day")
                    
                    # Memory optimization
                    memory_savings = daily_cost * 0.1  # 10% savings
                    service_savings += memory_savings
                    service_recommendations.append(f"🧠 Memory optimization: ${memory_savings:.2f}/day")
                
                # RDS specific recommendations
                elif 'RDS' in service or 'Relational Database' in service:
                    # Reserved instances
                    ri_savings = daily_cost * 0.3  # 30% savings
                    service_savings += ri_savings
                    service_recommendations.append(f"📅 RDS Reserved Instances: ${ri_savings:.2f}/day")
                    
                    # Right-sizing
                    rightsizing_savings = daily_cost * 0.15  # 15% savings
                    service_savings += rightsizing_savings
                    service_recommendations.append(f"📏 Instance right-sizing: ${rightsizing_savings:.2f}/day")
                
                # S3 specific recommendations
                elif 'S3' in service or 'Simple Storage' in service:
                    # Intelligent tiering
                    tiering_savings = daily_cost * 0.25  # 25% savings
                    service_savings += tiering_savings
                    service_recommendations.append(f"📦 Intelligent Tiering: ${tiering_savings:.2f}/day")
                    
                    # Lifecycle policies
                    lifecycle_savings = daily_cost * 0.2  # 20% savings
                    service_savings += lifecycle_savings
                    service_recommendations.append(f"🔄 Lifecycle policies: ${lifecycle_savings:.2f}/day")
                
                if service_recommendations:
                    output.append(f"\n💰 **{service}**: ${service_cost:.2f} (${daily_cost:.2f}/day)")
                    for rec in service_recommendations:
                        output.append(f"   • {rec}")
                    total_potential_savings += service_savings
            
            # Summary
            output.append(f"\n🎯 **OPTIMIZATION SUMMARY**")
            output.append(f"💰 **Total Daily Savings Potential**: ${total_potential_savings:.2f}")
            output.append(f"📅 **Monthly Potential**: ${total_potential_savings * 30:.2f}")
            output.append(f"📊 **Annual Potential**: ${total_potential_savings * 365:.2f}")
            output.append(f"📈 **Potential Cost Reduction**: {(total_potential_savings * days / total_cost * 100):.1f}%")
            
            # Quick wins
            output.append(f"\n🚀 **QUICK WINS** (Low effort, high impact):")
            output.append(f"   1. Enable S3 Intelligent Tiering")
            output.append(f"   2. Implement S3 lifecycle policies")
            output.append(f"   3. Review and stop unused EC2 instances")
            output.append(f"   4. Enable ARM/Graviton for compatible workloads")
            output.append(f"   5. Consider Spot instances for fault-tolerant workloads")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {str(e)}")
            return f"❌ Error generating optimization recommendations: {str(e)}" 