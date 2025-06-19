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
            
            # Note: Billing export setup is now available via MCP tool
            # Users can call gcp_setup_billing_export() when ready
            
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
        # Implementation would go here - this is a placeholder
        # In a full implementation, this would return appropriate clients
        # for different GCP services (compute, storage, monitoring, etc.)
        
        # For now, just return None to indicate the method exists
        return None
    
    async def get_billing_account_info(self) -> Dict:
        """Get billing account information for the current project."""
        try:
            from google.cloud import billing_v1
            
            client = billing_v1.CloudBillingClient()
            
            # Get billing accounts that the user has access to
            billing_accounts = []
            try:
                for account in client.list_billing_accounts():
                    billing_accounts.append({
                        'name': account.name,
                        'displayName': account.display_name,
                        'open': account.open,
                        'masterBillingAccount': account.master_billing_account
                    })
            except Exception as e:
                self.logger.warning(f"Could not list billing accounts: {str(e)}", "gcp")
            
            return {
                'billing_accounts': billing_accounts,
                'current_project': self._current_project
            }
            
        except ImportError:
            self.logger.error("google-cloud-billing library not installed", "gcp")
            return {'billing_accounts': [], 'error': 'Billing library not installed'}
        except Exception as e:
            self.logger.error(f"Error getting billing account info: {str(e)}", "gcp")
            return {'billing_accounts': [], 'error': str(e)}
    
    def setup_billing_export_with_preferences(self, dataset_id: str = "billing_export", 
                                             location: str = "US", 
                                             table_prefix: str = "gcp_billing_export") -> tuple[bool, str]:
        """
        Set up BigQuery billing export with user-specified preferences.
        
        Args:
            dataset_id: BigQuery dataset name for billing data
            location: BigQuery dataset location (US, EU, etc.)
            table_prefix: Prefix for billing export tables
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            from google.cloud import bigquery
            from google.cloud import billing_v1
            
            self.logger.info("🔍 Checking BigQuery billing export setup...", "gcp")
            
            # Check if we have a current project
            project_id = self._current_project
            if not project_id:
                return False, "❌ No current project set, cannot setup billing export"
            
            # Check if billing export already exists
            if self._check_existing_billing_export(project_id, dataset_id):
                return True, f"✅ BigQuery billing export already configured in dataset '{dataset_id}'"
            
            # Try to set up billing export
            self.logger.info(f"🔧 Setting up BigQuery billing export in {location}...", "gcp")
            
            # Create BigQuery dataset if it doesn't exist
            success, dataset_message = self._create_bigquery_dataset_if_needed(project_id, dataset_id, location)
            
            if success:
                success_msg = f"""✅ **BigQuery Dataset Created Successfully**

📊 **Configuration**:
- Project: {project_id}
- Dataset: {dataset_id}
- Location: {location}
- Table Prefix: {table_prefix}

🔧 **Next Steps** (Complete in GCP Console):
1. Go to Cloud Console → Billing → Billing Export
2. Click "Create Export"
3. Configure export:
   • Project: {project_id}
   • Dataset: {dataset_id}
   • Table prefix: {table_prefix}
   • Export type: Standard usage cost data
4. Wait 24-48 hours for data to flow

💡 **Alternative Setup** (gcloud CLI):
```bash
# Enable billing export API
gcloud services enable bigquerydatatransfer.googleapis.com

# Create billing export (requires billing admin role)
gcloud beta billing export create \\
  --billing-account=BILLING_ACCOUNT_ID \\
  --dataset-id={dataset_id} \\
  --project={project_id}
```

📋 **Required Permissions**:
- BigQuery Data Editor (for dataset creation) ✅
- Billing Account Administrator (for export creation)
"""
                return True, success_msg
            else:
                return False, dataset_message
                
        except ImportError:
            return False, """❌ **BigQuery Library Missing**

🔧 **Install Required Package**:
```bash
pip install google-cloud-bigquery
```

Or install with GCP dependencies:
```bash
pip install autocost-controller[gcp]
```"""
        except Exception as e:
            error_msg = f"""❌ **Billing Export Setup Failed**

**Error**: {str(e)}

🔧 **Troubleshooting Steps**:

1. **Check Permissions**:
   - Ensure you have BigQuery Admin or Data Editor role
   - Verify billing account access permissions

2. **Manual Setup Alternative**:
   - Go to Cloud Console → BigQuery
   - Create dataset manually: {dataset_id}
   - Set location: {location}
   - Then set up billing export in console

3. **Verify Prerequisites**:
   - BigQuery API enabled: `gcloud services enable bigquery.googleapis.com`
   - Billing account linked to project
   - Sufficient quota in target location

4. **Get Help**:
   - Use gcp_billing_setup_and_cost_guide() for detailed instructions
   - Check GCP Console → IAM for required permissions
