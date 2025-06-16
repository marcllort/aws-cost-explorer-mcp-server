# Provider Development Guide

This guide walks you through implementing a new cloud provider for Autocost Controller. We'll use Google Cloud Platform (GCP) as an example, but the same pattern applies to Azure, DataDog, or any other provider.

## Quick Start

To add a new provider, follow these steps:

1. **Create the provider structure**
2. **Implement the provider class**
3. **Add authentication handling**
4. **Create MCP tools**
5. **Register with the system**
6. **Test and document**

## Step 1: Create Provider Structure

First, create the directory structure for your provider:

```bash
mkdir -p autocost_controller/providers/gcp
touch autocost_controller/providers/gcp/__init__.py
touch autocost_controller/providers/gcp/provider.py
touch autocost_controller/providers/gcp/client.py
touch autocost_controller/providers/gcp/auth.py
touch autocost_controller/providers/gcp/models.py
```

## Step 2: Implement the Provider Class

### Base Provider Interface

All providers must inherit from `BaseProvider` and implement these methods:

```python
# autocost_controller/providers/gcp/provider.py
from typing import List, Optional
from ...core.provider_manager import BaseProvider
from ...core.models import ProviderType, ProviderStatus
from ...core.config import Config
from ...core.logger import AutocostLogger
from .client import GCPClient
from .auth import GCPAuth

class GCPProvider(BaseProvider):
    """Google Cloud Platform provider for cost analysis."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        super().__init__(config, logger)
        self.auth = GCPAuth(config, logger)
        self.client: Optional[GCPClient] = None
        self._initialize()
    
    def get_provider_name(self) -> ProviderType:
        """Return the provider name."""
        return "gcp"
    
    def validate_configuration(self) -> ProviderStatus:
        """Validate GCP configuration and return status."""
        try:
            # Check required environment variables
            if not self.auth.validate_credentials():
                return ProviderStatus(
                    status="error",
                    error="GCP credentials not configured",
                    capabilities=[]
                )
            
            # Test API access
            if not self.auth.test_permissions():
                return ProviderStatus(
                    status="error", 
                    error="Insufficient GCP permissions",
                    capabilities=[]
                )
            
            return ProviderStatus(
                status="ready",
                error=None,
                capabilities=self.get_capabilities()
            )
            
        except Exception as e:
            return ProviderStatus(
                status="error",
                error=f"GCP validation failed: {str(e)}",
                capabilities=[]
            )
    
    def get_capabilities(self) -> List[str]:
        """Return list of supported capabilities."""
        return [
            "cost_analysis",
            "billing_export",
            "bigquery_analysis", 
            "compute_optimization",
            "storage_lifecycle",
            "committed_use_discounts"
        ]
    
    async def test_connection(self) -> bool:
        """Test connection to GCP APIs."""
        try:
            if not self.client:
                self.client = GCPClient(self.auth, self.logger)
            
            # Test basic API call
            projects = await self.client.list_projects()
            self.logger.info(f"GCP connection test passed - found {len(projects)} projects")
            return True
            
        except Exception as e:
            self.logger.error(f"GCP connection test failed: {e}")
            return False
    
    def _initialize(self):
        """Initialize the GCP provider."""
        try:
            if self.auth.validate_credentials():
                self.client = GCPClient(self.auth, self.logger)
                self.logger.provider_status("gcp", "ready", "Client initialized")
            else:
                self.logger.provider_status("gcp", "error", "Invalid credentials")
        except Exception as e:
            self.logger.provider_status("gcp", "error", f"Initialization failed: {e}")
    
    def get_client(self, service: str = "billing") -> 'GCPClient':
        """Get the GCP client for API calls."""
        if not self.client:
            raise RuntimeError("GCP provider not properly initialized")
        return self.client
```

## Step 3: Implement Authentication

### Authentication Handler

