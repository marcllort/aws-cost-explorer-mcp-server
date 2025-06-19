"""GCP provider implementation for Autocost Controller."""

from google.cloud.resourcemanager_v3 import ProjectsClient
from google.cloud import billing
from google.cloud import monitoring_v3
from google.oauth2 import service_account
import os
from typing import List, Optional, Dict
from datetime import datetime

from ...core.provider_manager import BaseProvider
from ...core.config import Config
from ...core.logger import AutocostLogger
from ...core.models import ProviderType, ProviderStatus


class GCPProvider(BaseProvider):
    """GCP cloud provider implementation."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        super().__init__(config, logger)
        self._clients = {}
        self._current_project = None
        self._credentials = None
        
        # Set initial project from config
        if config.gcp_project_id:
            self.set_project(config.gcp_project_id)
    
    def get_provider_name(self) -> ProviderType:
        """Return the provider name."""
        return "gcp"
    
    def set_project(self, project_id: Optional[str] = None) -> bool:
        """Switch to a different GCP project and clear client cache."""
        try:
            if project_id == self._current_project:
                self.logger.info(f"Already using project: {project_id or 'default'}", "gcp")
                return True
            
            # Test the project access
            if project_id:
                try:
                    # Create Resource Manager client to validate project access
                    client = ProjectsClient()
                    request = {"name": f"projects/{project_id}"}
                    project = client.get_project(request=request)
                    self.logger.info(f"✅ Project '{project_id}' access verified successfully", "gcp")
                except Exception as e:
                    self.logger.error(f"Failed to access project '{project_id}': {str(e)}", "gcp")
                    return False
            else:
                # For default project, just log the switch
                self.logger.info("✅ Switching to default project", "gcp")
            
            # Clear all cached clients when switching projects
            self._clients.clear()
            self._current_project = project_id
            
            self.logger.info(f"🔄 Switched to GCP project: {project_id or 'default'}", "gcp")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to switch to project '{project_id}': {str(e)}", "gcp")
            return False
    
    def get_current_project(self) -> Optional[str]:
        """Get the currently active GCP project."""
        return self._current_project
    
    def list_available_projects(self) -> List[str]:
        """List all available GCP projects."""
        try:
            client = ProjectsClient()
            request = {"page_size": 1000}
            projects = client.search_projects(request=request)
            return [project.project_id for project in projects]
        except Exception as e:
            self.logger.error(f"Error listing GCP projects: {str(e)}", "gcp")
            return []
    
    def get_project_info(self, project_id: Optional[str] = None) -> Dict:
        """Get information about a specific project or current project."""
        try:
            client = ProjectsClient()
            request = {"name": f"projects/{project_id or self._current_project}"}
            project = client.get_project(request=request)
            
            return {
                'project_id': project.project_id,
                'name': project.display_name,
                'number': project.project_number,
                'state': project.state,
                'create_time': project.create_time,
                'labels': dict(project.labels)
            }
        except Exception as e:
            self.logger.error(f"Error getting project info: {str(e)}", "gcp")
            return {}
    
    def refresh_credentials_from_environment(self) -> bool:
        """Refresh GCP credentials from environment variables."""
        try:
            # Clear cached clients to force re-authentication
            self._clients.clear()
            self._credentials = None
            
            # Test if environment credentials work
            client = ProjectsClient()
            # Just list one project to verify credentials
            request = {"page_size": 1}
            next(client.search_projects(request=request))
            
            self.logger.info("✅ Refreshed GCP credentials from environment", "gcp")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to refresh credentials from environment: {str(e)}", "gcp")
            return False
    
    def validate_configuration(self) -> ProviderStatus:
        """Validate GCP configuration and return status."""
        try:
            # Clear any cached clients to ensure fresh authentication
            self._clients.clear()
            
            # Check if project is set
            if not self._current_project:
                self.logger.info("🔍 Checking environment for GCP project ID...", "gcp")
                project_id = os.environ.get("GCP_PROJECT_ID")
                if project_id:
                    self.logger.info(f"✅ Found GCP project ID in environment: {project_id}", "gcp")
                    self._current_project = project_id
                else:
                    self.logger.error("❌ No GCP project ID found in environment or config", "gcp")
                    raise ValueError("GCP project not configured - set GCP_PROJECT_ID environment variable or configure in config file")
            
            # Log the project we're trying to use
            self.logger.info(f"🔍 Validating GCP project: {self._current_project}", "gcp")
            
            # Check GCP credentials
            self.logger.info("🔍 Checking GCP credentials...", "gcp")
            client = ProjectsClient()
            
            # Verify access by getting the specific project
            self.logger.info(f"🔍 Verifying access to project {self._current_project}...", "gcp")
            request = {"name": f"projects/{self._current_project}"}
            project = client.get_project(request=request)
            
            # Log successful authentication
            self.logger.info(f"✅ GCP authentication successful - Project: {project.project_id}", "gcp")
            
            capabilities = [
                "cost_analysis",
                "performance_metrics", 
                "optimization_recommendations",
                "dimension_discovery",
                "tag_analysis",
                "billing_account_access",
                "project_switching"
            ]
            
            return ProviderStatus(
                provider="gcp",
                status="ready",
                is_configured=True,
                missing_config=[],
                capabilities=capabilities,
                last_check=datetime.now()
            )
            
        except Exception as e:
            missing_config = []
            error_msg = str(e)
            
            if "credentials" in error_msg.lower():
                missing_config.append("gcp_credentials")
                self.logger.error(f"❌ GCP credentials not found or invalid: {error_msg}", "gcp")
            elif "permission denied" in error_msg.lower():
                missing_config.append("insufficient_permissions")
                self.logger.error(f"❌ GCP credentials have insufficient permissions: {error_msg}", "gcp")
            elif "project" in error_msg.lower():
                missing_config.append("gcp_project")
                self.logger.error(f"❌ GCP project not configured or invalid: {error_msg}", "gcp")
            else:
                self.logger.error(f"❌ GCP validation failed: {error_msg}", "gcp")
            
            return ProviderStatus(
                provider="gcp",
                status="error",
                is_configured=False,
                missing_config=missing_config,
                capabilities=[],
                error_message=error_msg,
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
            "billing_account_access",
            "project_switching"
        ]
    
    async def test_connection(self) -> bool:
        """Test connection to GCP."""
        try:
            client = ProjectsClient()
            # Just list one project to verify connection
            request = {"page_size": 1}
            next(client.search_projects(request=request))
            return True
        except Exception as e:
            self.logger.error(f"GCP connection test failed: {str(e)}", "gcp")
            return False
    
    def get_client(self, service: str, project_id: Optional[str] = None) -> any:
        """Get a GCP client for the specified service."""
        try:
            if service not in self._clients:
                if service == 'billing':
                    self._clients[service] = billing.CloudBillingClient()
                elif service == 'monitoring':
                    self._clients[service] = monitoring_v3.MetricServiceClient()
                elif service == 'resource_manager':
                    self._clients[service] = ProjectsClient()
            
            return self._clients[service]
            
        except Exception as e:
            self.logger.error(f"Failed to get GCP client for service '{service}': {str(e)}", "gcp")
            return None
    
    # TODO: Implement GCP-specific methods
    # def get_billing_client(self):
    # def get_monitoring_client(self):
    # def get_resource_manager_client(self): 