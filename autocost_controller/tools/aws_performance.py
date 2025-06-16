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
        import asyncio
        
        logger.info(f"📊 Getting EC2 performance insights for {days} days...")
        
        try:
            async def get_ec2_insights_with_timeout():
                logger.info(f"🔍 Connecting to AWS services...")
                # Get EC2 and CloudWatch clients
                ec2_client = aws_provider.get_client("ec2", account_id, region)
                cloudwatch_client = aws_provider.get_client("cloudwatch", account_id, region)
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS services")
                
                # Get EC2 instances
                logger.info(f"🔄 Describing EC2 instances...")
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
                
                logger.info(f"📊 Found {len(instances)} instances to analyze")
                
                # Analyze each instance
                instance_analysis = []
                total_cost = 0.0
                
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                for i, instance in enumerate(instances[:10], 1):  # Limit to first 10 instances for performance
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    state = instance['State']['Name']
                    
                    logger.info(f"🔄 Analyzing instance {i}/10: {instance_id}")
                    
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
                            logger.info(f"📊 Getting CloudWatch metrics for {instance_id}")
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
                logger.info(f"✅ Analysis complete - {len(instance_analysis)} instances processed")
                
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
            
            # Use timeout to prevent hanging (90 seconds for this complex operation)
            result = await asyncio.wait_for(get_ec2_insights_with_timeout(), timeout=90.0)
            logger.info(f"✅ Successfully completed EC2 performance insights")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: EC2 performance insights took longer than 90 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error getting EC2 performance insights: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def get_ecs_performance_insights(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None,
        cluster_names: Optional[List[str]] = None
    ) -> str:
        """Get ECS performance insights with cost correlation and optimization recommendations."""
        import asyncio
        
        logger.info(f"📊 Getting ECS performance insights for {days} days...")
        
        try:
            async def get_ecs_insights_with_timeout():
                logger.info(f"🔍 Connecting to AWS services...")
                ecs_client = aws_provider.get_client("ecs", account_id, region)
                cloudwatch_client = aws_provider.get_client("cloudwatch", account_id, region)
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS services")
                
                # Get ECS clusters
                logger.info(f"🔄 Getting ECS clusters...")
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
                
                logger.info(f"📊 Found {len(clusters)} clusters to analyze")
                
                output = ["📊 **ECS PERFORMANCE INSIGHTS**", "=" * 50]
                output.append(f"📅 **Period**: Last {days} days")
                output.append(f"🐳 **Clusters Analyzed**: {len(clusters)}")
                
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=days)
                
                total_optimization_potential = 0.0
                
                for i, cluster in enumerate(clusters, 1):
                    cluster_name = cluster['clusterName']
                    logger.info(f"🔄 Analyzing cluster {i}/{len(clusters)}: {cluster_name}")
                    
                    # Get services in cluster
                    services_response = ecs_client.list_services(cluster=cluster_name)
                    service_arns = services_response.get('serviceArns', [])
                    
                    if not service_arns:
                        logger.info(f"⚠️ No services found in cluster {cluster_name}")
                        continue
                    
                    # Limit services for performance (default to 5 if not configured)
                    max_services = getattr(config, 'max_services_per_cluster', 5)
                    service_arns = service_arns[:max_services]
                    
                    services_detail = ecs_client.describe_services(
                        cluster=cluster_name,
                        services=service_arns
                    )
                    
                    output.append(f"\n🐳 **Cluster: {cluster_name}**")
                    output.append(f"   📊 Active Services: {len(service_arns)}")
                    
                    cluster_cost = 0.0
                    cluster_recommendations = []
                    
                    for j, service in enumerate(services_detail.get('services', []), 1):
                        service_name = service['serviceName']
                        logger.info(f"📊 Getting metrics for service {j}/{len(service_arns)}: {service_name}")
                        
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
                            
                            # Generate recommendations using configurable thresholds
                            service_recommendations = []
                            cpu_under_threshold = getattr(config, 'cpu_underutilization_threshold', 30)
                            memory_under_threshold = getattr(config, 'memory_underutilization_threshold', 50)
                            cpu_over_threshold = getattr(config, 'cpu_overutilization_threshold', 80)
                            
                            if avg_cpu < cpu_under_threshold:
                                service_recommendations.append("🔄 Consider ARM/Graviton Fargate for 20% cost savings")
                            
                            if avg_memory < memory_under_threshold:
                                service_recommendations.append("📉 Memory over-provisioned - consider reducing allocation")
                            
                            if avg_cpu > cpu_over_threshold:
                                service_recommendations.append("📈 CPU under-provisioned - consider increasing allocation")
                            
                            if service_recommendations:
                                output.append(f"      💡 Recommendations:")
                                for rec in service_recommendations:
                                    output.append(f"         • {rec}")
                            else:
                                output.append(f"      ✅ Well optimized")
                            
                        except Exception as e:
                            output.append(f"\n   📦 **{service_name}**")
                            output.append(f"      ⚠️ Error getting metrics: {str(e)[:50]}")
                    
                    # Get cluster cost
                    try:
                        logger.info(f"💰 Getting cost data for cluster {cluster_name}")
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
                        output.append(f"\n   ⚠️ Error getting cost data: {str(e)[:50]}")
                
                logger.info(f"✅ ECS analysis complete")
                return "\n".join(output)
            
            # Use timeout to prevent hanging (60 seconds for ECS analysis)
            result = await asyncio.wait_for(get_ecs_insights_with_timeout(), timeout=60.0)
            logger.info(f"✅ Successfully completed ECS performance insights")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: ECS performance insights took longer than 60 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error getting ECS performance insights: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    @mcp.tool()
    async def get_cost_optimization_recommendations(
        days: int = 7,
        account_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """Get comprehensive cost optimization recommendations across all AWS services."""
        import asyncio
        
        logger.info(f"💡 Generating cost optimization recommendations for {days} days...")
        
        try:
            async def get_recommendations_with_timeout():
                logger.info(f"🔍 Connecting to AWS Cost Explorer...")
                ce_client = aws_provider.get_client("ce", account_id, region)
                logger.info(f"✅ Connected to AWS Cost Explorer")
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)
                logger.info(f"📅 Querying period: {start_date} to {end_date}")
                
                logger.info(f"🔄 Making API call for cost data...")
                # Simplified API call without complex filters that cause validation errors
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
                    ]
                    # Removed Filter parameter that was causing validation issues
                )
                logger.info(f"✅ API call completed successfully")
                
                # Process results
                service_costs = {}
                total_cost = 0.0
                
                logger.info(f"🔄 Processing results...")
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
                logger.info(f"📊 Analyzed {len(sorted_services)} services with total cost: ${total_cost:.2f}")
                
                output = ["💡 **COST OPTIMIZATION RECOMMENDATIONS**", "=" * 60]
                output.append(f"📅 **Period**: {start_date} to {end_date} ({days} days)")
                output.append(f"💰 **Total Cost Analyzed**: ${total_cost:.2f}")
                output.append(f"📈 **Daily Average**: ${total_cost/days:.2f}")
                
                total_potential_savings = 0.0
                
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
                        # ARM migration opportunity (20% savings)
                        arm_savings = daily_cost * 0.2
                        service_savings += arm_savings
                        service_recommendations.append(f"🔄 ARM/Graviton migration: ${arm_savings:.2f}/day")
                        
                        # Spot instance opportunity (70% savings for applicable workloads)
                        spot_savings = daily_cost * 0.7
                        service_savings += spot_savings
                        service_recommendations.append(f"💡 Spot instances: ${spot_savings:.2f}/day")
                        
                        # Reserved instance opportunity (30% savings)
                        ri_savings = daily_cost * 0.3
                        service_savings += ri_savings
                        service_recommendations.append(f"📅 Reserved Instances: ${ri_savings:.2f}/day")
                    
                    # ECS/Fargate specific recommendations
                    elif 'Container' in service or 'ECS' in service:
                        # ARM Fargate (20% savings)
                        arm_savings = daily_cost * 0.2
                        service_savings += arm_savings
                        service_recommendations.append(f"🔄 ARM Fargate: ${arm_savings:.2f}/day")
                        
                        # Right-sizing (15% savings)
                        rightsizing_savings = daily_cost * 0.15
                        service_savings += rightsizing_savings
                        service_recommendations.append(f"📏 Right-sizing: ${rightsizing_savings:.2f}/day")
                    
                    # Lambda specific recommendations
                    elif 'Lambda' in service:
                        # ARM Lambda (20% savings)
                        arm_savings = daily_cost * 0.2
                        service_savings += arm_savings
                        service_recommendations.append(f"🔄 ARM Lambda: ${arm_savings:.2f}/day")
                        
                        # Memory optimization (10% savings)
                        memory_savings = daily_cost * 0.1
                        service_savings += memory_savings
                        service_recommendations.append(f"🧠 Memory optimization: ${memory_savings:.2f}/day")
                    
                    # RDS specific recommendations
                    elif 'RDS' in service or 'Relational Database' in service:
                        # Reserved instances (30% savings)
                        ri_savings = daily_cost * 0.3
                        service_savings += ri_savings
                        service_recommendations.append(f"📅 RDS Reserved Instances: ${ri_savings:.2f}/day")
                        
                        # Right-sizing (15% savings)
                        rightsizing_savings = daily_cost * 0.15
                        service_savings += rightsizing_savings
                        service_recommendations.append(f"📏 Instance right-sizing: ${rightsizing_savings:.2f}/day")
                    
                    # S3 specific recommendations
                    elif 'S3' in service or 'Simple Storage' in service:
                        # Intelligent tiering (25% savings)
                        tiering_savings = daily_cost * 0.25
                        service_savings += tiering_savings
                        service_recommendations.append(f"📦 Intelligent Tiering: ${tiering_savings:.2f}/day")
                        
                        # Lifecycle policies (20% savings)
                        lifecycle_savings = daily_cost * 0.2
                        service_savings += lifecycle_savings
                        service_recommendations.append(f"🔄 Lifecycle policies: ${lifecycle_savings:.2f}/day")
                    
                    # CloudWatch specific recommendations
                    elif 'CloudWatch' in service:
                        # Log retention optimization (30% savings)
                        log_savings = daily_cost * 0.3
                        service_savings += log_savings
                        service_recommendations.append(f"📝 Optimize log retention: ${log_savings:.2f}/day")
                    
                    # NAT Gateway recommendations
                    elif 'NAT' in service:
                        # NAT instance alternative (50% savings)
                        nat_savings = daily_cost * 0.5
                        service_savings += nat_savings
                        service_recommendations.append(f"🌐 Consider NAT instances: ${nat_savings:.2f}/day")
                    
                    if service_recommendations:
                        # Simplify service name
                        simple_name = service
                        if service.startswith('Amazon '):
                            simple_name = service[7:]
                        elif service.startswith('AWS '):
                            simple_name = service[4:]
                        
                        output.append(f"\n💰 **{simple_name}**: ${service_cost:.2f} (${daily_cost:.2f}/day)")
                        for rec in service_recommendations:
                            output.append(f"   • {rec}")
                        total_potential_savings += service_savings
                
                # Summary
                output.append(f"\n🎯 **OPTIMIZATION SUMMARY**")
                output.append(f"💰 **Total Daily Savings Potential**: ${total_potential_savings:.2f}")
                output.append(f"📅 **Monthly Potential**: ${total_potential_savings * 30:.2f}")
                output.append(f"📊 **Annual Potential**: ${total_potential_savings * 365:.2f}")
                
                if total_cost > 0:
                    reduction_percentage = (total_potential_savings * days / total_cost * 100)
                    output.append(f"📈 **Potential Cost Reduction**: {reduction_percentage:.1f}%")
                
                # Quick wins
                output.append(f"\n🚀 **QUICK WINS** (Low effort, high impact):")
                output.append(f"   1. Enable S3 Intelligent Tiering")
                output.append(f"   2. Implement S3 lifecycle policies")
                output.append(f"   3. Review and stop unused EC2 instances")
                output.append(f"   4. Enable ARM/Graviton for compatible workloads")
                output.append(f"   5. Consider Spot instances for fault-tolerant workloads")
                output.append(f"   6. Optimize CloudWatch log retention periods")
                output.append(f"   7. Purchase Reserved Instances for steady workloads")
                
                # Implementation tips
                output.append(f"\n💡 **IMPLEMENTATION TIPS**:")
                output.append(f"   • Start with services representing >10% of total cost")
                output.append(f"   • Test ARM workloads in development first")
                output.append(f"   • Use AWS Cost Explorer for detailed right-sizing recommendations")
                output.append(f"   • Monitor Reserved Instance utilization regularly")
                output.append(f"   • Set up cost alerts for budget tracking")
                
                return "\n".join(output)
            
            # Use timeout to prevent hanging (60 seconds for this complex analysis)
            result = await asyncio.wait_for(get_recommendations_with_timeout(), timeout=60.0)
            logger.info(f"✅ Successfully completed cost optimization analysis")
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ Timeout: Cost optimization analysis took longer than 60 seconds"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error generating optimization recommendations: {str(e)}"
            logger.error(error_msg)
            return error_msg 