```python
# autocost_controller/providers/gcp/auth.py
import os
import json
from typing import Optional
from google.auth import default
from google.auth.credentials import Credentials
from ...core.config import Config
from ...core.logger import AutocostLogger

class GCPAuth:
    """Handle GCP authentication and credentials."""
    
    def __init__(self, config: Config, logger: AutocostLogger):
        self.config = config
        self.logger = logger
        self.credentials: Optional[Credentials] = None
        self.project_id: Optional[str] = None
    
    def validate_credentials(self) -> bool:
        """Validate GCP credentials are available."""
        try:
            # Method 1: Service Account Key File
            if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                key_file = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
                if os.path.exists(key_file):
                    self.credentials, self.project_id = default()
                    self.logger.info("Using GCP service account from key file")
                    return True
            
            # Method 2: Application Default Credentials (ADC)
            try:
                self.credentials, self.project_id = default()
                self.logger.info("Using GCP Application Default Credentials")
                return True
            except Exception:
                pass
            
            # Method 3: Environment variables
            if self._validate_env_credentials():
                self.logger.info("Using GCP credentials from environment")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"GCP credential validation failed: {e}")
            return False
    
    def _validate_env_credentials(self) -> bool:
        """Validate environment-based credentials."""
        required_vars = [
            "GCP_PROJECT_ID",
            "GCP_CLIENT_EMAIL", 
            "GCP_PRIVATE_KEY"
        ]
        
        return all(os.environ.get(var) for var in required_vars)
    
    def test_permissions(self) -> bool:
        """Test if credentials have required permissions."""
        try:
            # Test billing API access
            from google.cloud import billing
            
            client = billing.CloudBillingClient(credentials=self.credentials)
            
            # Try to list billing accounts
            accounts = list(client.list_billing_accounts())
            
            if not accounts:
                self.logger.warning("No GCP billing accounts found")
                return False
            
            self.logger.info(f"Found {len(accounts)} GCP billing accounts")
            return True
            
        except Exception as e:
            self.logger.error(f"GCP permission test failed: {e}")
            return False
    
    def get_credentials(self) -> Credentials:
        """Get the current credentials."""
        if not self.credentials:
            raise RuntimeError("GCP credentials not initialized")
        return self.credentials
    
    def get_project_id(self) -> str:
        """Get the current project ID."""
        if not self.project_id:
            self.project_id = os.environ.get("GCP_PROJECT_ID", "")
        return self.project_id
```

## Step 4: Implement API Client

### Client Wrapper

```python
# autocost_controller/providers/gcp/client.py
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google.cloud import billing, bigquery, monitoring
from ...core.logger import AutocostLogger
from .auth import GCPAuth

class GCPClient:
    """GCP API client wrapper."""
    
    def __init__(self, auth: GCPAuth, logger: AutocostLogger):
        self.auth = auth
        self.logger = logger
        self.credentials = auth.get_credentials()
        self.project_id = auth.get_project_id()
        
        # Initialize clients
        self.billing_client = billing.CloudBillingClient(credentials=self.credentials)
        self.bigquery_client = bigquery.Client(
            project=self.project_id, 
            credentials=self.credentials
        )
        self.monitoring_client = monitoring.MetricServiceClient(credentials=self.credentials)
    
    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all accessible GCP projects."""
        try:
            from google.cloud import resourcemanager
            
            client = resourcemanager.ProjectsClient(credentials=self.credentials)
            projects = []
            
            for project in client.list_projects():
                projects.append({
                    "project_id": project.project_id,
                    "name": project.name,
                    "state": project.state.name
                })
            
            return projects
            
        except Exception as e:
            self.logger.error(f"Failed to list GCP projects: {e}")
            raise
    
    async def get_billing_data(
        self, 
        days: int = 7,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get billing data for specified period."""
        try:
            # Use BigQuery to query billing export data
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Billing data query
            query = f"""
            SELECT 
                service.description as service_name,
                sku.description as sku_description,
                project.id as project_id,
                SUM(cost) as total_cost,
                currency,
                usage_start_time,
                usage_end_time
            FROM `{self.project_id}.billing_export.gcp_billing_export_v1_*`
            WHERE _PARTITIONTIME >= '{start_date}'
              AND _PARTITIONTIME <= '{end_date}'
              {"AND project.id = '" + project_id + "'" if project_id else ""}
            GROUP BY 
                service_name, sku_description, project_id, 
                currency, usage_start_time, usage_end_time
            ORDER BY total_cost DESC
            """
            
            query_job = self.bigquery_client.query(query)
            results = query_job.result()
            
            billing_data = []
            for row in results:
                billing_data.append({
                    "service": row.service_name,
                    "sku": row.sku_description,
                    "project_id": row.project_id,
                    "cost": float(row.total_cost),
                    "currency": row.currency,
                    "start_time": row.usage_start_time,
                    "end_time": row.usage_end_time
                })
            
            return {
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_records": len(billing_data),
                "billing_data": billing_data
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get GCP billing data: {e}")
            raise
    
    async def get_compute_usage(self, days: int = 7) -> Dict[str, Any]:
        """Get Compute Engine usage and costs."""
        try:
            # Implementation for getting compute usage
            # This would query the monitoring API for instance metrics
            pass
        except Exception as e:
            self.logger.error(f"Failed to get GCP compute usage: {e}")
            raise
```

