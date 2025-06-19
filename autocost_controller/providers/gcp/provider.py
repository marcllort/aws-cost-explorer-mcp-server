"""GCP provider implementation for Autocost Controller."""

from google.cloud.resourcemanager_v3 import ProjectsClient
from google.cloud import billing
from google.cloud import monitoring_v3
from google.oauth2 import service_account
import os
import json
from pathlib import Path
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
        self._organization_id = None
        self._credentials = None
        
        # Load saved credentials if available (similar to AWS approach)
        self._load_saved_credentials()
        
        # Set initial project from config
        if config.gcp_project_id:
            self.set_project(config.gcp_project_id)
        
        # Set organization ID from config
        if config.gcp_organization_id:
            self._organization_id = config.gcp_organization_id
            self.logger.info(f"🏢 Organization ID configured: {self._organization_id}", "gcp")
    
    def _load_saved_credentials(self) -> bool:
        """Load saved GCP credentials from .gcp_credentials.json file (similar to AWS approach)."""
        try:
            # Look for saved credentials file
            project_root = Path(__file__).parent.parent.parent.parent
            creds_file = project_root / ".gcp_credentials.json"
            
            if not creds_file.exists():
                self.logger.debug("No saved GCP credentials file found", "gcp")
                return False
            
            with open(creds_file, 'r') as f:
                creds_data = json.load(f)
            
            # Set up environment for GCP credentials
            if creds_data.get("type") == "service_account" and creds_data.get("credentials_file"):
                # Service account credentials
                if os.path.exists(creds_data["credentials_file"]):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_data["credentials_file"]
                    self.logger.info("✅ Loaded GCP service account credentials from saved file", "gcp")
                else:
                    self.logger.warning(f"Service account file not found: {creds_data['credentials_file']}", "gcp")
                    return False
            
            # Set project and organization from saved credentials
            if creds_data.get("project_id"):
                self._current_project = creds_data["project_id"]
                self.logger.info(f"📝 Using saved project: {self._current_project}", "gcp")
            
            self.logger.info(f"✅ Loaded GCP credentials - Source: {creds_data.get('source', 'unknown')}", "gcp")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading saved GCP credentials: {str(e)}", "gcp")
            return False
    
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
    
    def get_organization_id(self) -> Optional[str]:
        """Get the configured GCP organization ID."""
        return self._organization_id
    
    def get_access_scope(self) -> str:
        """Get the current access scope (project or organization)."""
        return "organization" if self._organization_id else "project"
    
    def test_organization_access(self) -> bool:
        """Test organization access when needed (lazy loading)."""
        if not self._organization_id:
            return False
            
        try:
            self.logger.info(f"🔍 Verifying organization access to {self._organization_id}...", "gcp")
            client = ProjectsClient()
            # Test organization access by listing a few projects
            request = {"page_size": 5, "query": f"parent.id:{self._organization_id}"}
            projects = list(client.search_projects(request=request))
            self.logger.info(f"✅ Organization access verified - Found {len(projects)} project(s)", "gcp")
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ Organization access test failed: {e}", "gcp")
            return False
    
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
    
    def _get_project_state_name(self, state) -> str:
        """Convert project state enum to readable name."""
        state_map = {
            0: 'LIFECYCLE_STATE_UNSPECIFIED',
            1: 'ACTIVE', 
            2: 'DELETE_REQUESTED',
            3: 'DELETE_IN_PROGRESS'
        }
        state_value = int(state) if hasattr(state, '__int__') else state
        return state_map.get(state_value, f'UNKNOWN_STATE_{state_value}')

    def get_project_info(self, project_id: Optional[str] = None) -> Dict:
        """Get information about a specific project or current project."""
        try:
            client = ProjectsClient()
            request = {"name": f"projects/{project_id or self._current_project}"}
            project = client.get_project(request=request)
            
            # Build project info dict with safe attribute access
            project_info = {
                'project_id': project.project_id,
                'name': getattr(project, 'display_name', project.project_id),
                'state': self._get_project_state_name(project.state) if hasattr(project, 'state') else 'UNKNOWN',
                'labels': dict(getattr(project, 'labels', {}))
            }
            
            # Add optional fields if they exist
            if hasattr(project, 'create_time') and project.create_time:
                project_info['create_time'] = project.create_time
            
            return project_info
            
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
            
            # Check for organization ID first
            if not self._organization_id:
                org_id = os.environ.get("GCP_ORGANIZATION_ID")
                if org_id:
                    self._organization_id = org_id
                    self.logger.info(f"🏢 Organization ID configured: {org_id}", "gcp")
            
            # Check if project is set (required for some operations, but not all)
            if not self._current_project:
                project_id = os.environ.get("GCP_PROJECT_ID")
                if project_id:
                    self._current_project = project_id
                elif not self._organization_id:
                    # Only require project ID if no organization ID is set
                    self.logger.error("❌ No GCP project ID or organization ID found", "gcp")
                    raise ValueError("GCP project or organization not configured - set GCP_PROJECT_ID or GCP_ORGANIZATION_ID environment variable")
            
            # Determine access scope
            if self._organization_id:
                self.logger.info(f"🏢 Using organization-level access: {self._organization_id}", "gcp")
                access_scope = "organization"
            else:
                self.logger.info(f"📝 Using project-level access: {self._current_project}", "gcp")
                access_scope = "project"
            
            # Quick credential test - just create client without making API calls
            self.logger.info("🔍 Checking GCP credentials...", "gcp")
            try:
                client = ProjectsClient()
                # Only test actual API access if explicitly needed
                if access_scope == "project" and self._current_project:
                    # Quick project validation
                    request = {"name": f"projects/{self._current_project}"}
                    project = client.get_project(request=request)
                    self.logger.info(f"✅ Project access verified - Project: {project.project_id}", "gcp")
                else:
                    # For organization access, just verify we can create the client
                    # Actual organization access will be tested when needed
                    self.logger.info("✅ GCP credentials loaded successfully", "gcp")
                    
            except Exception as e:
                self.logger.error(f"❌ GCP credential validation failed: {str(e)}", "gcp")
                raise e
            
            # Log successful authentication
            self.logger.info(f"✅ GCP authentication successful - Access scope: {access_scope}", "gcp")
            
            capabilities = [
                "cost_analysis",
                "performance_metrics", 
                "optimization_recommendations",
                "dimension_discovery",
                "tag_analysis",
                "billing_account_access"
            ]
            
            # Add scope-specific capabilities
            if access_scope == "organization":
                capabilities.extend(["organization_access", "cross_project_analysis"])
            else:
                capabilities.append("project_switching")
            
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
            elif "project" in error_msg.lower() or "organization" in error_msg.lower():
                missing_config.append("gcp_project_or_organization")
                self.logger.error(f"❌ GCP project or organization not configured: {error_msg}", "gcp")
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