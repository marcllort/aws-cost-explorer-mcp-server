"""GCP performance analysis tools for Autocost Controller."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from google.cloud import monitoring_v3
from google.cloud import container_v1
from google.cloud import compute_v1

from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger


def register_gcp_performance_tools(mcp, provider_manager: ProviderManager, 
                                 config: Config, logger: AutocostLogger) -> None:
    """Register GCP performance analysis tools."""
    
    gcp_provider = provider_manager.get_provider("gcp")
    if not gcp_provider:
        logger.warning("GCP provider not available, skipping tools registration")
        return

    @mcp.tool()
    async def gcp_performance_compute_insights(
        days: int = 7,
        instance_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """GCP Performance: Get Compute Engine performance insights with cost correlation."""
        logger.info(f"🔍 Analyzing Compute Engine performance for {days} days...")
        
        try:
            monitoring_client = gcp_provider.get_client('monitoring')
            compute_client = gcp_provider.get_client('compute')
            
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # Define metrics to collect
            metrics = [
                'compute.googleapis.com/instance/cpu/utilization',
                'compute.googleapis.com/instance/memory/utilization',
                'compute.googleapis.com/instance/disk/read_bytes_count',
                'compute.googleapis.com/instance/disk/write_bytes_count',
                'compute.googleapis.com/instance/network/received_bytes_count',
                'compute.googleapis.com/instance/network/sent_bytes_count'
            ]
            
            # Collect metrics for each instance
            instance_metrics = {}
            for instance_id in (instance_ids or []):
                instance_data = {}
                for metric in metrics:
                    query = monitoring_client.query_time_series(
                        name=f"projects/{project_id}",
                        filter=f'metric.type = "{metric}" AND resource.labels.instance_id = "{instance_id}"',
                        interval=monitoring_v3.TimeInterval(
                            start_time=start_time,
                            end_time=end_time
                        ),
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                    )
                    
                    # Process time series data
                    values = []
                    for series in query:
                        for point in series.points:
                            values.append(point.value.double_value)
                    
                    if values:
                        instance_data[metric] = {
                            'avg': sum(values) / len(values),
                            'max': max(values),
                            'min': min(values)
                        }
                
                instance_metrics[instance_id] = instance_data
            
            # Generate analysis
            analysis = [
                "🖥️ **COMPUTE ENGINE PERFORMANCE ANALYSIS**",
                "=" * 60,
                f"📅 Analysis Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}",
                ""
            ]
            
            for instance_id, metrics in instance_metrics.items():
                analysis.extend([
                    f"📊 **Instance: {instance_id}**",
                    "Performance Metrics:",
                    f"- CPU Utilization: {metrics.get('compute.googleapis.com/instance/cpu/utilization', {}).get('avg', 0)*100:.1f}% avg",
                    f"  Peak: {metrics.get('compute.googleapis.com/instance/cpu/utilization', {}).get('max', 0)*100:.1f}%",
                    f"- Memory Utilization: {metrics.get('compute.googleapis.com/instance/memory/utilization', {}).get('avg', 0)*100:.1f}% avg",
                    f"  Peak: {metrics.get('compute.googleapis.com/instance/memory/utilization', {}).get('max', 0)*100:.1f}%",
                    "",
                    "I/O Metrics:",
                    f"- Disk Read: {metrics.get('compute.googleapis.com/instance/disk/read_bytes_count', {}).get('avg', 0)/1024/1024:.1f} MB/s avg",
                    f"- Disk Write: {metrics.get('compute.googleapis.com/instance/disk/write_bytes_count', {}).get('avg', 0)/1024/1024:.1f} MB/s avg",
                    f"- Network In: {metrics.get('compute.googleapis.com/instance/network/received_bytes_count', {}).get('avg', 0)/1024/1024:.1f} MB/s avg",
                    f"- Network Out: {metrics.get('compute.googleapis.com/instance/network/sent_bytes_count', {}).get('avg', 0)/1024/1024:.1f} MB/s avg",
                    ""
                ])
                
                # Add optimization recommendations
                cpu_util = metrics.get('compute.googleapis.com/instance/cpu/utilization', {}).get('avg', 0)
                mem_util = metrics.get('compute.googleapis.com/instance/memory/utilization', {}).get('avg', 0)
                
                if cpu_util < 0.3 and mem_util < 0.3:
                    analysis.extend([
                        "💡 **Optimization Opportunities**:",
                        "- Consider downsizing instance due to low resource utilization",
                        "- Evaluate using a smaller machine type to reduce costs",
                        "- Monitor workload patterns for potential consolidation"
                    ])
                elif cpu_util > 0.8 or mem_util > 0.8:
                    analysis.extend([
                        "⚠️ **Performance Alerts**:",
                        "- High resource utilization detected",
                        "- Consider upgrading instance size",
                        "- Evaluate workload distribution"
                    ])
            
            return "\n".join(analysis)
            
        except Exception as e:
            logger.error(f"Failed to analyze Compute Engine performance: {str(e)}", "gcp")
            return f"Error analyzing Compute Engine performance: {str(e)}"

    @mcp.tool()
    async def gcp_performance_gke_insights(
        days: int = 7,
        cluster_names: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """Get GKE performance insights with cost correlation and optimization recommendations."""
        logger.info(f"🔍 Analyzing GKE performance for {days} days...")
        
        try:
            monitoring_client = gcp_provider.get_client('monitoring')
            container_client = gcp_provider.get_client('container')
            
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # Define metrics to collect
            metrics = [
                'kubernetes.io/container/cpu/core_usage_time',
                'kubernetes.io/container/memory/used_bytes',
                'kubernetes.io/pod/network/received_bytes_count',
                'kubernetes.io/pod/network/sent_bytes_count',
                'kubernetes.io/node/cpu/allocatable_utilization'
            ]
            
            # Collect metrics for each cluster
            cluster_metrics = {}
            for cluster_name in (cluster_names or []):
                cluster_data = {}
                for metric in metrics:
                    query = monitoring_client.query_time_series(
                        name=f"projects/{project_id}",
                        filter=f'metric.type = "{metric}" AND resource.labels.cluster_name = "{cluster_name}"',
                        interval=monitoring_v3.TimeInterval(
                            start_time=start_time,
                            end_time=end_time
                        ),
                        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
                    )
                    
                    # Process time series data
                    values = []
                    for series in query:
                        for point in series.points:
                            values.append(point.value.double_value)
                    
                    if values:
                        cluster_data[metric] = {
                            'avg': sum(values) / len(values),
                            'max': max(values),
                            'min': min(values)
                        }
                
                cluster_metrics[cluster_name] = cluster_data
            
            # Generate analysis
            analysis = [
                "🎯 **GKE PERFORMANCE ANALYSIS**",
                "=" * 60,
                f"📅 Analysis Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}",
                ""
            ]
            
            for cluster_name, metrics in cluster_metrics.items():
                analysis.extend([
                    f"📊 **Cluster: {cluster_name}**",
                    "Resource Utilization:",
                    f"- Node CPU Utilization: {metrics.get('kubernetes.io/node/cpu/allocatable_utilization', {}).get('avg', 0)*100:.1f}% avg",
                    f"  Peak: {metrics.get('kubernetes.io/node/cpu/allocatable_utilization', {}).get('max', 0)*100:.1f}%",
                    f"- Container CPU Usage: {metrics.get('kubernetes.io/container/cpu/core_usage_time', {}).get('avg', 0):.1f} core-seconds avg",
                    f"- Container Memory Usage: {metrics.get('kubernetes.io/container/memory/used_bytes', {}).get('avg', 0)/1024/1024/1024:.1f} GB avg",
                    "",
                    "Network Metrics:",
                    f"- Pod Network In: {metrics.get('kubernetes.io/pod/network/received_bytes_count', {}).get('avg', 0)/1024/1024:.1f} MB/s avg",
                    f"- Pod Network Out: {metrics.get('kubernetes.io/pod/network/sent_bytes_count', {}).get('avg', 0)/1024/1024:.1f} MB/s avg",
                    ""
                ])
                
                # Add optimization recommendations
                node_cpu_util = metrics.get('kubernetes.io/node/cpu/allocatable_utilization', {}).get('avg', 0)
                
                if node_cpu_util < 0.4:
                    analysis.extend([
                        "💡 **Optimization Opportunities**:",
                        "- Consider reducing node pool size",
                        "- Evaluate pod resource requests/limits",
                        "- Implement horizontal pod autoscaling",
                        "- Review node autoscaling configuration"
                    ])
                elif node_cpu_util > 0.8:
                    analysis.extend([
                        "⚠️ **Performance Alerts**:",
                        "- High node utilization detected",
                        "- Review node autoscaling settings",
                        "- Consider adding node capacity",
                        "- Evaluate pod scheduling and affinity rules"
                    ])
                
                analysis.append("")
            
            return "\n".join(analysis)
            
        except Exception as e:
            logger.error(f"Failed to analyze GKE performance: {str(e)}", "gcp")
            return f"Error analyzing GKE performance: {str(e)}"

    @mcp.tool()
    async def gcp_get_cost_optimization_recommendations(
        days: int = 7,
        project_id: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """Get comprehensive cost optimization recommendations across all GCP services."""
        logger.info(f"🔍 Generating cost optimization recommendations...")
        
        try:
            monitoring_client = gcp_provider.get_client('monitoring')
            compute_client = gcp_provider.get_client('compute')
            container_client = gcp_provider.get_client('container')
            
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # Collect various metrics
            metrics = {
                'compute': [
                    'compute.googleapis.com/instance/cpu/utilization',
                    'compute.googleapis.com/instance/memory/utilization'
                ],
                'gke': [
                    'kubernetes.io/node/cpu/allocatable_utilization',
                    'kubernetes.io/container/memory/limit_utilization'
                ]
            }
            
            recommendations = [
                "🎯 **GCP COST OPTIMIZATION RECOMMENDATIONS**",
                "=" * 60,
                f"📅 Analysis Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}",
                ""
            ]
            
            # Compute Engine recommendations
            recommendations.extend([
                "💻 **Compute Engine Optimization**:",
                "1. Instance Right-sizing:",
                "   - Review instances with consistently low CPU/memory utilization",
                "   - Consider using custom machine types for specific workloads",
                "   - Implement instance scheduling for non-24/7 workloads",
                "",
                "2. Disk Optimization:",
                "   - Delete unattached persistent disks",
                "   - Consider switching to balanced persistent disks",
                "   - Use snapshot scheduling for backup cost optimization",
                "",
                "3. Network Optimization:",
                "   - Review and optimize Cloud NAT usage",
                "   - Use Cloud CDN for content delivery",
                "   - Optimize egress traffic patterns",
                ""
            ])
            
            # GKE recommendations
            recommendations.extend([
                "🎯 **GKE Optimization**:",
                "1. Cluster Configuration:",
                "   - Use node auto-provisioning",
                "   - Implement horizontal pod autoscaling",
                "   - Configure cluster autoscaling appropriately",
                "",
                "2. Workload Optimization:",
                "   - Set appropriate resource requests/limits",
                "   - Use pod disruption budgets",
                "   - Implement multi-tenant clusters where appropriate",
                "",
                "3. Cost Controls:",
                "   - Use preemptible nodes for suitable workloads",
                "   - Implement pod priority classes",
                "   - Monitor and optimize container image sizes",
                ""
            ])
            
            # Storage recommendations
            recommendations.extend([
                "💾 **Storage Optimization**:",
                "1. Object Storage:",
                "   - Use appropriate storage classes",
                "   - Implement lifecycle policies",
                "   - Use signed URLs for secure access",
                "",
                "2. Database Optimization:",
                "   - Right-size database instances",
                "   - Use committed use discounts",
                "   - Implement proper backup retention",
                ""
            ])
            
            # Billing recommendations
            recommendations.extend([
                "💰 **Billing Optimization**:",
                "1. Committed Use Discounts:",
                "   - Analyze stable workload patterns",
                "   - Consider 1-year or 3-year commitments",
                "   - Monitor commitment utilization",
                "",
                "2. Budget Controls:",
                "   - Set up billing alerts",
                "   - Implement project quotas",
                "   - Use labels for cost allocation",
                "",
                "3. Resource Organization:",
                "   - Implement proper resource hierarchy",
                "   - Use folders for billing segregation",
                "   - Regular cleanup of unused resources"
            ])
            
            return "\n".join(recommendations)
            
        except Exception as e:
            logger.error(f"Failed to generate optimization recommendations: {str(e)}", "gcp")
            return f"Error generating optimization recommendations: {str(e)}" 