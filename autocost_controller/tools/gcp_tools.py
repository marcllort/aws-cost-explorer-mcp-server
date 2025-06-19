"""GCP tools registration for Autocost Controller."""

from typing import Dict, List, Optional
from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger
from .gcp_cost_analysis import register_gcp_cost_analysis_tools
from .gcp_performance import register_gcp_performance_tools


def register_gcp_tools(mcp, provider_manager: ProviderManager, 
                      config: Config, logger: AutocostLogger) -> None:
    """Register all GCP tools."""
    
    gcp_provider = provider_manager.get_provider("gcp")
    if not gcp_provider:
        logger.warning("GCP provider not available, skipping tools registration")
        return
    
    # Register cost analysis tools
    register_gcp_cost_analysis_tools(mcp, provider_manager, config, logger)
    
    # Register performance tools
    register_gcp_performance_tools(mcp, provider_manager, config, logger)
    
    # Register GCP-specific tools
    
    @mcp.tool()
    async def gcp_test_permissions(random_string: str = "") -> str:
        """Test GCP permissions for various services with current project."""
        logger.info("🔍 Testing GCP permissions...")
        
        try:
            # Test basic connectivity
            if not await gcp_provider.test_connection():
                return "❌ Failed to connect to GCP"
            
            # Get current project info
            project_info = gcp_provider.get_project_info()
            if not project_info:
                return "❌ Failed to get project information"
            
            # Test various services
            services_status = []
            
            # Test Billing API
            try:
                client = gcp_provider.get_client('billing')
                services_status.append("✅ Billing API")
            except Exception as e:
                services_status.append(f"❌ Billing API: {str(e)}")
            
            # Test Monitoring API
            try:
                client = gcp_provider.get_client('monitoring')
                services_status.append("✅ Monitoring API")
            except Exception as e:
                services_status.append(f"❌ Monitoring API: {str(e)}")
            
            # Test Resource Manager API
            try:
                client = gcp_provider.get_client('resource_manager')
                services_status.append("✅ Resource Manager API")
            except Exception as e:
                services_status.append(f"❌ Resource Manager API: {str(e)}")
            
            # Generate report
            report = f"""
            GCP Permissions Test Results:
            
            🔑 Authentication:
            - Project: {project_info.get('project_id', 'Unknown')}
            - Name: {project_info.get('name', 'Unknown')}
            - Number: {project_info.get('number', 'Unknown')}
            - State: {project_info.get('state', 'Unknown')}
            
            🔌 API Access:
            """
            
            for status in services_status:
                report += f"- {status}\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to test GCP permissions: {str(e)}", "gcp")
            return f"Error testing GCP permissions: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_list(random_string: str = "") -> str:
        """List all available GCP projects."""
        logger.info("🔍 Listing GCP projects...")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Generate report
            report = """
            Available GCP Projects:
            
            📋 Projects:
            """
            
            for project in projects:
                # Get project info
                info = gcp_provider.get_project_info(project)
                if info:
                    report += f"- {info['name']} ({info['project_id']})\n"
                    report += f"  State: {info['state']}\n"
                    if info.get('labels'):
                        report += f"  Labels: {', '.join(f'{k}={v}' for k, v in info['labels'].items())}\n"
                else:
                    report += f"- {project} (Error getting details)\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to list GCP projects: {str(e)}", "gcp")
            return f"Error listing GCP projects: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_switch(project_id: str) -> str:
        """Switch to a different GCP project."""
        logger.info(f"🔄 Switching to GCP project: {project_id}")
        
        try:
            if gcp_provider.set_project(project_id):
                info = gcp_provider.get_project_info(project_id)
                
                return f"""
                ✅ Successfully switched to GCP project:
                - Project ID: {info['project_id']}
                - Name: {info['name']}
                - Number: {info['number']}
                - State: {info['state']}
                """
            else:
                return f"❌ Failed to switch to project: {project_id}"
            
        except Exception as e:
            logger.error(f"Failed to switch GCP project: {str(e)}", "gcp")
            return f"Error switching GCP project: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_info(project_id: Optional[str] = None) -> str:
        """Get detailed information about a GCP project."""
        logger.info(f"🔍 Getting info for GCP project: {project_id or 'current'}")
        
        try:
            info = gcp_provider.get_project_info(project_id)
            
            if not info:
                return f"❌ Failed to get project information for: {project_id or 'current project'}"
            
            # Generate report
            report = f"""
            GCP Project Information:
            
            📋 Project Details:
            - Project ID: {info['project_id']}
            - Name: {info['name']}
            - Number: {info['number']}
            - State: {info['state']}
            - Created: {info['create_time']}
            """
            
            if info.get('labels'):
                report += "\n🏷️ Labels:\n"
                for key, value in info['labels'].items():
                    report += f"- {key}: {value}\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to get GCP project info: {str(e)}", "gcp")
            return f"Error getting GCP project info: {str(e)}" 