## Step 5: Create Data Models

### Provider-Specific Models

```python
# autocost_controller/providers/gcp/models.py
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class GCPBillingAccount(BaseModel):
    """GCP billing account information."""
    account_id: str
    display_name: str
    open: bool
    master_billing_account: Optional[str] = None

class GCPProject(BaseModel):
    """GCP project information."""
    project_id: str
    name: str
    project_number: str
    state: str
    billing_account: Optional[str] = None

class GCPCostItem(BaseModel):
    """Individual cost item from GCP billing."""
    service: str
    sku: str
    project_id: str
    cost: float
    currency: str
    usage_start_time: datetime
    usage_end_time: datetime
    location: Optional[str] = None
    labels: Optional[dict] = None

class GCPCostAnalysis(BaseModel):
    """Complete GCP cost analysis results."""
    period_days: int
    start_date: str
    end_date: str
    total_cost: float
    currency: str
    cost_by_service: List[dict]
    cost_by_project: List[dict]
    cost_by_location: List[dict]
    optimization_opportunities: List[dict]
```

## Step 6: Create MCP Tools

### Tool Registration

```python
# autocost_controller/tools/gcp_tools.py
from typing import Optional
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
from ..core.config import Config
from ..core.logger import AutocostLogger
from ..core.provider_manager import ProviderManager

def register_gcp_tools(
    mcp: FastMCP, 
    provider_manager: ProviderManager, 
    config: Config, 
    logger: AutocostLogger
) -> None:
    """Register GCP cost analysis tools."""
    
    gcp_provider = provider_manager.get_provider("gcp")
    if not gcp_provider:
        logger.warning("GCP provider not available, skipping tools registration")
        return
    
    logger.info("🔧 Registering GCP Cloud Billing tools...")
    
    @mcp.tool()
    async def gcp_billing_analyze_costs(
        days: int = 7,
        project_id: Optional[str] = None,
        group_by: str = "service"
    ) -> str:
        """GCP Cloud Billing: Analyze costs with detailed breakdown."""
        logger.info(f"🔍 Analyzing GCP costs for {days} days...")
        
        try:
            client = gcp_provider.get_client("billing")
            
            # Get billing data
            billing_data = await client.get_billing_data(days, project_id)
            
            # Process and format results
            total_cost = sum(item["cost"] for item in billing_data["billing_data"])
            
            # Group by specified dimension
            grouped_data = {}
            for item in billing_data["billing_data"]:
                key = item.get(group_by, "unknown")
                if key not in grouped_data:
                    grouped_data[key] = 0
                grouped_data[key] += item["cost"]
            
            # Sort by cost
            sorted_data = sorted(
                grouped_data.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # Format response
            response = f"🔍 **GCP COST ANALYSIS ({days} days)**\n\n"
            response += f"💰 **Total Cost**: ${total_cost:.2f}\n"
            response += f"📊 **Average Daily**: ${total_cost/days:.2f}\n\n"
            
            response += f"📈 **Top {group_by.title()}s by Cost:**\n"
            for i, (name, cost) in enumerate(sorted_data[:10], 1):
                percentage = (cost / total_cost) * 100
                response += f"{i:2d}. {name}: ${cost:.2f} ({percentage:.1f}%)\n"
            
            # Add recommendations
            response += "\n💡 **Optimization Opportunities:**\n"
            response += "• Enable committed use discounts for compute workloads\n"
            response += "• Review storage lifecycle policies\n"
            response += "• Consider preemptible instances for batch workloads\n"
            
            logger.cost_analysis_summary("gcp", total_cost, days, 3)
            return response
            
        except Exception as e:
            logger.error(f"GCP cost analysis failed: {e}", provider="gcp")
            return f"❌ Error analyzing GCP costs: {str(e)}"
    
    @mcp.tool()
    async def gcp_billing_list_projects(
        include_costs: bool = True
    ) -> str:
        """GCP Cloud Billing: List all accessible projects with optional cost data."""
        logger.info("📋 Listing GCP projects...")
        
        try:
            client = gcp_provider.get_client("billing")
            
            projects = await client.list_projects()
            
            response = f"📋 **GCP PROJECTS** ({len(projects)} found)\n\n"
            
            for i, project in enumerate(projects, 1):
                response += f"{i:2d}. **{project['name']}**\n"
                response += f"    Project ID: {project['project_id']}\n"
                response += f"    State: {project['state']}\n"
                
                if include_costs:
                    # Get costs for this project
                    try:
                        billing_data = await client.get_billing_data(
                            days=7, 
                            project_id=project['project_id']
                        )
                        total_cost = sum(
                            item["cost"] for item in billing_data["billing_data"]
                        )
                        response += f"    7-day cost: ${total_cost:.2f}\n"
                    except:
                        response += f"    7-day cost: Unable to retrieve\n"
                
                response += "\n"
            
            return response
            
        except Exception as e:
            logger.error(f"GCP project listing failed: {e}", provider="gcp")
            return f"❌ Error listing GCP projects: {str(e)}"
    
    @mcp.tool()
    async def gcp_billing_optimize_bigquery(
        project_id: Optional[str] = None,
        days: int = 30
    ) -> str:
        """GCP Cloud Billing: Analyze and optimize BigQuery costs."""
        logger.info(f"🔍 Analyzing BigQuery optimization for {days} days...")
        
        try:
            # Implementation for BigQuery cost optimization
            response = "🔍 **BIGQUERY OPTIMIZATION ANALYSIS**\n\n"
            response += "💡 **Recommendations:**\n"
            response += "• Use partitioned tables to reduce query costs\n"
            response += "• Implement query result caching\n"
            response += "• Review and optimize expensive queries\n"
            response += "• Consider using materialized views for frequent queries\n"
            response += "• Set up slot reservations for predictable workloads\n"
            
            return response
            
        except Exception as e:
            logger.error(f"BigQuery optimization failed: {e}", provider="gcp")
            return f"❌ Error analyzing BigQuery optimization: {str(e)}"
```

