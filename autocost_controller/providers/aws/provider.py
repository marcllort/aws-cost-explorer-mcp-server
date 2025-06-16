"""AWS provider implementation for Autocost Controller."""

import boto3
from typing import List, Optional
from datetime import datetime

from ...core.provider_manager import BaseProvider
from ...core.config import Config
from ...core.logger import AutocostLogger
from ...core.models import ProviderType, ProviderStatus


class AWSProvider(BaseProvider):
    """AWS cloud provider implementation."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        super().__init__(config, logger)
        self._clients = {}
    
    def get_provider_name(self) -> ProviderType:
        """Return the provider name."""
        return "aws"
    
    def validate_configuration(self) -> ProviderStatus:
        """Validate AWS configuration and return status."""
        try:
            # Check AWS credentials
            sts_client = boto3.client('sts')
            identity = sts_client.get_caller_identity()
            
            capabilities = [
                "cost_analysis",
                "performance_metrics", 
                "optimization_recommendations",
                "dimension_discovery",
                "tag_analysis",
                "cross_account_access"
            ]
            
            return ProviderStatus(
                provider="aws",
                status="ready",
                is_configured=True,
                missing_config=[],
                capabilities=capabilities,
                last_check=datetime.now()
            )
            
        except Exception as e:
            missing_config = []
            if "credentials" in str(e).lower():
                missing_config.append("aws_credentials")
            if "region" in str(e).lower():
                missing_config.append("aws_region")
            
            return ProviderStatus(
                provider="aws",
                status="error",
                is_configured=False,
                missing_config=missing_config,
                capabilities=[],
                error_message=str(e),
                last_check=datetime.now()
            )
    
    def get_capabilities(self) -> List[str]:
        """Return list of supported capabilities."""
        return [
            "cost_analysis",
            "performance_metrics", 
            "optimization_recommendations",
            "dimension_discovery",
            "tag_analysis",
            "cross_account_access",
            "ec2_analysis",
            "ecs_analysis",
            "lambda_analysis",
            "rds_analysis",
            "s3_analysis"
        ]
    
    async def test_connection(self) -> bool:
        """Test connection to AWS."""
        try:
            # Test Cost Explorer access
            ce_client = self.get_client("ce")
            
            # Simple test call
            ce_client.get_dimension_values(
                TimePeriod={
                    'Start': '2024-01-01',
                    'End': '2024-01-02'
                },
                Dimension='SERVICE',
                Context='COST_AND_USAGE',
                MaxResults=1
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"AWS connection test failed: {str(e)}", "aws")
            return False
    
    def get_client(self, service: str, account_id: Optional[str] = None, region: Optional[str] = None):
        """Get AWS client with optional cross-account access."""
        region = region or self.config.aws_region
        
        # Create cache key
        cache_key = f"{service}_{account_id or 'default'}_{region}"
        
        if cache_key in self._clients:
            return self._clients[cache_key]
        
        try:
            current_account = boto3.client('sts').get_caller_identity()['Account']
            
            if account_id and current_account != account_id:
                client = self._create_cross_account_client(service, account_id, region)
            else:
                client = self._create_standard_client(service, region)
            
            # Cache the client
            self._clients[cache_key] = client
            return client
            
        except Exception as e:
            self.logger.error(f"Error creating AWS client for {service}: {e}", "aws")
            raise
    
    def _create_cross_account_client(self, service: str, account_id: str, region: str):
        """Create a client with cross-account role assumption."""
        self.logger.debug(f"Creating cross-account client for {service} in account {account_id}", "aws")
        
        sts_client = boto3.client('sts')
        role_arn = f"arn:aws:iam::{account_id}:role/{self.config.aws_cross_account_role}"
        
        self.logger.debug(f"Assuming role: {role_arn}", "aws")
        
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="AutocostControllerSession"
        )
        
        credentials = assumed_role['Credentials']
        
        client = boto3.client(
            service,
            region_name=region,
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        
        self.logger.debug(f"Successfully created cross-account client for {service}", "aws")
        return client
    
    def _create_standard_client(self, service: str, region: str):
        """Create a standard client for the current account."""
        if self.config.aws_profile:
            session = boto3.Session(profile_name=self.config.aws_profile)
            client = session.client(service, region_name=region)
        else:
            client = boto3.client(service, region_name=region)
        
        current_account = boto3.client('sts').get_caller_identity()['Account']
        self.logger.debug(f"Successfully created client for {service} in account {current_account}", "aws")
        
        return client 