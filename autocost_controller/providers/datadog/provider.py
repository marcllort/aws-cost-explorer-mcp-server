"""DataDog provider implementation for Autocost Controller."""

from typing import List, Optional
from datetime import datetime

from ...core.provider_manager import BaseProvider
from ...core.config import Config
from ...core.logger import AutocostLogger
from ...core.models import ProviderType, ProviderStatus
from .auth import DatadogAuth
from .client import DatadogClient


class DatadogProvider(BaseProvider):
    """DataDog monitoring provider implementation."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        super().__init__(config, logger)
        self.auth = DatadogAuth(config, logger)
        self.client: Optional[DatadogClient] = None
        self._initialize()
    
    def get_provider_name(self) -> ProviderType:
        """Return the provider name."""
        return "datadog"
    
    def _initialize(self):
        """Initialize the DataDog provider."""
        try:
            if self.auth.validate_credentials():
                self.client = DatadogClient(self.auth, self.logger)
                self.logger.provider_status("datadog", "ready", "Client initialized")
            else:
                self.logger.provider_status("datadog", "error", "Invalid credentials")
        except Exception as e:
            self.logger.provider_status("datadog", "error", f"Initialization failed: {e}")
    
    def validate_configuration(self) -> ProviderStatus:
        """Validate DataDog configuration and return status."""
        try:
            # Check required environment variables
            if not self.auth.validate_credentials():
                missing_config = []
                if not self.config.datadog_api_key:
                    missing_config.append("datadog_api_key")
                if not self.config.datadog_app_key:
                    missing_config.append("datadog_app_key")
                
                return ProviderStatus(
                    provider="datadog",
                    status="error",
                    is_configured=False,
                    missing_config=missing_config,
                    capabilities=[],
                    error_message="DataDog credentials not configured",
                    last_check=datetime.now()
                )
            
            # Test API access
            if not self.auth.test_permissions():
                return ProviderStatus(
                    provider="datadog",
                    status="error",
                    is_configured=False,
                    missing_config=[],
                    capabilities=[],
                    error_message="DataDog API access test failed - check permissions",
                    last_check=datetime.now()
                )
            
            capabilities = self.get_capabilities()
            
            return ProviderStatus(
                provider="datadog",
                status="ready",
                is_configured=True,
                missing_config=[],
                capabilities=capabilities,
                last_check=datetime.now()
            )
            
        except Exception as e:
            return ProviderStatus(
                provider="datadog",
                status="error",
                is_configured=False,
                missing_config=["datadog_api_key", "datadog_app_key"],
                capabilities=[],
                error_message=str(e),
                last_check=datetime.now()
            )
    
    def get_capabilities(self) -> List[str]:
        """Return list of supported capabilities."""
        return [
            "log_analysis",
            "metrics_analysis", 
            "dashboard_management",
            "usage_analysis",
            "apm_analysis",
            "infrastructure_monitoring",
            "alerting",
            "synthetic_monitoring"
        ]
    
    async def test_connection(self) -> bool:
        """Test connection to DataDog."""
        try:
            if not self.client:
                self.client = DatadogClient(self.auth, self.logger)
            
            # Test with a simple API call
            dashboards = await self.client.list_dashboards()
            self.logger.info(f"DataDog connection test passed - found {dashboards.get('total_dashboards', 0)} dashboards", "datadog")
            return True
            
        except Exception as e:
            self.logger.error(f"DataDog connection test failed: {str(e)}", "datadog")
            return False
    
    def get_client(self, service: str = "general") -> DatadogClient:
        """Get the DataDog client for API calls."""
        if not self.client:
            raise RuntimeError("DataDog provider not properly initialized")
        return self.client
    
    def refresh_client(self) -> bool:
        """Refresh the DataDog client connection."""
        try:
            self.auth = DatadogAuth(self.config, self.logger)
            if self.auth.validate_credentials():
                self.client = DatadogClient(self.auth, self.logger)
                self.logger.info("DataDog client refreshed successfully", "datadog")
                return True
            else:
                self.logger.error("Failed to refresh DataDog client - invalid credentials", "datadog")
                return False
        except Exception as e:
            self.logger.error(f"Error refreshing DataDog client: {e}", "datadog")
            return False 