## Step 7: Register Provider in System

### Update Provider Manager

The provider is automatically loaded by the provider manager if the import is available. Make sure your provider class is importable:

```python
# autocost_controller/providers/gcp/__init__.py
from .provider import GCPProvider

__all__ = ["GCPProvider"]
```

### Update Tool Registration

```python
# autocost_controller/tools/__init__.py
def register_core_tools(mcp: FastMCP, provider_manager: ProviderManager, config: Config, logger: AutocostLogger) -> None:
    # ... existing core tools ...
    
    # Register provider-specific tools
    enabled_providers = get_enabled_providers()
    
    if "aws" in enabled_providers:
        from .aws_tools import register_aws_tools
        register_aws_tools(mcp, provider_manager, config, logger)
    
    if "gcp" in enabled_providers:
        from .gcp_tools import register_gcp_tools
        register_gcp_tools(mcp, provider_manager, config, logger)
```

### Update Server Registration

```python
# server_manual.py
# Add to the main() function:

if "gcp" in enabled_providers:
    from autocost_controller.tools.gcp_tools import register_gcp_tools
    register_gcp_tools(mcp, provider_manager, config, logger)
```

## Step 8: Configuration and Environment

### Environment Variables

Add support for GCP-specific environment variables:

```python
# .env example
AUTOCOST_PROVIDERS=aws,gcp
GCP_PROJECT_ID=my-project-123
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Or for environment-based auth:
GCP_CLIENT_EMAIL=service-account@project.iam.gserviceaccount.com
GCP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
```

### Required Dependencies

Update `pyproject.toml`:

