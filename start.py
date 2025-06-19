#!/usr/bin/env python3
"""
Autocost Controller - Interactive Setup & Auto-Installation

This script provides an interactive setup wizard for configuring the
multi-cloud cost analysis platform with auto-installation of dependencies.
"""

import os
import sys
import json
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Rich imports for beautiful terminal interface
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.columns import Columns
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("📦 Installing rich for better interface...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.columns import Columns
    from rich.align import Align

console = Console()

# Configuration paths for different platforms
CLAUDE_DESKTOP_CONFIGS = {
    "darwin": "~/Library/Application Support/Claude/claude_desktop_config.json",
    "win32": "~/AppData/Roaming/Claude/claude_desktop_config.json",
    "linux": "~/.config/Claude/claude_desktop_config.json"
}

CURSOR_CONFIGS = {
    "darwin": "~/Library/Application Support/Cursor/User/settings.json",
    "win32": "~/AppData/Roaming/Cursor/User/settings.json", 
    "linux": "~/.config/Cursor/User/settings.json"
}

class AutocostSetup:
    def __init__(self):
        self.console = console
        self.project_root = Path(__file__).parent
        self.config_data = {}
        self.provider_endpoints = {}
        
    def get_python_executable(self) -> str:
        """Get the path to the current Python executable."""
        return sys.executable
    
    def _get_gcp_env_vars(self) -> Dict[str, str]:
        """Get GCP environment variables from saved credentials file."""
        env_vars = {}
        
        try:
            creds_file = Path(".gcp_credentials.json")
            if creds_file.exists():
                with open(creds_file, 'r') as f:
                    creds_data = json.load(f)
                
                # Add project ID if available - check multiple possible field names
                project_id = (creds_data.get("project_id") or 
                             creds_data.get("quota_project_id") or 
                             creds_data.get("default_project_id"))
                if project_id:
                    env_vars["GCP_PROJECT_ID"] = project_id
                
                # Add organization ID if available
                if creds_data.get("organization_id"):
                    env_vars["GCP_ORGANIZATION_ID"] = creds_data["organization_id"]
                    
        except Exception as e:
            self.console.print(f"⚠️ Could not read GCP credentials for environment variables: {e}", style="yellow")
        
        return env_vars

    def show_banner(self):
        """Display the enhanced startup banner."""
        banner_text = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    🚀 AUTOCOST CONTROLLER 🚀                 ║
    ║                                                              ║
    ║           Multi-Cloud Cost Optimization Platform            ║
    ║                                                              ║
    ║  🔧 Interactive Setup & Auto-Installation Wizard 🔧         ║
    ╚══════════════════════════════════════════════════════════════╝
        """
        
        self.console.print(Panel(
            banner_text,
            style="bold blue",
            border_style="bright_blue"
        ))
        
        features = [
            "✅ Multi-provider cost analysis (AWS, GCP, Azure, DataDog)",
            "🔧 Provider-specific endpoints for focused analysis", 
            "📊 Performance insights and optimization recommendations",
            "🤖 Auto-installation for Claude Desktop & Cursor",
            "🏷️ Advanced tagging and cost allocation",
            "💡 AI-powered cost optimization suggestions"
        ]
        
        self.console.print(Panel(
            "\n".join(features),
            title="🌟 Key Features",
            style="green"
        ))

    def check_python_version(self) -> bool:
        """Check if Python version is compatible."""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.console.print("❌ Python 3.8+ required. Current version: {}.{}.{}".format(
                version.major, version.minor, version.micro
            ), style="red")
            return False
        
        self.console.print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible", style="green")
        return True

    def check_and_install_dependencies(self) -> bool:
        """Check and install required dependencies."""
        required_packages = [
            "boto3", "mcp", "pydantic", "python-dotenv", "rich"
        ]
        
        missing_packages = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("🔍 Checking dependencies...", total=len(required_packages))
            
            for package in required_packages:
                try:
                    __import__(package.replace("-", "_"))
                    progress.console.print(f"✅ {package}", style="green")
                except ImportError:
                    missing_packages.append(package)
                    progress.console.print(f"❌ {package} - Missing", style="red")
                progress.advance(task)
        
        if missing_packages:
            self.console.print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
            
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "--upgrade"
                ] + missing_packages)
                self.console.print("✅ All dependencies installed successfully!", style="green")
                return True
            except subprocess.CalledProcessError as e:
                self.console.print(f"❌ Failed to install dependencies: {e}", style="red")
                return False
        
        self.console.print("✅ All dependencies are already installed!", style="green")
        return True

    def configure_providers(self) -> Dict[str, bool]:
        """Configure cloud providers with enhanced options."""
        self.console.print("\n" + "="*60)
        self.console.print("🔧 PROVIDER CONFIGURATION", style="bold blue")
        self.console.print("="*60)
        
        providers_config = {}
        
        # AWS Configuration
        aws_enabled = Confirm.ask("🔶 Enable AWS Cost Explorer?", default=True)
        providers_config["aws"] = aws_enabled
        
        if aws_enabled:
            self.configure_aws()
        
        # GCP Configuration
        gcp_enabled = Confirm.ask("🔵 Enable Google Cloud Platform?", default=True)
        providers_config["gcp"] = gcp_enabled
        
        if gcp_enabled:
            self.configure_gcp()
        
        # Azure Configuration (placeholder)
        azure_enabled = Confirm.ask("🔷 Enable Microsoft Azure? (Coming Soon)", default=False)
        providers_config["azure"] = azure_enabled
        
        if azure_enabled:
            self.console.print("🚧 Azure integration coming soon! Configuration saved for future use.", style="yellow")
        
        # DataDog Configuration (placeholder)
        datadog_enabled = Confirm.ask("🐕 Enable DataDog monitoring? (Coming Soon)", default=False)
        providers_config["datadog"] = datadog_enabled
        
        if datadog_enabled:
            self.console.print("🚧 DataDog integration coming soon! Configuration saved for future use.", style="yellow")
        
        return providers_config

    def configure_aws(self):
        """Configure AWS with enhanced credential checking."""
        self.console.print("\n🔶 AWS CONFIGURATION", style="bold yellow")
        
        # Check for existing credentials
        aws_configured = self.check_aws_credentials()
        
        if not aws_configured:
            self.console.print("❌ AWS credentials not found or invalid", style="red")
            
            setup_method = Prompt.ask(
                "Choose AWS setup method",
                choices=["profile", "environment", "role", "skip"],
                default="profile"
            )
            
            if setup_method == "profile":
                self.setup_aws_profile()
            elif setup_method == "environment":
                self.setup_aws_env()
            elif setup_method == "role":
                self.setup_aws_role()
            elif setup_method == "skip":
                self.console.print("⚠️ Skipping AWS setup. Configure manually later.", style="yellow")
                return
        
        # Show required permissions
        if Confirm.ask("📋 Show required AWS IAM permissions?", default=False):
            self.show_iam_instructions()
        
        # Test credentials again
        final_check = self.check_aws_credentials()
        if final_check:
            self.console.print("✅ AWS credentials configured successfully!", style="green")
            
            # Save current credentials for Claude Desktop
            if Confirm.ask("💾 Save current AWS credentials for future use?", default=True):
                try:
                    # Save AWS credentials specifically
                    subprocess.run([sys.executable, "save_credentials.py", "--provider", "aws"], 
                                 cwd=self.project_root, check=True)
                    self.console.print("✅ AWS credentials saved successfully", style="green")
                except Exception as e:
                    self.console.print(f"⚠️ Could not save AWS credentials: {e}", style="yellow")
        else:
            self.console.print("❌ AWS credentials still not working", style="red")

    def check_aws_credentials(self) -> bool:
        """Enhanced AWS credential validation."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # Try to create a Cost Explorer client
            session = boto3.Session()
            ce_client = session.client('ce', region_name='us-east-1')
            
            # Test with a simple API call
            ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': '2024-01-01',
                    'End': '2024-01-02'
                },
                Granularity='DAILY',
                Metrics=['BlendedCost']
            )
            
            # Get account info
            sts_client = session.client('sts')
            identity = sts_client.get_caller_identity()
            
            self.console.print(f"✅ AWS Account: {identity.get('Account', 'Unknown')}", style="green")
            self.console.print(f"✅ User/Role: {identity.get('Arn', 'Unknown').split('/')[-1]}", style="green")
            
            return True
            
        except NoCredentialsError:
            self.console.print("❌ No AWS credentials found", style="red")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'UnauthorizedOperation':
                self.console.print("❌ AWS credentials lack Cost Explorer permissions", style="red")
            elif error_code == 'TokenRefreshRequired':
                self.console.print("❌ AWS credentials expired", style="red")
            else:
                self.console.print(f"❌ AWS error: {error_code}", style="red")
            return False
        except Exception as e:
            self.console.print(f"❌ AWS connection error: {str(e)}", style="red")
            return False

    def setup_aws_profile(self):
        """Setup AWS using profiles."""
        self.console.print("\n🔧 Setting up AWS via profiles...")
        
        profile_name = Prompt.ask("Enter AWS profile name", default="default")
        region = Prompt.ask("Enter AWS region", default="us-east-1")
        
        # Create/update AWS config
        aws_dir = Path.home() / ".aws"
        aws_dir.mkdir(exist_ok=True)
        
        config_file = aws_dir / "config"
        credentials_file = aws_dir / "credentials"
        
        self.console.print(f"📝 Please configure your AWS credentials in {credentials_file}")
        self.console.print("You can use 'aws configure' or edit the files manually")
        
        # Set environment variable for this session
        os.environ['AWS_PROFILE'] = profile_name
        os.environ['AWS_DEFAULT_REGION'] = region

    def setup_aws_env(self):
        """Setup AWS using environment variables."""
        self.console.print("\n🔧 Setting up AWS via environment variables...")
        
        access_key = Prompt.ask("Enter AWS Access Key ID")
        secret_key = Prompt.ask("Enter AWS Secret Access Key", password=True)
        session_token = Prompt.ask("Enter AWS Session Token (optional, press Enter to skip)", default="")
        region = Prompt.ask("Enter AWS region", default="us-east-1")
        
        # Set environment variables
        os.environ['AWS_ACCESS_KEY_ID'] = access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
        if session_token:
            os.environ['AWS_SESSION_TOKEN'] = session_token
        os.environ['AWS_DEFAULT_REGION'] = region
        
        self.console.print("✅ Environment variables set for this session", style="green")

    def setup_aws_role(self):
        """Setup AWS using role assumption (configurable)."""
        self.console.print("\n🔧 Setting up AWS via role assumption...")
        
        self.console.print("This method is for users who need to assume roles for AWS access.")
        self.console.print("Examples: SAML federation, cross-account roles, etc.")
        
        # Get user's specific setup
        auth_method = Prompt.ask(
            "What authentication method do you use?",
            choices=["saml", "oidc", "cross-account", "other"],
            default="other"
        )
        
        if auth_method == "saml":
            self.console.print("\n🔐 SAML Federation Setup")
            saml_provider = Prompt.ask("Enter your SAML provider name (e.g., 'okta', 'adfs')")
            role_arn = Prompt.ask("Enter the role ARN to assume")
            profile_name = Prompt.ask("Enter profile name for this role", default=f"{saml_provider}_role")
            
            self.console.print(f"\n📋 **Manual Setup Required:**")
            self.console.print(f"1. Configure your SAML provider authentication")
            self.console.print(f"2. Use a tool like aws-vault, saml2aws, or aws-cli with SAML")
            self.console.print(f"3. Example command might be:")
            self.console.print(f"   saml2aws login --profile {profile_name}")
            self.console.print(f"   OR")
            self.console.print(f"   aws-vault exec {profile_name} -- aws sts get-caller-identity")
            
            # Save configuration hint for later
            self.config_data['aws_auth_method'] = 'saml'
            self.config_data['aws_role_arn'] = role_arn
            self.config_data['aws_profile'] = profile_name
            
        elif auth_method == "cross-account":
            self.console.print("\n🔗 Cross-Account Role Setup")
            source_profile = Prompt.ask("Enter source profile name", default="default")
            role_arn = Prompt.ask("Enter the cross-account role ARN")
            profile_name = Prompt.ask("Enter profile name for this role", default="cross_account_role")
            
            # Create AWS config entry
            aws_dir = Path.home() / ".aws"
            aws_dir.mkdir(exist_ok=True)
            config_file = aws_dir / "config"
            
            config_entry = f"""
[profile {profile_name}]
role_arn = {role_arn}
source_profile = {source_profile}
"""
            
            self.console.print(f"\n📝 Add this to your {config_file}:")
            self.console.print(config_entry)
            
            self.config_data['aws_auth_method'] = 'cross_account'
            self.config_data['aws_role_arn'] = role_arn
            self.config_data['aws_profile'] = profile_name
            
        else:
            self.console.print("\n🔧 Custom Authentication Setup")
            self.console.print("Please configure your specific authentication method manually.")
            
            auth_command = Prompt.ask(
                "Enter the command you use to authenticate (optional)",
                default=""
            )
            
            if auth_command:
                self.console.print(f"\n📋 **Your Authentication Command:**")
                self.console.print(f"   {auth_command}")
                self.console.print("\n💡 Run this command before starting the server")
                
                self.config_data['aws_auth_command'] = auth_command
        
        self.console.print("\n⚠️ **Important:** Make sure you authenticate before running the server!")
        self.console.print("The server will use whatever credentials are active in your shell.")

    def show_iam_instructions(self):
        """Show required IAM permissions."""
        iam_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ce:GetCostAndUsage",
                        "ce:GetDimensionValues",
                        "ce:GetReservationCoverage", 
                        "ce:GetReservationPurchaseRecommendation",
                        "ce:GetReservationUtilization",
                        "ce:GetUsageReport",
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:ListMetrics",
                        "ec2:DescribeInstances",
                        "ec2:DescribeInstanceTypes",
                        "ec2:DescribeRegions",
                        "ecs:ListClusters",
                        "ecs:ListServices",
                        "ecs:DescribeServices",
                        "sts:GetCallerIdentity"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        self.console.print("\n📋 **REQUIRED AWS IAM PERMISSIONS**", style="bold blue")
        self.console.print("Your AWS user/role needs these permissions:")
        
        # Display as formatted JSON
        policy_json = json.dumps(iam_policy, indent=2)
        syntax = Syntax(policy_json, "json", theme="monokai", line_numbers=True)
        self.console.print(syntax)
        
        self.console.print("\n💡 **Tips:**")
        self.console.print("• Attach this as a custom policy to your IAM user/role")
        self.console.print("• For read-only cost analysis, these permissions are safe")
        self.console.print("• Consider using AWS managed policies like 'CostExplorerReadOnlyAccess'")
        self.console.print("• For cross-account access, ensure the role trusts your account")

    def configure_gcp(self):
        """Configure GCP by reading saved credentials (consistent with AWS approach)."""
        self.console.print("\n🔵 GCP CONFIGURATION", style="bold blue")
        
        # Check for existing credentials
        gcp_configured = self.check_gcp_credentials()
        
        if not gcp_configured:
            self.console.print("❌ GCP credentials not found", style="red")
            self.console.print("\n💡 **Setup Instructions:**", style="bold blue")
            self.console.print("1. Run: python save_credentials_gcp.py [project_id] [--org-id ORGANIZATION_ID]")
            self.console.print("2. This will save your GCP credentials for the server to use")
            self.console.print("3. Come back and run this setup again")
            
            skip_gcp = Confirm.ask("Skip GCP setup for now?", default=True)
            if skip_gcp:
                self.console.print("⚠️ Skipping GCP setup. Run save_credentials_gcp.py first.", style="yellow")
                return
        
        # Read project ID and organization ID from saved credentials
        try:
            creds_file = Path(".gcp_credentials.json")
            if creds_file.exists():
                with open(creds_file, 'r') as f:
                    creds_data = json.load(f)
                
                # Display project information - check multiple possible field names
                project_id = (creds_data.get("project_id") or 
                             creds_data.get("quota_project_id") or 
                             creds_data.get("default_project_id"))
                if project_id:
                    project_name = creds_data.get("project_name", "Unknown")
                    self.console.print(f"✅ Project: {project_id} ({project_name})", style="green")
                    
                # Display organization information if available
                if creds_data.get("organization_id"):
                    org_id = creds_data["organization_id"]
                    org_source = creds_data.get("organization_source", "saved credentials")
                    self.config_data['gcp_organization_id'] = org_id
                    self.console.print(f"✅ Organization: {org_id} (from {org_source})", style="green")
                else:
                    self.console.print("ℹ️ No organization ID found - using project-level access", style="blue")
                
                # Display credential source
                cred_source = creds_data.get("source", "unknown")
                self.console.print(f"📊 Credential source: {cred_source}", style="cyan")
                    
        except Exception as e:
            self.console.print(f"⚠️ Could not read GCP credentials: {e}", style="yellow")
        
        # Show required permissions
        if Confirm.ask("📋 Show required GCP IAM permissions?", default=False):
            self.show_gcp_iam_instructions()
        
        # Note about billing export setup
        self.console.print("\n💡 **BigQuery Billing Export Setup**:", style="bold blue")
        self.console.print("🎯 For comprehensive cost analysis, run: gcp_setup_billing_export")
        self.console.print("📊 This interactive guide explains why you need billing export and walks you through setup")
        self.console.print("🔧 Includes automated dataset creation and detailed console instructions")
        self.console.print("💰 Enables advanced cost optimization and resource-level insights")

    def check_gcp_credentials(self) -> bool:
        """Check if GCP credentials are configured and valid (similar to AWS approach)."""
        try:
            # Check for saved credentials file (similar to AWS approach)
            creds_file = Path(".gcp_credentials.json")
            if creds_file.exists():
                with open(creds_file, 'r') as f:
                    creds_data = json.load(f)
                    
                # Verify the credentials data looks valid
                if creds_data.get("project_id") and creds_data.get("source"):
                    self.console.print("✅ GCP credentials file found and appears valid", style="green")
                    return True
                else:
                    self.console.print("⚠️ GCP credentials file exists but appears incomplete", style="yellow")
                    return False
            else:
                self.console.print("❌ No saved GCP credentials found", style="red")
                self.console.print("💡 Run: python save_credentials_gcp.py [project_id]", style="blue")
                return False
                
        except Exception as e:
            self.console.print(f"❌ Error checking GCP credentials: {e}", style="red")
            return False

    def setup_gcp_application_default(self):
        """Set up GCP using application default credentials (deprecated - use save_credentials_gcp.py)."""
        self.console.print("\n📝 **DEPRECATED SETUP METHOD**", style="yellow")
        self.console.print("Please use the new simplified approach:")
        self.console.print("1. Run: python save_credentials_gcp.py [project_id]")
        self.console.print("2. This will handle all credential setup automatically")

    def setup_gcp_service_account(self):
        """Set up GCP using a service account key file (deprecated - use save_credentials_gcp.py)."""
        self.console.print("\n📝 **DEPRECATED SETUP METHOD**", style="yellow")
        self.console.print("Please use the new simplified approach:")
        self.console.print("1. Set GOOGLE_APPLICATION_CREDENTIALS to your service account key file")
        self.console.print("2. Run: python save_credentials_gcp.py [project_id]")
        self.console.print("3. This will handle all credential setup automatically")

    def show_gcp_iam_instructions(self):
        """Show required GCP IAM permissions based on saved credentials."""
        self.console.print("\n📋 Required GCP IAM Permissions:")
        
        # Check if organization access is configured from saved credentials
        has_org_id = False
        org_id = None
        
        try:
            creds_file = Path(".gcp_credentials.json")
            if creds_file.exists():
                with open(creds_file, 'r') as f:
                    creds_data = json.load(f)
                    if creds_data.get("organization_id"):
                        has_org_id = True
                        org_id = creds_data["organization_id"]
        except:
            # Fallback to config_data if file read fails
            has_org_id = 'gcp_organization_id' in self.config_data
            org_id = self.config_data.get('gcp_organization_id')
        
        if has_org_id and org_id:
            self.console.print("For ORGANIZATION-LEVEL access, your service account needs these roles:")
            self.console.print("• roles/billing.viewer (at organization level)")
            self.console.print("• roles/resourcemanager.organizationViewer")
            self.console.print("• roles/monitoring.viewer (at organization level)")
            self.console.print("• roles/bigquery.user (for billing export access)")
            self.console.print("• roles/resourcemanager.projectViewer (for project enumeration)")
            
            self.console.print(f"\n🏢 Organization ID: {org_id}")
            self.console.print("\n💡 To grant organization-level permissions:")
            self.console.print("1. Go to GCP Console → IAM & Admin → IAM")
            self.console.print("2. Select your organization at the top")
            self.console.print("3. Add your service account with the roles above")
        else:
            self.console.print("For PROJECT-LEVEL access, your service account needs these roles:")
            self.console.print("• roles/billing.viewer")
            self.console.print("• roles/monitoring.viewer")
            self.console.print("• roles/bigquery.user")
            self.console.print("• roles/resourcemanager.projectViewer")

    def configure_endpoints(self, providers_config: Dict[str, bool]) -> Dict[str, Dict]:
        """Configure provider-specific endpoints with environment variables."""
        self.console.print("\n" + "="*60)
        self.console.print("🎯 ENDPOINT CONFIGURATION", style="bold blue")
        self.console.print("="*60)
        
        endpoints = {}
        
        # Always create a unified endpoint if multiple providers are enabled
        enabled_providers = [name for name, enabled in providers_config.items() if enabled]
        
        if len(enabled_providers) > 1:
            endpoints["unified"] = {
                "name": "autocost-unified",
                "description": "Multi-provider cost analysis endpoint",
                "providers": enabled_providers,
                "environment": {
                    "AUTOCOST_ENDPOINT": "unified",
                    "AUTOCOST_PROVIDERS": ",".join(enabled_providers)
                }
            }
            
            # Add GCP environment variables to unified endpoint if configured
            if "gcp" in enabled_providers:
                gcp_env_vars = self._get_gcp_env_vars()
                endpoints["unified"]["environment"].update(gcp_env_vars)
        
        # Create individual provider endpoints
        for provider_name in enabled_providers:
            provider_display = provider_name.upper()
            endpoints[provider_name] = {
                "name": f"autocost-{provider_name}",
                "description": f"{provider_display} cost analysis endpoint",
                "providers": [provider_name],
                "environment": {
                    "AUTOCOST_ENDPOINT": provider_name,
                    "AUTOCOST_PROVIDERS": provider_name
                }
            }
            
            # Add provider-specific environment variables
            if provider_name == "aws":
                # Add AWS-specific configuration from user setup
                if 'aws_auth_method' in self.config_data:
                    endpoints[provider_name]["environment"]["AWS_AUTH_METHOD"] = self.config_data['aws_auth_method']
                if 'aws_profile' in self.config_data:
                    endpoints[provider_name]["environment"]["AWS_PROFILE"] = self.config_data['aws_profile']
                if 'aws_auth_command' in self.config_data:
                    endpoints[provider_name]["auth_command"] = self.config_data['aws_auth_command']
            elif provider_name == "gcp":
                # Add GCP-specific configuration from saved credentials
                gcp_env_vars = self._get_gcp_env_vars()
                endpoints[provider_name]["environment"].update(gcp_env_vars)
        
        # Show configuration summary
        table = Table(title="Configured Endpoints")
        table.add_column("Endpoint", style="cyan", no_wrap=True)
        table.add_column("Providers", style="magenta")
        table.add_column("Description", style="green")
        
        for endpoint_id, config in endpoints.items():
            providers_str = ", ".join(config["providers"])
            table.add_row(endpoint_id, providers_str, config["description"])
        
        self.console.print(table)
        
        return endpoints

    def configure_pre_run_scripts(self, endpoints: Dict[str, Dict]) -> Dict[str, Dict]:
        """Configure pre-run scripts for endpoints that need authentication setup."""
        self.console.print("\n" + "="*60)
        self.console.print("🔧 PRE-RUN SCRIPT CONFIGURATION", style="bold blue")
        self.console.print("="*60)
        
        self.console.print(
            "💡 Pre-run scripts execute before the MCP server starts.\n"
            "   Use them for authentication setup, environment preparation, etc.\n"
        )
        
        for endpoint_id, config in endpoints.items():
            providers = config["providers"]
            
            # Check if this endpoint needs pre-run scripts
            self.console.print(f"\n🌐 Endpoint: [cyan]{endpoint_id}[/cyan] (Providers: {', '.join(providers)})")
            
            needs_scripts = Confirm.ask(
                f"⚙️ Add pre-run scripts for {endpoint_id}?", 
                default=False
            )
            
            if needs_scripts:
                commands = []
                
                self.console.print("📝 Enter commands to run before starting the MCP server.")
                self.console.print("   Press Enter on empty line to finish.")
                
                # Special suggestions for AWS
                if "aws" in providers:
                    self.console.print("\n💡 [yellow]Common AWS commands:[/yellow]")
                    self.console.print("   • assume <PROFILE_NAME>")
                    self.console.print("   • unset AWS_SESSION_TOKEN AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY")
                    self.console.print("   • export AWS_PROFILE=your-profile")
                    self.console.print("\n⚠️  [red]Note: Run 'assume' first, then 'unset' to avoid conflicts[/red]")
                    self.console.print("")
                
                command_num = 1
                while True:
                    command = Prompt.ask(f"Command {command_num} (or press Enter to finish)", default="")
                    if not command.strip():
                        break
                    commands.append(command.strip())
                    command_num += 1
                
                config["pre_run_commands"] = commands
                
                if commands:
                    self.console.print(f"✅ Added {len(commands)} pre-run commands to {endpoint_id}")
                    for i, cmd in enumerate(commands, 1):
                        self.console.print(f"   {i}. {cmd}")
        
        return endpoints

    def create_wrapper_scripts(self, endpoints: Dict[str, Dict]):
        """Create wrapper scripts for endpoints with pre-run commands."""
        scripts_dir = self.project_root / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        
        for endpoint_id, config in endpoints.items():
            if config.get("pre_run_commands"):
                # Create wrapper script
                script_name = f"run_{endpoint_id}.py"
                script_path = scripts_dir / script_name
                
                python_executable = self.get_python_executable()
                main_script = str(self.project_root / "main.py")
                
                script_content = f'''#!/usr/bin/env python3
"""
Wrapper script for Autocost Controller endpoint: {endpoint_id}
Executes pre-run commands before starting the MCP server.
"""

import os
import sys
import subprocess
import logging

def setup_logging():
    """Setup logging to stderr to avoid polluting MCP stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    return logging.getLogger(__name__)

def run_command(command: str, logger) -> bool:
    """Run a shell command and return success status."""
    try:
        logger.info(f"🔧 Running pre-command: {{command}}")
        
        # Run command in shell to support shell built-ins and aliases
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Command succeeded: {{command}}")
            if result.stdout.strip():
                logger.info(f"Output: {{result.stdout.strip()}}")
            return True
        else:
            logger.error(f"❌ Command failed: {{command}}")
            logger.error(f"Error: {{result.stderr.strip()}}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ Command timed out: {{command}}")
        return False
    except Exception as e:
        logger.error(f"💥 Command error: {{command}} - {{e}}")
        return False

def main():
    """Main wrapper function."""
    logger = setup_logging()
    
    logger.info("🚀 Starting Autocost Controller wrapper for endpoint: {endpoint_id}")
    
    # Pre-run commands
    pre_commands = {config["pre_run_commands"]}
    
    if pre_commands:
        logger.info(f"🔧 Executing {{len(pre_commands)}} pre-run commands...")
        
        for i, command in enumerate(pre_commands, 1):
            logger.info(f"📝 Step {{i}}/{{len(pre_commands)}}: {{command}}")
            
            if not run_command(command, logger):
                logger.error(f"❌ Pre-command failed, aborting startup")
                sys.exit(1)
        
        logger.info("✅ All pre-commands completed successfully")
    
    # Start the main MCP server
    logger.info("🌐 Starting Autocost Controller MCP server...")
    
    try:
        # Execute the main script with the same arguments
        main_args = [
            "{python_executable}",
            "{main_script}",
            "--endpoint", "{endpoint_id}"
        ]
        
        # Add any additional arguments passed to this wrapper
        main_args.extend(sys.argv[1:])
        
        # Replace current process with the main script
        os.execvp(main_args[0], main_args)
        
    except Exception as e:
        logger.error(f"💥 Failed to start main server: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
                
                with open(script_path, 'w') as f:
                    f.write(script_content)
                
                # Make script executable on Unix systems
                if os.name != 'nt':
                    script_path.chmod(0o755)
                
                self.console.print(f"✅ Created wrapper script: {script_path}")
        
        self.console.print(f"📁 Wrapper scripts saved to: {scripts_dir}")

    def auto_install_integrations(self, endpoints: Dict[str, Dict]):
        """Auto-install MCP server configurations for Claude Desktop and Cursor."""
        self.console.print("\n" + "="*60)
        self.console.print("🤖 AUTO-INSTALLATION", style="bold blue")
        self.console.print("="*60)
        
        install_claude = Confirm.ask("📱 Auto-install for Claude Desktop?", default=True)
        install_cursor = Confirm.ask("🖱️ Auto-install for Cursor?", default=True)
        
        if install_claude:
            self.setup_claude_desktop(endpoints)
        
        if install_cursor:
            self.install_cursor(endpoints)

    def setup_claude_desktop(self, endpoints: Dict[str, Dict]):
        """Setup Claude Desktop with environment-based configurations."""
        if not Confirm.ask("🖥️ Setup Claude Desktop integration?", default=True):
            return
        
        self.console.print("\n🖥️ CLAUDE DESKTOP SETUP", style="bold blue")
        
        # Detect Claude Desktop config location
        config_paths = [
            Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",  # macOS
            Path.home() / ".config/claude/claude_desktop_config.json",  # Linux
            Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json"  # Windows
        ]
        
        claude_config_path = None
        for path in config_paths:
            if path.parent.exists():
                claude_config_path = path
                break
        
        if not claude_config_path:
            self.console.print("❌ Claude Desktop config directory not found", style="red")
            self.console.print("💡 Install Claude Desktop first, then re-run setup")
            return
        
        # Load existing config or create new
        claude_config = {}
        if claude_config_path.exists():
            try:
                claude_config = json.loads(claude_config_path.read_text())
            except Exception as e:
                self.console.print(f"⚠️ Could not read existing config: {e}", style="yellow")
                claude_config = {}
        
        # Ensure mcpServers section exists
        if "mcpServers" not in claude_config:
            claude_config["mcpServers"] = {}
        
        # Add configurations for each endpoint
        server_script = str(self.project_root / "server_manual.py")
        
        for endpoint_id, endpoint_config in endpoints.items():
            config_name = endpoint_config["name"]
            
            mcp_config = {
                "command": "python",
                "args": [server_script],
                "env": endpoint_config.get("environment", {})
            }
            
            claude_config["mcpServers"][config_name] = mcp_config
            
            self.console.print(f"✅ Added configuration: {config_name}", style="green")
        
        # Save configuration
        try:
            claude_config_path.write_text(json.dumps(claude_config, indent=2))
            self.console.print(f"✅ Claude Desktop configured: {claude_config_path}", style="green")
            
            # Show summary
            self.console.print("\n📋 **CLAUDE DESKTOP CONFIGURATIONS:**")
            for endpoint_id, endpoint_config in endpoints.items():
                config_name = endpoint_config["name"]
                providers = ", ".join(endpoint_config["providers"])
                self.console.print(f"• **{config_name}**: {providers}")
            
            # Show restart instruction
            self.console.print(f"\n🔄 **RESTART CLAUDE DESKTOP** to load new configurations")
            
            # Show credential saving reminder for AWS
            aws_endpoints = [ep for ep in endpoints.values() if "aws" in ep["providers"]]
            if aws_endpoints:
                self.console.print(f"\n💾 **REMEMBER:** Run these commands before using AWS endpoints:")
                if 'aws_auth_command' in self.config_data:
                    self.console.print(f"1. {self.config_data['aws_auth_command']}")
                    self.console.print(f"2. python save_credentials.py")
                else:
                    self.console.print(f"1. Authenticate to AWS (profile, role, etc.)")
                    self.console.print(f"2. python save_credentials.py")
                
        except Exception as e:
            self.console.print(f"❌ Error saving Claude Desktop config: {e}", style="red")
            self.console.print(f"💡 Manual path: {claude_config_path}")
            
            # Show manual configuration
            self.console.print("\n📝 **MANUAL CONFIGURATION:**")
            config_json = json.dumps(claude_config, indent=2)
            syntax = Syntax(config_json, "json", theme="monokai", line_numbers=True)
            self.console.print(syntax)

    def install_cursor(self, endpoints: Dict[str, Dict]):
        """Install MCP server configuration for Cursor."""
        platform_name = platform.system().lower()
        if platform_name == "darwin":
            platform_key = "darwin"
        elif platform_name == "windows":
            platform_key = "win32"
        else:
            platform_key = "linux"
        
        config_path = Path(CURSOR_CONFIGS[platform_key]).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create new
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    cursor_config = json.load(f)
            except json.JSONDecodeError:
                cursor_config = {}
        else:
            cursor_config = {}
        
        # Ensure mcp section exists
        if "mcp" not in cursor_config:
            cursor_config["mcp"] = {"enabled": True}
        
        # Save settings.json
        with open(config_path, 'w') as f:
            json.dump(cursor_config, f, indent=2)
        
        self.console.print(f"✅ Cursor settings configured at: {config_path}", style="green")
        
        # Create mcp.json configuration
        self.create_cursor_mcp_config(endpoints)
        
        # Show restart instructions
        endpoint_info = []
        for endpoint_id, config in endpoints.items():
            script_type = " (with pre-run scripts)" if config.get("pre_run_commands") else ""
            endpoint_info.append(f"• {config['name']}{script_type}")
        
        self.console.print(Panel(
            "🖱️ Please restart Cursor to load the new MCP servers.\n\n"
            f"Added {len(endpoints)} Autocost Controller endpoint(s):\n" +
            "\n".join(endpoint_info),
            title="🔄 Cursor Setup Complete",
            style="green"
        ))

    def create_cursor_mcp_config(self, endpoints: Dict[str, Dict]):
        """Create the mcp.json file for Cursor integration."""
        # Get the platform-specific config directory
        platform_name = platform.system().lower()
        if platform_name == "darwin":
            mcp_config_dir = Path.home() / ".cursor"
        elif platform_name == "windows":
            mcp_config_dir = Path.home() / "AppData" / "Roaming" / "Cursor"
        else:  # linux
            mcp_config_dir = Path.home() / ".config" / "cursor"
            
        mcp_config_dir.mkdir(parents=True, exist_ok=True)
        mcp_config_file = mcp_config_dir / "mcp.json"
        
        # Load existing config or create new
        mcp_config = {"mcpServers": {}}
        if mcp_config_file.exists():
            try:
                mcp_config = json.loads(mcp_config_file.read_text())
                if "mcpServers" not in mcp_config:
                    mcp_config["mcpServers"] = {}
            except json.JSONDecodeError:
                self.console.print("⚠️ Existing mcp.json is invalid, creating new", style="yellow")
                mcp_config = {"mcpServers": {}}
        
        # Get the Python executable path
        python_path = self.get_python_executable()
        server_script = str(self.project_root / "server_manual.py")
        
        # Add AWS server configuration
        aws_config = {
            "command": python_path,
            "args": [server_script, "--config", "configs/aws.json"],
            "env": {
                "AUTOCOST_PROVIDERS": "aws",
                "AUTOCOST_ENDPOINT": "aws",
                "PYTHONPATH": str(self.project_root)
            },
            "cwd": str(self.project_root)
        }
        mcp_config["mcpServers"]["aws-cost-explorer"] = aws_config
        
        # Add GCP server configuration
        gcp_config = {
            "command": python_path,
            "args": [server_script, "--config", "configs/gcp.json"],
            "env": {
                "AUTOCOST_PROVIDERS": "gcp",
                "AUTOCOST_ENDPOINT": "gcp",
                "PYTHONPATH": str(self.project_root)
            },
            "cwd": str(self.project_root)
        }
        
        # Add GCP environment variables from saved credentials
        gcp_env_vars = self._get_gcp_env_vars()
        gcp_config["env"].update(gcp_env_vars)
        
        mcp_config["mcpServers"]["gcp-cost-explorer"] = gcp_config
        
        # Save configuration
        try:
            mcp_config_file.write_text(json.dumps(mcp_config, indent=2))
            self.console.print(f"✅ Created Cursor MCP config at: {mcp_config_file}", style="green")
            
            # Show summary
            self.console.print("\n📋 **CURSOR MCP CONFIGURATIONS:**")
            self.console.print("• **aws-cost-explorer**: AWS Cost Analysis Tools")
            self.console.print("• **gcp-cost-explorer**: GCP Cost Analysis Tools")
            
            # Show restart instruction
            self.console.print(f"\n🔄 **RESTART CURSOR** to load new configurations")
            
        except Exception as e:
            self.console.print(f"❌ Error saving Cursor MCP config: {e}", style="red")
            self.console.print(f"💡 Manual path: {mcp_config_file}")
            
            # Show manual configuration
            self.console.print("\n📝 **MANUAL CONFIGURATION:**")
            config_json = json.dumps(mcp_config, indent=2)
            syntax = Syntax(config_json, "json", theme="monokai", line_numbers=True)
            self.console.print(syntax)

    def save_configuration(self, providers_config: Dict[str, bool], endpoints: Dict[str, Dict]):
        """Save configuration to .env file and endpoint configs."""
        env_file = self.project_root / ".env"
        
        # Prepare environment variables
        env_content = [
            "# Autocost Controller Configuration",
            "# Generated by setup script",
            "",
            "# Logging Configuration",
            "LOG_LEVEL=INFO",
            "",
            "# Provider Configuration"
        ]
        
        # Add provider flags
        for provider, enabled in providers_config.items():
            env_content.append(f"ENABLE_{provider.upper()}={'true' if enabled else 'false'}")
        
        # Add AWS configuration if provided
        if self.config_data:
            env_content.extend([
                "",
                "# AWS Configuration"
            ])
            for key, value in self.config_data.items():
                if key.startswith('aws_'):
                    env_content.append(f"{key}={value}")
            
            # Add GCP configuration if provided
            if any(key.startswith('gcp_') for key in self.config_data.keys()):
                env_content.extend([
                    "",
                    "# GCP Configuration"
                ])
                for key, value in self.config_data.items():
                    if key.startswith('gcp_'):
                        env_content.append(f"{key}={value}")
        
        # Add endpoint configuration
        env_content.extend([
            "",
            "# Endpoint Configuration",
            f"AUTOCOST_ENDPOINTS={json.dumps(endpoints)}"
        ])
        
        # Save .env file
        with open(env_file, 'w') as f:
            f.write("\n".join(env_content))
        
        self.console.print(f"✅ Configuration saved to: {env_file}", style="green")
        
        # Save endpoint-specific configs
        config_dir = self.project_root / "configs"
        config_dir.mkdir(exist_ok=True)
        
        for endpoint_id, config in endpoints.items():
            endpoint_config = {
                "endpoint_id": endpoint_id,
                "providers": config["providers"],
                "name": config["name"],
                "pre_run_commands": config.get("pre_run_commands", [])
            }
            
            # Add provider-specific configuration
            if "gcp" in config["providers"]:
                gcp_config = {}
                if 'gcp_organization_id' in self.config_data:
                    gcp_config["organization_id"] = self.config_data['gcp_organization_id']
                if gcp_config:
                    endpoint_config["gcp"] = gcp_config
            
            config_file = config_dir / f"{endpoint_id}.json"
            with open(config_file, 'w') as f:
                json.dump(endpoint_config, f, indent=2)
        
        self.console.print(f"✅ Endpoint configs saved to: {config_dir}", style="green")

    def show_completion_summary(self, endpoints: Dict[str, Dict]):
        """Show setup completion summary with next steps."""
        self.console.print("\n" + "="*60)
        self.console.print("🎉 SETUP COMPLETE!", style="bold green")
        self.console.print("="*60)
        
        # Show available endpoints
        table = Table(title="🚀 Available Endpoints")
        table.add_column("Endpoint", style="cyan")
        table.add_column("Command", style="green")
        table.add_column("Providers", style="yellow")
        
        for endpoint_id, config in endpoints.items():
            command = f"python main.py --endpoint {endpoint_id}"
            table.add_row(
                config["name"],
                command,
                ", ".join(config["providers"])
            )
        
        self.console.print(table)
        
        # Next steps
        next_steps = [
            "🔄 Restart Claude Desktop and/or Cursor if auto-installed",
            "🧪 Test your setup with: python main.py --test",
            "📊 Start analyzing costs with your preferred MCP client",
            "📖 Check README.md for advanced usage examples",
            "🔧 Customize settings in .env file as needed"
        ]
        
        self.console.print(Panel(
            "\n".join(next_steps),
            title="📋 Next Steps",
            style="blue"
        ))
        
        # Quick start command
        default_endpoint = list(endpoints.keys())[0]
        self.console.print(f"\n🚀 Quick start: python main.py --endpoint {default_endpoint}", style="bold green")

    def run_setup(self):
        """Run the complete setup process."""
        try:
            # Show banner
            self.show_banner()
            
            # Check Python version
            if not self.check_python_version():
                return False
            
            # Check and install dependencies
            if not self.check_and_install_dependencies():
                return False
            
            # Configure providers
            providers_config = self.configure_providers()
            
            # Configure endpoints
            endpoints = self.configure_endpoints(providers_config)
            
            # Configure pre-run scripts
            self.configure_pre_run_scripts(endpoints)
            
            # Create wrapper scripts
            self.create_wrapper_scripts(endpoints)
            
            # Auto-install integrations
            self.auto_install_integrations(endpoints)
            
            # Save configuration
            self.save_configuration(providers_config, endpoints)
            
            # Show completion summary
            self.show_completion_summary(endpoints)
            
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n\n👋 Setup cancelled by user", style="yellow")
            return False
        except Exception as e:
            self.console.print(f"\n❌ Setup failed: {str(e)}", style="red")
            return False


def main():
    """Main entry point for the setup script."""
    setup = AutocostSetup()
    success = setup.run_setup()
    
    if success:
        console.print("\n✨ Autocost Controller is ready to optimize your cloud costs! ✨", style="bold green")
    else:
        console.print("\n💔 Setup incomplete. Please check the errors above and try again.", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main() 