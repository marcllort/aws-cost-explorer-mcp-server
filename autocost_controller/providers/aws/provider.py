"""AWS provider implementation for Autocost Controller."""

import boto3
import os
from typing import List, Optional, Dict
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
        self._current_profile = None
        self._profile_sessions = {}
    
    def get_provider_name(self) -> ProviderType:
        """Return the provider name."""
        return "aws"
    
    def set_profile(self, profile_name: Optional[str] = None) -> bool:
        """Switch to a different AWS profile and clear client cache."""
        try:
            if profile_name == self._current_profile:
                self.logger.info(f"Already using profile: {profile_name or 'default'}", "aws")
                return True
            
            # Test the profile first (with minimal validation)
            if profile_name:
                # Check if profile exists (fast operation)
                available_profiles = boto3.session.Session().available_profiles
                if profile_name not in available_profiles:
                    self.logger.error(f"Profile '{profile_name}' not found. Available: {available_profiles}", "aws")
                    return False
                
                # Quick test - just create session without API call
                try:
                    session = boto3.Session(profile_name=profile_name)
                    # Only test credentials if we can do it quickly
                    # Skip the validation API call to avoid timeouts
                    self.logger.info(f"✅ Profile '{profile_name}' session created successfully", "aws")
                    self._profile_sessions[profile_name] = session
                except Exception as e:
                    self.logger.error(f"Failed to create session for profile '{profile_name}': {str(e)}", "aws")
                    return False
            else:
                # For default credentials, just log the switch
                self.logger.info(f"✅ Switching to default credentials", "aws")
            
            # Clear all cached clients when switching profiles
            self._clients.clear()
            self._current_profile = profile_name
            
            self.logger.info(f"🔄 Switched to AWS profile: {profile_name or 'default'}", "aws")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to switch to profile '{profile_name}': {str(e)}", "aws")
            return False
    
    def get_current_profile(self) -> Optional[str]:
        """Get the currently active AWS profile."""
        return self._current_profile
    
    def list_available_profiles(self) -> List[str]:
        """List all available AWS profiles."""
        try:
            return boto3.session.Session().available_profiles
        except Exception as e:
            self.logger.error(f"Error listing AWS profiles: {str(e)}", "aws")
            return []
    
    def get_profile_info(self, profile_name: Optional[str] = None) -> Dict:
        """Get information about a specific profile or current profile."""
        try:
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
            else:
                if self._current_profile:
                    session = boto3.Session(profile_name=self._current_profile)
                else:
                    session = boto3.Session()
            
            # Try to get caller identity with timeout protection
            try:
                sts_client = session.client('sts')
                # This is the potentially slow operation
                identity = sts_client.get_caller_identity()
                
                # Get region
                region = session.region_name or os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
                
                return {
                    'profile_name': profile_name or self._current_profile or 'default',
                    'account_id': identity['Account'],
                    'user_arn': identity['Arn'],
                    'region': region,
                    'user_id': identity['UserId']
                }
            except Exception as api_error:
                # If API call fails, return basic info
                region = session.region_name or os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
                return {
                    'profile_name': profile_name or self._current_profile or 'default',
                    'account_id': 'Unknown (API timeout)',
                    'user_arn': f'Unknown ({str(api_error)[:50]})',
                    'region': region,
                    'user_id': 'Unknown'
                }
            
        except Exception as e:
            self.logger.error(f"Error getting profile info: {str(e)}", "aws")
            return {}
    
    def get_profile_info_fast(self, profile_name: Optional[str] = None) -> Dict:
        """Get basic profile information without API calls (fast version)."""
        try:
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
            else:
                if self._current_profile:
                    session = boto3.Session(profile_name=self._current_profile)
                else:
                    session = boto3.Session()
            
            # Get region without API calls
            region = session.region_name or os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            
            return {
                'profile_name': profile_name or self._current_profile or 'default',
                'region': region,
                'status': 'ready'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting fast profile info: {str(e)}", "aws")
            return {
                'profile_name': profile_name or self._current_profile or 'default',
                'region': 'unknown',
                'status': 'error'
            }
    
    def validate_configuration(self) -> ProviderStatus:
        """Validate AWS configuration and return status."""
        try:
            # Check AWS credentials
            if self._current_profile:
                session = boto3.Session(profile_name=self._current_profile)
                sts_client = session.client('sts')
            else:
                sts_client = boto3.client('sts')
                
            identity = sts_client.get_caller_identity()
            
            capabilities = [
                "cost_analysis",
                "performance_metrics", 
                "optimization_recommendations",
                "dimension_discovery",
                "tag_analysis",
                "cross_account_access",
                "profile_switching"
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
            "s3_analysis",
            "profile_switching"
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
        
        # Create cache key including current profile
        cache_key = f"{service}_{account_id or 'default'}_{region}_{self._current_profile or 'default'}"
        
        if cache_key in self._clients:
            return self._clients[cache_key]
        
        try:
            # Use current profile if set
            if self._current_profile:
                session = boto3.Session(profile_name=self._current_profile)
                sts_client = session.client('sts')
            else:
                sts_client = boto3.client('sts')
                session = boto3.Session()
                
            current_account = sts_client.get_caller_identity()['Account']
            
            if account_id and current_account != account_id:
                client = self._create_cross_account_client(service, account_id, region, session)
            else:
                client = self._create_standard_client(service, region, session)
            
            # Cache the client
            self._clients[cache_key] = client
            return client
            
        except Exception as e:
            self.logger.error(f"Error creating AWS client for {service}: {e}", "aws")
            raise
    
    def _create_cross_account_client(self, service: str, account_id: str, region: str, session: boto3.Session):
        """Create a client with cross-account role assumption."""
        self.logger.debug(f"Creating cross-account client for {service} in account {account_id}", "aws")
        
        sts_client = session.client('sts')
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
    
    def _create_standard_client(self, service: str, region: str, session: boto3.Session):
        """Create a standard client for the current account."""
        client = session.client(service, region_name=region)
        
        sts_client = session.client('sts')
        current_account = sts_client.get_caller_identity()['Account']
        self.logger.debug(f"Successfully created client for {service} in account {current_account}", "aws")
        
        return client 