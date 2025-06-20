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
    async def ping_server() -> str:
        """Quick ping test to verify server connectivity and responsiveness."""
        import asyncio
        from datetime import datetime
        
        logger.info("🏓 Ping test requested")
        
        start_time = datetime.now()
        
        # Simulate a quick async operation
        await asyncio.sleep(0.1)
        
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        response = [
            "🏓 **PING RESPONSE**",
            "=" * 30,
            f"⏰ Response time: {duration_ms:.1f}ms",
            f"📅 Server time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"🚀 Status: Server is responsive",
            "",
            "✅ Connection test successful!"
        ]
        
        logger.info(f"🏓 Ping completed in {duration_ms:.1f}ms")
        return "\n".join(response)
    
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
            
            # Add AWS profile information if AWS provider is ready
            if provider_name == "aws" and status.status == "ready":
                aws_provider = provider_manager.get_provider("aws")
                if aws_provider:
                    current_profile = aws_provider.get_current_profile()
                    try:
                        # Use fast profile info to avoid timeouts in provider status
                        profile_info = aws_provider.get_profile_info_fast()
                        output.append(f"   Profile: {current_profile or 'default'}")
                        if profile_info:
                            output.append(f"   Region: {profile_info.get('region', 'Unknown')}")
                            # Only show account if we have full info (not just fast info)
                            try:
                                full_info = aws_provider.get_profile_info()
                                if full_info and full_info.get('account_id') and 'timeout' not in full_info.get('account_id', ''):
                                    output.append(f"   Account: {full_info.get('account_id', 'Unknown')}")
                            except Exception:
                                # If full info fails, just skip account info
                                pass
                    except Exception:
                        output.append(f"   Profile: {current_profile or 'default'} (info unavailable)")
            
            # Add GCP project information if GCP provider is ready
            elif provider_name == "gcp" and status.status == "ready":
                gcp_provider = provider_manager.get_provider("gcp")
                if gcp_provider:
                    current_project = gcp_provider.get_current_project()
                    try:
                        project_info = gcp_provider.get_project_info()
                        output.append(f"   Project: {current_project or 'default'}")
                        if project_info:
                            output.append(f"   Name: {project_info.get('name', 'Unknown')}")
                            output.append(f"   Number: {project_info.get('number', 'Unknown')}")
                            output.append(f"   State: {project_info.get('state', 'Unknown')}")
                    except Exception:
                        output.append(f"   Project: {current_project or 'default'} (info unavailable)")
            
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
        
        # Add quick usage tips
        if ready_count > 0:
            output.append(f"\n💡 **QUICK TIPS**:")
            if any(k == "aws" and v.status == "ready" for k, v in filtered_statuses.items()):
                output.append(f"   • AWS: Use `aws_profile_list()` to see profiles")
                output.append(f"   • AWS: Use `aws_test_permissions()` to check access")
                output.append(f"   • AWS: Use `aws_cost_explorer_analyze_by_service()` for cost analysis")
            if any(k == "gcp" and v.status == "ready" for k, v in filtered_statuses.items()):
                output.append(f"   • GCP: Use `gcp_project_list()` to see available projects")
                output.append(f"   • GCP: Use `gcp_test_permissions()` to check access")
                output.append(f"   • GCP: Use `gcp_project_info()` to see current project details")
                output.append(f"   • GCP: Use `gcp_compute_cost_analysis()` for compute cost analysis")
                output.append(f"   • GCP: Use `gcp_gke_cost_deep_dive()` for GKE cluster analysis")
                output.append(f"   • GCP: Use `gcp_preemptible_instance_analysis()` for preemptible usage")
                output.append(f"   • GCP: Use `gcp_project_cost_analysis()` for cost by labels/environments")
                output.append(f"   • GCP: Use `gcp_committed_use_discount_analysis()` for CUD opportunities")
                output.append(f"   • GCP: Use `gcp_cost_analysis_summary()` for comprehensive cost guidance")
        
        return "\n".join(output)


def register_aws_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register AWS-specific tools."""
    logger.info("🔧 Registering AWS Cost Explorer tools...")
    
    # Import and register AWS tools
    from .aws_tools import register_aws_tools as register_aws_cost_tools
    from .aws_performance import register_aws_performance_tools
    from .custom import register_custom_tools
    
    # Register basic cost analysis tools
    register_aws_cost_tools(mcp, provider_manager, config, logger)
    
    # Register performance and optimization tools
    register_aws_performance_tools(mcp, provider_manager, config, logger)
    
    # Register custom company-specific tools (can be disabled via env var)
    register_custom_tools(mcp, provider_manager, config, logger)


def register_gcp_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register GCP-specific tools."""
    logger.info("🔧 Registering GCP Cost Explorer tools...")
    
    # Import and register GCP tools
    from .gcp_tools import register_gcp_tools as register_gcp_base_tools
    from .gcp_cost_analysis import register_gcp_cost_analysis_tools
    from .gcp_performance import register_gcp_performance_tools
    
    # Register basic GCP tools
    register_gcp_base_tools(mcp, provider_manager, config, logger)
    
    # Register cost analysis tools
    register_gcp_cost_analysis_tools(mcp, provider_manager, config, logger)
    
    # Register performance and optimization tools
    register_gcp_performance_tools(mcp, provider_manager, config, logger)


def register_azure_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register Azure-specific tools (placeholder)."""
    logger.info("🔧 Azure tools registration - coming soon...")


def register_datadog_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    """Register DataDog-specific tools (placeholder)."""
    logger.info("🔧 DataDog tools registration - coming soon...") 