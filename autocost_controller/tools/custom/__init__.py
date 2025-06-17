"""Custom company-specific cost analysis tools."""

from mcp.server.fastmcp import FastMCP

from ...core.provider_manager import ProviderManager
from ...core.config import Config
from ...core.logger import AutocostLogger
from .company_specific_tools import register_company_specific_tools


def register_custom_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register all custom tools if enabled."""
    
    # Check if custom tools are enabled
    if not config.enable_custom_tools:
        logger.info("Custom tools disabled via AUTOCOST_ENABLE_CUSTOM_TOOLS=false")
        return
    
    logger.info("🔧 Registering custom company-specific tools...")
    
    # Register company-specific tools
    register_company_specific_tools(mcp, provider_manager, config, logger)
    
    logger.info("✅ Custom tools registration complete") 