"""
            return False, error_msg

    def _check_existing_billing_export(self, project_id: str, dataset_id: str = "billing_export") -> bool:
        """Check if billing export dataset and tables already exist."""
        try:
            from google.cloud import bigquery
            
            client = bigquery.Client(project=project_id)
            dataset_ref = f"{project_id}.{dataset_id}"
            
            # Check if dataset exists
            try:
                dataset = client.get_dataset(dataset_ref)
                
                # Check if there are any billing export tables
                tables = list(client.list_tables(dataset))
                billing_tables = [t for t in tables if 'billing_export' in t.table_id or 'gcp_billing' in t.table_id]
                
                if billing_tables:
                    self.logger.info(f"Found {len(billing_tables)} billing export tables in {dataset_id}", "gcp")
                    return True
                else:
                    self.logger.info(f"Dataset '{dataset_id}' exists but no billing export tables found", "gcp")
                    return False
                    
            except Exception:
                # Dataset doesn't exist
                return False
                
        except Exception as e:
            self.logger.warning(f"Error checking existing billing export: {str(e)}", "gcp")
            return False

    def list_bigquery_datasets(self, project_id: Optional[str] = None) -> List[Dict]:
        """List all BigQuery datasets in the project."""
        try:
            from google.cloud import bigquery
            
            target_project = project_id or self._current_project
            if not target_project:
                return []
            
            client = bigquery.Client(project=target_project)
            datasets = []
            
            for dataset in client.list_datasets():
                dataset_info = {
                    'dataset_id': dataset.dataset_id,
                    'full_dataset_id': f"{target_project}.{dataset.dataset_id}",
                    'location': dataset.location if hasattr(dataset, 'location') else 'Unknown',
                    'created': dataset.created.isoformat() if hasattr(dataset, 'created') and dataset.created else 'Unknown',
                    'description': dataset.description if hasattr(dataset, 'description') else '',
                    'labels': dict(dataset.labels) if hasattr(dataset, 'labels') and dataset.labels else {}
                }
                
                # Get detailed dataset info
                try:
                    full_dataset = client.get_dataset(dataset.reference)
                    dataset_info.update({
                        'location': full_dataset.location,
                        'created': full_dataset.created.isoformat() if full_dataset.created else 'Unknown',
                        'description': full_dataset.description or '',
                        'labels': dict(full_dataset.labels) if full_dataset.labels else {}
                    })
                    
                    # Count tables in dataset
                    tables = list(client.list_tables(full_dataset))
                    dataset_info['table_count'] = len(tables)
                    
                    # Check for billing-related tables
                    billing_tables = [t.table_id for t in tables if any(keyword in t.table_id.lower() 
                                     for keyword in ['billing', 'cost', 'usage', 'gcp_billing_export'])]
                    dataset_info['billing_tables'] = billing_tables
                    dataset_info['has_billing_data'] = len(billing_tables) > 0
                    
                except Exception as e:
                    self.logger.warning(f"Error getting details for dataset {dataset.dataset_id}: {str(e)}", "gcp")
                    dataset_info['table_count'] = 0
                    dataset_info['billing_tables'] = []
                    dataset_info['has_billing_data'] = False
                
                datasets.append(dataset_info)
            
            return datasets
            
        except ImportError:
            self.logger.error("BigQuery library not available", "gcp")
            return []
        except Exception as e:
            self.logger.error(f"Error listing BigQuery datasets: {str(e)}", "gcp")
            return []

    def _create_bigquery_dataset_if_needed(self, project_id: str, dataset_id: str, location: str = "US") -> tuple[bool, str]:
        """Create BigQuery dataset for billing export if it doesn't exist."""
        try:
            from google.cloud import bigquery
            
            client = bigquery.Client(project=project_id)
            dataset_ref = f"{project_id}.{dataset_id}"
            
            # Check if dataset already exists
            try:
                existing_dataset = client.get_dataset(dataset_ref)
                return True, f"✅ Dataset '{dataset_id}' already exists in {existing_dataset.location}"
            except Exception:
                pass  # Dataset doesn't exist, create it
            
            # Validate location
            valid_locations = ["US", "EU", "asia-east1", "asia-northeast1", "asia-southeast1", 
                             "australia-southeast1", "europe-north1", "europe-west1", "europe-west2", 
                             "europe-west3", "europe-west4", "europe-west6", "northamerica-northeast1",
                             "southamerica-east1", "us-central1", "us-east1", "us-east4", "us-west1", 
                             "us-west2", "us-west3", "us-west4"]
            
            if location not in valid_locations:
                return False, f"❌ Invalid location '{location}'. Valid options: {', '.join(valid_locations[:10])}..."
            
            # Create the dataset
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = location
            dataset.description = f"GCP billing export data for cost analysis (Created by Autocost Controller)"
            
            # Set dataset to auto-delete tables after 400 days (optional)
            dataset.default_table_expiration_ms = 400 * 24 * 60 * 60 * 1000
            
            # Add labels for identification
            dataset.labels = {
                "created_by": "autocost_controller",
                "purpose": "billing_export",
                "auto_created": "true"
            }
            
            created_dataset = client.create_dataset(dataset, timeout=30)
            self.logger.info(f"✅ Created BigQuery dataset: {created_dataset.dataset_id} in {location}", "gcp")
            return True, f"✅ Successfully created dataset '{dataset_id}' in {location}"
            
        except Exception as e:
            error_details = f"Failed to create BigQuery dataset '{dataset_id}' in {location}: {str(e)}"
            self.logger.error(error_details, "gcp")
            return False, f"❌ {error_details}"
