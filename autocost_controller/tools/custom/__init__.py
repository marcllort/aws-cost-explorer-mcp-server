"""Custom company-specific tools for Autocost Controller."""

import os
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from ..aws_cost_analysis import register_aws_cost_analysis_tools
from ...core.provider_manager import ProviderManager
from ...core.config import Config
from ...core.logger import AutocostLogger


def is_custom_tools_enabled() -> bool:
    """Check if custom tools are enabled via environment variable."""
    return os.environ.get('AUTOCOST_ENABLE_CUSTOM_TOOLS', 'true').lower() in ('true', '1', 'yes')


def register_custom_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register custom company-specific tools if enabled."""
    
    if not is_custom_tools_enabled():
        logger.info("🔧 Custom tools disabled via AUTOCOST_ENABLE_CUSTOM_TOOLS")
        return
    
    logger.info("🔧 Registering custom company-specific tools...")
    
    # Register the advanced cost analysis tools (including tenant analysis)
    # These are company-specific and may not be relevant for all users
    register_aws_cost_analysis_tools(mcp, provider_manager, config, logger)
    
    logger.info("✅ Custom tools registered successfully") 