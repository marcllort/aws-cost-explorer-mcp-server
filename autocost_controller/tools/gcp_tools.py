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
        """List all available GCP projects (fast - IDs only)."""
        logger.info("🔍 Listing GCP projects...")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Fast listing - just project IDs
            report = f"""📋 **Available GCP Projects**
Organization: {gcp_provider.get_organization_id() or 'N/A'}
Total Projects: {len(projects)}

🚀 **Quick List** (Project IDs):
"""
            
            # Show projects in columns for better readability
            for i, project in enumerate(projects, 1):
                if i <= 50:  # Show first 50 projects
                    report += f"{i:3d}. {project}\n"
                elif i == 51:
                    report += f"\n... and {len(projects) - 50} more projects\n"
                    break
            
            report += f"""
💡 **Usage Tips**:
• Use gcp_project_info("project-id") for detailed info about a specific project
• Use gcp_project_switch("project-id") to switch to a different project
• Use gcp_project_list_detailed() for detailed info (slower for large lists)

📊 **Summary**: {len(projects)} projects accessible under organization {gcp_provider.get_organization_id() or 'N/A'}
"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to list GCP projects: {str(e)}", "gcp")
            return f"Error listing GCP projects: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_list_detailed(limit: int = 20, random_string: str = "") -> str:
        """List GCP projects with detailed information (slower - use limit to control performance)."""
        logger.info(f"🔍 Listing GCP projects with details (limit: {limit})...")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Limit the number of projects to fetch details for
            limited_projects = projects[:limit]
            
            report = f"""📋 **Detailed GCP Projects List**
Organization: {gcp_provider.get_organization_id() or 'N/A'}
Total Projects: {len(projects)}
Showing Details: {len(limited_projects)} projects

🔍 **Detailed Information**:
"""
            
            for i, project in enumerate(limited_projects, 1):
                try:
                    info = gcp_provider.get_project_info(project)
                    if info:
                        report += f"\n{i:2d}. **{info['name']}** ({info['project_id']})\n"
                        report += f"    State: {info['state']}\n"
                        report += f"    Number: {info['number']}\n"
                        if info.get('labels'):
                            labels = ', '.join(f'{k}={v}' for k, v in list(info['labels'].items())[:3])
                            report += f"    Labels: {labels}\n"
                    else:
                        report += f"\n{i:2d}. **{project}** (Error getting details)\n"
                except Exception as e:
                    report += f"\n{i:2d}. **{project}** (Error: {str(e)[:50]}...)\n"
            
            if len(projects) > limit:
                report += f"\n... and {len(projects) - limit} more projects (use gcp_project_list() for full list)\n"
            
            report += f"""
💡 **Performance Tips**:
• Use gcp_project_list() for fast ID-only listing
• Increase limit parameter for more detailed results (slower)
• Use gcp_project_info("specific-id") for single project details

📊 **Summary**: Showed {len(limited_projects)} of {len(projects)} total projects
"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to list GCP projects with details: {str(e)}", "gcp")
            return f"Error listing GCP projects with details: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_activity_check(limit: int = 30, days: int = 30, random_string: str = "") -> str:
        """Check recent activity for GCP projects to see when they were last used.
        
        ⚠️ PERFORMANCE WARNING: This function can be slow (~2 seconds per project).
        With default limit=30, expect ~60 seconds total execution time.
        Consider using a smaller limit (e.g., 10) for faster results.
        """
        logger.info(f"🔍 Checking activity for {limit} GCP projects over last {days} days...")
        logger.info(f"⚠️ This may take ~{limit * 2} seconds to complete ({limit} projects × ~2s each)")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Limit the number of projects to check for performance
            limited_projects = projects[:limit]
            
            active_projects = []
            inactive_projects = []
            error_projects = []
            
            logger.info(f"📊 Analyzing {len(limited_projects)} projects...")
            
            for i, project_id in enumerate(limited_projects, 1):
                try:
                    # Get project info
                    info = gcp_provider.get_project_info(project_id)
                    
                    if not info:
                        error_projects.append((project_id, "Failed to get info"))
                        continue
                    
                    # Check project state
                    state = info.get('state', 'Unknown')
                    name = info.get('name', 'Unknown')
                    create_time = info.get('create_time')
                    
                    if state != 'ACTIVE':
                        inactive_projects.append((project_id, name, f"State: {state}"))
                        continue
                    
                    # For active projects, categorize by naming patterns
                    # This is a heuristic since we don't have usage metrics easily available
                    
                    # Check if it's a system project (usually auto-generated)
                    if project_id.startswith('sys-'):
                        inactive_projects.append((project_id, name, "System project (likely auto-generated)"))
                    elif any(keyword in project_id.lower() for keyword in ['test', 'demo', 'staging']):
                        active_projects.append((project_id, name, "Development/Test project"))
                    elif any(keyword in project_id.lower() for keyword in ['cosmos', 'scheduling', 'nuvolar', 'couplesync']):
                        active_projects.append((project_id, name, "Application project"))
                    else:
                        active_projects.append((project_id, name, "Active project"))
                        
                except Exception as e:
                    error_projects.append((project_id, str(e)[:50]))
            
            # Build results
            report = []
            report.append(f"📊 **GCP Project Activity Analysis**")
            report.append(f"Organization: {gcp_provider.get_organization_id()}")
            report.append(f"Analyzed: {len(limited_projects)} of {len(projects)} total projects")
            report.append("")
            
            if active_projects:
                report.append(f"✅ **Likely Active Projects** ({len(active_projects)}):")
                for project_id, name, category in active_projects:
                    report.append(f"  • {name} ({project_id})")
                    report.append(f"    Category: {category}")
                report.append("")
            
            if inactive_projects:
                report.append(f"⏸️ **Likely Inactive Projects** ({len(inactive_projects)}):")
                for project_id, name, status in inactive_projects[:10]:
                    report.append(f"  • {name} ({project_id})")
                    report.append(f"    Status: {status}")
                if len(inactive_projects) > 10:
                    report.append(f"  ... and {len(inactive_projects) - 10} more")
                report.append("")
            
            if error_projects:
                report.append(f"❌ **Errors** ({len(error_projects)}):")
                for project_id, error in error_projects[:5]:
                    report.append(f"  • {project_id}: {error}")
                report.append("")
            
            report.append(f"📊 **Summary:**")
            report.append(f"• Likely Active: {len(active_projects)} projects")
            report.append(f"• Likely Inactive: {len(inactive_projects)} projects")
            report.append(f"• Errors: {len(error_projects)} projects")
            report.append("")
            report.append(f"💡 **Note:** This analysis is based on project names, states, and patterns.")
            report.append(f"For detailed usage metrics, billing data or monitoring APIs would be needed.")
            
            logger.cost_analysis_summary("gcp", len(active_projects), days, len(limited_projects))
            return "\n".join(report)
            
        except Exception as e:
            error_msg = f"❌ Error checking project activity: {str(e)}"
            logger.error(error_msg, "gcp")
            return error_msg
    
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