"""Provider manager for multi-cloud cost analysis."""

from typing import Dict, List, Optional, Type
from abc import ABC, abstractmethod

from .config import Config
from .logger import AutocostLogger
from .models import ProviderType, ProviderStatus


class BaseProvider(ABC):
    """Base class for all cloud providers."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        self.config = config
        self.logger = logger
        self.provider_name = self.get_provider_name()
    
    @abstractmethod
    def get_provider_name(self) -> ProviderType:
        """Return the provider name."""
        pass
    
    @abstractmethod
    def validate_configuration(self) -> ProviderStatus:
        """Validate provider configuration and return status."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of supported capabilities."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the provider."""
        pass


class ProviderManager:
    """Manages multiple cloud provider integrations."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        self.config = config
        self.logger = logger
        self.providers: Dict[ProviderType, BaseProvider] = {}
        self.provider_statuses: Dict[ProviderType, ProviderStatus] = {}
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all enabled providers."""
        self.logger.info("🔄 Initializing cloud providers...")
        
        for provider_name in self.config.enabled_providers:
            try:
                provider = self._create_provider(provider_name)
                if provider:
                    self.providers[provider_name] = provider
                    status = provider.validate_configuration()
                    self.provider_statuses[provider_name] = status
                    
                    self.logger.provider_status(
                        provider_name, 
                        status.status, 
                        f"Capabilities: {', '.join(status.capabilities)}"
                    )
                else:
                    self.logger.provider_status(
                        provider_name, 
                        "error", 
                        "Provider not implemented yet"
                    )
            except Exception as e:
                self.logger.provider_status(
                    provider_name, 
                    "error", 
                    f"Initialization failed: {str(e)}"
                )
    
    def _create_provider(self, provider_name: ProviderType) -> Optional[BaseProvider]:
        """Create a provider instance."""
        if provider_name == "aws":
            from ..providers.aws.provider import AWSProvider
            return AWSProvider(self.config, self.logger)
        elif provider_name == "gcp":
            from ..providers.gcp.provider import GCPProvider
            return GCPProvider(self.config, self.logger)
        elif provider_name == "azure":
            from ..providers.azure.provider import AzureProvider
            return AzureProvider(self.config, self.logger)
        elif provider_name == "datadog":
            from ..providers.datadog.provider import DatadogProvider
            return DatadogProvider(self.config, self.logger)
        else:
            return None
    
    def get_provider(self, provider_name: ProviderType) -> Optional[BaseProvider]:
        """Get a provider instance."""
        return self.providers.get(provider_name)
    
    def get_ready_providers(self) -> List[ProviderType]:
        """Get list of ready providers."""
        return [
            provider for provider, status in self.provider_statuses.items()
            if status.status == "ready"
        ]
    
    def get_provider_status(self, provider_name: ProviderType) -> Optional[ProviderStatus]:
        """Get status for a specific provider."""
        return self.provider_statuses.get(provider_name)
    
    def get_all_statuses(self) -> Dict[ProviderType, ProviderStatus]:
        """Get all provider statuses."""
        return self.provider_statuses.copy()
    
    def is_provider_ready(self, provider_name: ProviderType) -> bool:
        """Check if a provider is ready for use."""
        status = self.provider_statuses.get(provider_name)
        return status is not None and status.status == "ready"
    
    async def test_all_connections(self) -> Dict[ProviderType, bool]:
        """Test connections for all providers."""
        results = {}
        
        for provider_name, provider in self.providers.items():
            try:
                result = await provider.test_connection()
                results[provider_name] = result
                
                if result:
                    self.logger.provider_status(provider_name, "ready", "Connection test passed")
                else:
                    self.logger.provider_status(provider_name, "error", "Connection test failed")
                    
            except Exception as e:
                results[provider_name] = False
                self.logger.provider_status(provider_name, "error", f"Connection test error: {str(e)}")
        
        return results 