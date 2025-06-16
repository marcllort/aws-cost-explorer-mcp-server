"""Data models for Autocost Controller."""

from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# Provider Types
ProviderType = Literal["aws", "gcp", "azure", "datadog"]


class BaseProviderParams(BaseModel):
    """Base parameters for any cloud provider cost analysis."""
    
    provider: ProviderType = Field(description="Cloud provider to analyze")
    days: int = Field(
        default=7,
        description="Number of days to look back for cost data",
        ge=1,
        le=90
    )
    region: Optional[str] = Field(
        default=None,
        description="Provider region to filter by (if None, all regions included)"
    )
    account_id: Optional[str] = Field(        
        description="Account/Project/Subscription ID (if different from default)",
        default=None
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tags to filter by (key-value pairs)"
    )


class AWSParams(BaseProviderParams):
    """Parameters for AWS cost analysis."""
    
    provider: Literal["aws"] = "aws"
    instance_types: Optional[List[str]] = Field(
        default=None,
        description="List of EC2 instance types to filter by"
    )
    usage_types: Optional[List[str]] = Field(
        default=None,
        description="List of usage types to filter by"
    )
    services: Optional[List[str]] = Field(
        default=None,
        description="List of AWS services to filter by"
    )


class GCPParams(BaseProviderParams):
    """Parameters for GCP cost analysis."""
    
    provider: Literal["gcp"] = "gcp"
    project_id: Optional[str] = Field(
        default=None,
        description="GCP Project ID to analyze"
    )
    services: Optional[List[str]] = Field(
        default=None,
        description="List of GCP services to filter by"
    )
    machine_types: Optional[List[str]] = Field(
        default=None,
        description="List of GCP machine types to filter by"
    )


class AzureParams(BaseProviderParams):
    """Parameters for Azure cost analysis."""
    
    provider: Literal["azure"] = "azure"
    subscription_id: Optional[str] = Field(
        default=None,
        description="Azure Subscription ID to analyze"
    )
    resource_groups: Optional[List[str]] = Field(
        default=None,
        description="List of Azure resource groups to filter by"
    )
    services: Optional[List[str]] = Field(
        default=None,
        description="List of Azure services to filter by"
    )


class DatadogParams(BaseProviderParams):
    """Parameters for Datadog cost analysis."""
    
    provider: Literal["datadog"] = "datadog"
    org_id: Optional[str] = Field(
        default=None,
        description="Datadog organization ID"
    )
    products: Optional[List[str]] = Field(
        default=None,
        description="List of Datadog products to analyze"
    )


class FlexibleAnalysisParams(BaseModel):
    """Parameters for flexible multi-provider cost analysis."""
    
    provider: ProviderType = Field(description="Cloud provider to analyze")
    days: int = Field(
        default=7,
        description="Number of days to look back for cost data",
        ge=1,
        le=90
    )
    region: Optional[str] = Field(
        default=None,
        description="Provider region to filter by"
    )
    account_id: Optional[str] = Field(        
        description="Account/Project/Subscription ID",
        default=None
    )
    services: Optional[List[str]] = Field(
        default=None,
        description="List of services to filter by"
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tags to filter by (key-value pairs)"
    )
    resource_types: Optional[List[str]] = Field(
        default=None,
        description="List of resource types to filter by"
    )
    cost_categories: Optional[List[str]] = Field(
        default=None,
        description="List of cost categories to filter by"
    )


class PerformanceParams(BaseModel):
    """Parameters for performance metrics analysis."""
    
    provider: ProviderType = Field(description="Cloud provider for metrics")
    days: int = Field(
        default=7,
        description="Number of days to look back for metrics data",
        ge=1,
        le=90
    )
    region: Optional[str] = Field(
        default=None,
        description="Provider region to get metrics from"
    )
    account_id: Optional[str] = Field(        
        description="Account/Project/Subscription ID for metrics access",
        default=None
    )
    resource_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific resource IDs to analyze"
    )
    metric_types: Optional[List[str]] = Field(
        default=None,
        description="Specific metric types to retrieve"
    )


class OptimizationRecommendation(BaseModel):
    """A single optimization recommendation."""
    
    provider: ProviderType = Field(description="Cloud provider for this recommendation")
    category: str = Field(description="Category of optimization")
    title: str = Field(description="Short title of the recommendation")
    description: str = Field(description="Detailed description of the recommendation")
    potential_savings: float = Field(description="Estimated cost savings per day")
    annual_savings: float = Field(description="Estimated annual cost savings")
    confidence: Literal["High", "Medium", "Low"] = Field(description="Confidence level")
    effort: Literal["Low", "Medium", "High"] = Field(description="Implementation effort")
    risk: Literal["Low", "Medium", "High"] = Field(description="Risk level")
    priority: int = Field(description="Priority ranking (1-10, 10 being highest)")
    implementation_steps: Optional[List[str]] = Field(
        default=None,
        description="Step-by-step implementation guide"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags for categorization"
    )


class ResourceAnalysis(BaseModel):
    """Analysis results for a specific resource."""
    
    provider: ProviderType = Field(description="Cloud provider")
    resource_id: str = Field(description="Unique resource identifier")
    resource_type: str = Field(description="Type of resource")
    resource_name: Optional[str] = Field(default=None, description="Human-readable name")
    current_cost: float = Field(description="Current daily cost")
    utilization_metrics: Dict[str, float] = Field(description="Utilization metrics")
    recommendations: List[OptimizationRecommendation] = Field(description="Optimization recommendations")
    optimization_potential: float = Field(description="Total potential daily savings")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Resource tags")
    last_analyzed: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")


class CostBreakdown(BaseModel):
    """Cost breakdown by various dimensions."""
    
    provider: ProviderType = Field(description="Cloud provider")
    total_cost: float = Field(description="Total cost for the period")
    period_days: int = Field(description="Number of days in the analysis period")
    daily_average: float = Field(description="Average daily cost")
    breakdown_by_service: Dict[str, float] = Field(description="Cost breakdown by service")
    breakdown_by_region: Dict[str, float] = Field(description="Cost breakdown by region")
    breakdown_by_resource_type: Dict[str, float] = Field(description="Cost breakdown by resource type")
    top_cost_drivers: List[Dict[str, Union[str, float]]] = Field(description="Top cost drivers")
    trends: Optional[Dict[str, List[float]]] = Field(default=None, description="Daily cost trends")


class ProviderStatus(BaseModel):
    """Status of a cloud provider integration."""
    
    provider: ProviderType = Field(description="Cloud provider")
    status: Literal["ready", "error", "warning", "disabled"] = Field(description="Provider status")
    is_configured: bool = Field(description="Whether provider is properly configured")
    missing_config: List[str] = Field(description="List of missing configuration items")
    last_check: datetime = Field(default_factory=datetime.now, description="Last status check")
    error_message: Optional[str] = Field(default=None, description="Error message if any")
    capabilities: List[str] = Field(description="Available capabilities for this provider")


class MultiProviderSummary(BaseModel):
    """Summary across multiple cloud providers."""
    
    total_cost: float = Field(description="Total cost across all providers")
    period_days: int = Field(description="Analysis period in days")
    provider_costs: Dict[ProviderType, float] = Field(description="Cost by provider")
    provider_statuses: Dict[ProviderType, ProviderStatus] = Field(description="Status by provider")
    total_recommendations: int = Field(description="Total number of recommendations")
    total_potential_savings: float = Field(description="Total potential daily savings")
    top_recommendations: List[OptimizationRecommendation] = Field(description="Top optimization opportunities")
    analysis_timestamp: datetime = Field(default_factory=datetime.now, description="Analysis timestamp") 