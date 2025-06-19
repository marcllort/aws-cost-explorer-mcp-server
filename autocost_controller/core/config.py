"""Configuration management for Autocost Controller."""

import os
from typing import Dict, List, Optional, Set
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration settings for the multi-cloud cost controller."""
    
    def __init__(self) -> None:
        # Load environment variables from .env file if it exists
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
        
        # Core MCP settings
        self.mcp_transport = os.environ.get('MCP_TRANSPORT', 'stdio')
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO')
        
        # Provider enablement
        self.enabled_providers = self._parse_enabled_providers()
        
        # AWS Configuration
        self.aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        self.aws_cross_account_role = os.environ.get('AWS_CROSS_ACCOUNT_ROLE_NAME', 'AutocostCrossAccount')
        self.aws_profile = os.environ.get('AWS_PROFILE')
        
        # GCP Configuration
        self.gcp_project_id = os.environ.get('GCP_PROJECT_ID')
        self.gcp_credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        self.gcp_billing_account = os.environ.get('GCP_BILLING_ACCOUNT_ID')
        
        # Azure Configuration
        self.azure_subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        self.azure_tenant_id = os.environ.get('AZURE_TENANT_ID')
        self.azure_client_id = os.environ.get('AZURE_CLIENT_ID')
        self.azure_client_secret = os.environ.get('AZURE_CLIENT_SECRET')
        
        # DataDog Configuration
        self.datadog_api_key = os.environ.get('DATADOG_API_KEY')
        self.datadog_app_key = os.environ.get('DATADOG_APP_KEY')
        self.datadog_site = os.environ.get('DATADOG_SITE', 'datadoghq.com')
        
        # Performance settings
        self.max_instances_per_analysis = int(os.environ.get('MAX_INSTANCES_PER_ANALYSIS', '10'))
        self.max_services_per_cluster = int(os.environ.get('MAX_SERVICES_PER_CLUSTER', '5'))
        self.default_analysis_days = int(os.environ.get('DEFAULT_ANALYSIS_DAYS', '7'))
        self.max_concurrent_requests = int(os.environ.get('MAX_CONCURRENT_REQUESTS', '5'))
        
        # Cost optimization thresholds
        self.cpu_underutilization_threshold = float(os.environ.get('CPU_UNDERUTILIZATION_THRESHOLD', '10.0'))
        self.cpu_overutilization_threshold = float(os.environ.get('CPU_OVERUTILIZATION_THRESHOLD', '80.0'))
        self.memory_underutilization_threshold = float(os.environ.get('MEMORY_UNDERUTILIZATION_THRESHOLD', '30.0'))
        self.memory_overutilization_threshold = float(os.environ.get('MEMORY_OVERUTILIZATION_THRESHOLD', '85.0'))
        
        # Savings estimates
        self.arm_savings_percentage = float(os.environ.get('ARM_SAVINGS_PERCENTAGE', '20.0'))
        self.spot_savings_percentage = float(os.environ.get('SPOT_SAVINGS_PERCENTAGE', '50.0'))
        self.reserved_instance_savings = float(os.environ.get('RESERVED_INSTANCE_SAVINGS', '30.0'))
        
        # Custom tools enablement (enabled by default)
        self.enable_custom_tools = os.environ.get('AUTOCOST_ENABLE_CUSTOM_TOOLS', 'true').lower() == 'true'
    
    def _parse_enabled_providers(self) -> Set[str]:
        """Parse enabled providers from environment variable."""
        providers_str = os.environ.get('AUTOCOST_PROVIDERS', os.environ.get('ENABLED_PROVIDERS', 'aws'))
        return set(provider.strip().lower() for provider in providers_str.split(','))
    
    @property
    def is_stdio_transport(self) -> bool:
        """Check if using stdio transport."""
        return self.mcp_transport.lower() == 'stdio'
    
    @property
    def is_sse_transport(self) -> bool:
        """Check if using SSE transport."""
        return self.mcp_transport.lower() == 'sse'
    
    def validate_provider_config(self, provider: str) -> Dict[str, bool]:
        """Validate configuration for a specific provider."""
        validation = {}
        
        if provider == 'aws':
            validation['aws_region'] = bool(self.aws_region)
            validation['aws_credentials'] = self._check_aws_credentials()
            
        elif provider == 'gcp':
            validation['gcp_project_id'] = bool(self.gcp_project_id)
            validation['gcp_credentials'] = bool(self.gcp_credentials_path) or self._check_gcp_default_credentials()
            
        elif provider == 'azure':
            validation['azure_subscription_id'] = bool(self.azure_subscription_id)
            validation['azure_credentials'] = self._check_azure_credentials()
            
        elif provider == 'datadog':
            validation['datadog_api_key'] = bool(self.datadog_api_key)
            validation['datadog_app_key'] = bool(self.datadog_app_key)
        
        return validation
    
    def _check_aws_credentials(self) -> bool:
        """Check if AWS credentials are available."""
        try:
            import boto3
            boto3.client('sts').get_caller_identity()
            return True
        except Exception:
            return False
    
    def _check_gcp_default_credentials(self) -> bool:
        """Check if GCP default credentials are available."""
        try:
            from google.auth import default
            default()
            return True
        except Exception:
            return False
    
    def _check_azure_credentials(self) -> bool:
        """Check if Azure credentials are available."""
        return bool(self.azure_tenant_id and (
            (self.azure_client_id and self.azure_client_secret) or
            os.environ.get('AZURE_CLI_CREDENTIALS')
        ))
    
    def get_missing_config(self) -> Dict[str, List[str]]:
        """Get missing configuration for enabled providers."""
        missing = {}
        
        for provider in self.enabled_providers:
            validation = self.validate_provider_config(provider)
            missing_items = [key for key, valid in validation.items() if not valid]
            if missing_items:
                missing[provider] = missing_items
        
        return missing
    
    def is_provider_ready(self, provider: str) -> bool:
        """Check if a provider is properly configured."""
        validation = self.validate_provider_config(provider)
        return all(validation.values())
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary for logging."""
        return {
            'enabled_providers': list(self.enabled_providers),
            'mcp_transport': self.mcp_transport,
            'log_level': self.log_level,
            'aws_region': self.aws_region,
            'gcp_project_id': self.gcp_project_id,
            'azure_subscription_id': self.azure_subscription_id,
            'performance_settings': {
                'max_instances_per_analysis': self.max_instances_per_analysis,
                'max_services_per_cluster': self.max_services_per_cluster,
                'default_analysis_days': self.default_analysis_days,
            }
        } 