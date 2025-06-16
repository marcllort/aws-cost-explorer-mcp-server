"""MCP tools registration for Autocost Controller."""

import os
from mcp.server.fastmcp import FastMCP
from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger


def register_all_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register all MCP tools for multi-provider cost analysis with provider filtering."""
    
    # Get enabled providers from environment
    enabled_providers = []
    if "AUTOCOST_PROVIDERS" in os.environ:
        providers = os.environ["AUTOCOST_PROVIDERS"].split(",")
        enabled_providers = [p.strip().lower() for p in providers if p.strip()]
    
    # Register core multi-provider tools
    register_core_tools(mcp, provider_manager, config, logger)
    
    # Register provider-specific tools only for enabled providers
    if not enabled_providers or "aws" in enabled_providers:
        if provider_manager.is_provider_ready("aws"):
            register_aws_tools(mcp, provider_manager, config, logger)
        else:
            logger.info("🔶 AWS tools skipped - provider not ready")
    else:
        logger.info("🔶 AWS tools skipped - provider not enabled for this endpoint")
    
    if not enabled_providers or "gcp" in enabled_providers:
        if provider_manager.is_provider_ready("gcp"):
            register_gcp_tools(mcp, provider_manager, config, logger)
        else:
            logger.info("🔵 GCP tools skipped - provider not ready")
    else:
        logger.info("🔵 GCP tools skipped - provider not enabled for this endpoint")
    
    if not enabled_providers or "azure" in enabled_providers:
        if provider_manager.is_provider_ready("azure"):
            register_azure_tools(mcp, provider_manager, config, logger)
        else:
            logger.info("🔷 Azure tools skipped - provider not ready")
    else:
        logger.info("🔷 Azure tools skipped - provider not enabled for this endpoint")
    
    if not enabled_providers or "datadog" in enabled_providers:
        if provider_manager.is_provider_ready("datadog"):
            register_datadog_tools(mcp, provider_manager, config, logger)
        else:
            logger.info("🐕 DataDog tools skipped - provider not ready")
    else:
        logger.info("🐕 DataDog tools skipped - provider not enabled for this endpoint")


def register_core_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register core multi-provider tools."""
    
    @mcp.tool()
    async def get_provider_status() -> str:
        """Get status of all configured cloud providers."""
        logger.info("📋 Getting provider status...")
        
        statuses = provider_manager.get_all_statuses()
        
        # Get enabled providers filter
        enabled_providers = []
        if "AUTOCOST_PROVIDERS" in os.environ:
            providers = os.environ["AUTOCOST_PROVIDERS"].split(",")
            enabled_providers = [p.strip().lower() for p in providers if p.strip()]
        
        output = ["🔍 **PROVIDER STATUS REPORT**", "=" * 50]
        
        # Show endpoint info if available
        endpoint_id = os.environ.get("AUTOCOST_ENDPOINT", "default")
        if endpoint_id != "default":
            output.append(f"📡 **Endpoint**: {endpoint_id}")
        
        if enabled_providers:
            output.append(f"🎯 **Enabled Providers**: {', '.join(enabled_providers).upper()}")
            output.append("")
        
        for provider_name, status in statuses.items():
            # Skip providers not enabled for this endpoint
            if enabled_providers and provider_name not in enabled_providers:
                continue
                
            emoji = {
                "ready": "✅",
                "error": "❌", 
                "warning": "⚠️",
                "disabled": "⏸️"
            }.get(status.status, "❓")
            
            output.append(f"\n{emoji} **{provider_name.upper()}**: {status.status}")
            output.append(f"   Configured: {'Yes' if status.is_configured else 'No'}")
            
            if status.capabilities:
                output.append(f"   Capabilities: {', '.join(status.capabilities)}")
            
            if status.missing_config:
                output.append(f"   Missing: {', '.join(status.missing_config)}")
            
            if status.error_message:
                output.append(f"   Error: {status.error_message}")
        
        # Filter ready providers by enabled providers
        filtered_statuses = {k: v for k, v in statuses.items() 
                           if not enabled_providers or k in enabled_providers}
        ready_count = len([s for s in filtered_statuses.values() if s.status == "ready"])
        
        output.append(f"\n📊 **SUMMARY**: {ready_count}/{len(filtered_statuses)} providers ready")
        
        return "\n".join(output)


def register_aws_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register AWS-specific tools."""
    logger.info("🔧 Registering AWS Cost Explorer tools...")
    
    # Import and register AWS tools
    from .aws_tools import register_aws_tools as register_aws_cost_tools
    from .aws_performance import register_aws_performance_tools
    
    # Register cost analysis tools
    register_aws_cost_tools(mcp, provider_manager, config, logger)
    
    # Register performance and optimization tools
    register_aws_performance_tools(mcp, provider_manager, config, logger)


def register_gcp_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register GCP-specific tools (placeholder)."""
    logger.info("🔧 GCP tools registration - coming soon...")


def register_azure_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register Azure-specific tools (placeholder)."""
    logger.info("🔧 Azure tools registration - coming soon...")


def register_datadog_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register DataDog-specific tools (placeholder)."""
    logger.info("🔧 DataDog tools registration - coming soon...") 