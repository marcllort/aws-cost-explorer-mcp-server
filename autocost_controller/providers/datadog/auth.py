"""DataDog authentication handler for Autocost Controller."""

import os
from typing import Optional, Dict, Any
from datadog_api_client import Configuration, ApiClient
from datadog_api_client.v1.api.authentication_api import AuthenticationApi
from ...core.config import Config
from ...core.logger import AutocostLogger


class DatadogAuth:
    """Handle DataDog authentication and credentials."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        self.config = config
        self.logger = logger
        self.configuration: Optional[Configuration] = None
        self.api_client: Optional[ApiClient] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize DataDog configuration."""
        try:
            if self.validate_credentials():
                self.configuration = Configuration()
                self.configuration.api_key["apiKeyAuth"] = self.config.datadog_api_key
                self.configuration.api_key["appKeyAuth"] = self.config.datadog_app_key
                self.configuration.server_variables["site"] = self.config.datadog_site
                
                self.api_client = ApiClient(self.configuration)
                self.logger.info(f"DataDog auth initialized for site: {self.config.datadog_site}", "datadog")
            else:
                self.logger.warning("DataDog credentials not properly configured", "datadog")
        except Exception as e:
            self.logger.error(f"DataDog auth initialization failed: {e}", "datadog")
    
    def validate_credentials(self) -> bool:
        """Validate DataDog credentials are available."""
        try:
            # Check required environment variables
            if not self.config.datadog_api_key:
                self.logger.error("DATADOG_API_KEY environment variable is required", "datadog")
                return False
                
            if not self.config.datadog_app_key:
                self.logger.error("DATADOG_APP_KEY environment variable is required", "datadog")
                return False
            
            self.logger.info("DataDog credentials found", "datadog")
            return True
            
        except Exception as e:
            self.logger.error(f"DataDog credential validation failed: {e}", "datadog")
            return False
    
    def test_permissions(self) -> bool:
        """Test if credentials have required permissions."""
        try:
            if not self.api_client:
                return False
            
            # Test authentication with the validation endpoint
            auth_api = AuthenticationApi(self.api_client)
            response = auth_api.validate()
            
            if response.valid:
                self.logger.info("DataDog authentication test successful", "datadog")
                return True
            else:
                self.logger.error("DataDog authentication failed - invalid credentials", "datadog")
                return False
                
        except Exception as e:
            self.logger.error(f"DataDog permission test failed: {e}", "datadog")
            return False
    
    def get_api_client(self) -> ApiClient:
        """Get the configured API client."""
        if not self.api_client:
            raise RuntimeError("DataDog API client not initialized")
        return self.api_client
    
    def get_configuration(self) -> Configuration:
        """Get the configuration object."""
        if not self.configuration:
            raise RuntimeError("DataDog configuration not initialized")
        return self.configuration
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API calls."""
        return {
            "DD-API-KEY": self.config.datadog_api_key,
            "DD-APPLICATION-KEY": self.config.datadog_app_key
        } 