```toml
[project.optional-dependencies]
gcp = [
    "google-cloud-billing>=1.12.0",
    "google-cloud-bigquery>=3.11.0",
    "google-cloud-monitoring>=2.16.0",
    "google-cloud-resource-manager>=1.10.4",
]
```

## Step 9: Testing

### Unit Tests

Create tests for your provider:

```python
# tests/providers/test_gcp_provider.py
import pytest
from unittest.mock import Mock, patch
from autocost_controller.providers.gcp.provider import GCPProvider
from autocost_controller.core.config import Config
from autocost_controller.core.logger import AutocostLogger

class TestGCPProvider:
    def setup_method(self):
        self.config = Config()
        self.logger = AutocostLogger("test")
        self.provider = GCPProvider(self.config, self.logger)
    
    def test_provider_name(self):
        assert self.provider.get_provider_name() == "gcp"
    
    def test_capabilities(self):
        capabilities = self.provider.get_capabilities()
        assert "cost_analysis" in capabilities
        assert "billing_export" in capabilities
    
    @patch.dict("os.environ", {"GOOGLE_APPLICATION_CREDENTIALS": "/fake/path.json"})
    @patch("os.path.exists", return_value=True)
    @patch("google.auth.default")
    def test_validate_configuration_success(self, mock_default, mock_exists):
        mock_default.return_value = (Mock(), "test-project")
        
        with patch.object(self.provider.auth, 'test_permissions', return_value=True):
            status = self.provider.validate_configuration()
            assert status.status == "ready"
            assert status.error is None
    
    async def test_connection_failure(self):
        # Test connection failure scenario
        result = await self.provider.test_connection()
        # This should fail without proper credentials
        assert result is False
```

### Integration Tests

```python
# tests/integration/test_gcp_integration.py
import pytest
import os
from autocost_controller.providers.gcp.provider import GCPProvider

@pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="GCP credentials not available"
)
class TestGCPIntegration:
    async def test_real_gcp_connection(self):
        # Test with real GCP credentials
        provider = GCPProvider(Config(), AutocostLogger("test"))
        result = await provider.test_connection()
        assert result is True
```

## Step 10: Documentation

### Update README

Add GCP configuration to the main README:

```markdown
#### GCP Authentication Methods

##### 1. Service Account Key File
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GCP_PROJECT_ID=my-project-123
```

##### 2. Application Default Credentials
```bash
gcloud auth application-default login
export GCP_PROJECT_ID=my-project-123
```

### Required GCP Permissions

Your service account needs these IAM roles:
- `roles/billing.viewer`
- `roles/bigquery.user`
- `roles/monitoring.viewer`
- `roles/resourcemanager.projectViewer`
```

## Checklist

Before submitting your provider implementation:

- [ ] Provider class inherits from `BaseProvider`
- [ ] All required methods are implemented
- [ ] Authentication supports multiple methods
- [ ] API client handles errors gracefully
- [ ] Tools follow naming convention: `gcp_{category}_{action}`
- [ ] Environment variables are documented
- [ ] Dependencies are added to `pyproject.toml`
- [ ] Unit tests cover main functionality
- [ ] Integration tests work with real credentials
- [ ] Documentation is updated
- [ ] Error messages are user-friendly
- [ ] Logging uses the AutocostLogger properly
- [ ] No hardcoded values or secrets

## Advanced Features

### Cross-Provider Analysis

Once multiple providers are implemented, you can create cross-provider tools:

```python
@mcp.tool()
async def compare_cloud_costs(
    providers: List[str] = ["aws", "gcp"],
    days: int = 30
) -> str:
    """Compare costs across multiple cloud providers."""
    # Implementation for cross-cloud comparison
```

### Optimization Recommendations

Implement AI-powered optimization suggestions:

```python
@mcp.tool()
async def gcp_optimization_recommendations(
    project_id: str,
    include_rightsizing: bool = True
) -> str:
    """Get AI-powered optimization recommendations for GCP resources."""
    # Use cost data + usage patterns to generate recommendations
```

## Getting Help

- Study the AWS provider implementation for patterns
- Check the `.cursorrules` file for coding standards
- Test with `python server_manual.py --test`
- Use the AutocostLogger for consistent error reporting
- Follow the provider interface exactly as defined in `BaseProvider`

This pattern ensures consistency across all providers and makes the system easily extensible for new cloud platforms. 