#!/usr/bin/env python3
"""
Autocost Controller Interactive Setup Script

Enhanced setup with auto-installation for Claude Desktop and Cursor,
plus provider-specific endpoint configuration.
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
        
        # GCP Configuration (placeholder)
        gcp_enabled = Confirm.ask("🔵 Enable Google Cloud Platform? (Coming Soon)", default=False)
        providers_config["gcp"] = gcp_enabled
        
        if gcp_enabled:
            self.console.print("🚧 GCP integration coming soon! Configuration saved for future use.", style="yellow")
        
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
            if Confirm.ask("💾 Save current credentials for Claude Desktop?", default=True):
                try:
                    subprocess.run([sys.executable, "save_credentials.py"], 
                                 cwd=self.project_root, check=True)
                    self.console.print("✅ Credentials saved for Claude Desktop", style="green")
                except Exception as e:
                    self.console.print(f"⚠️ Could not save credentials: {e}", style="yellow")
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
            cursor_config["mcp"] = {"servers": {}}
        elif "servers" not in cursor_config["mcp"]:
            cursor_config["mcp"]["servers"] = {}
        
        # Add each endpoint
        for endpoint_id, config in endpoints.items():
            server_name = f"autocost-{endpoint_id}"
            
            # Use wrapper script if pre-run commands exist, otherwise use main script
            if config.get("pre_run_commands"):
                command_script = str(self.project_root / "scripts" / f"run_{endpoint_id}.py")
                args = []  # Wrapper script handles the endpoint argument
            else:
                command_script = str(self.project_root / "main.py")
                args = ["--endpoint", endpoint_id]
            
            cursor_config["mcp"]["servers"][server_name] = {
                "command": self.get_python_executable(),
                "args": [command_script] + args,
                "env": {
                    "AUTOCOST_ENDPOINT": endpoint_id,
                    "AUTOCOST_PROVIDERS": ",".join(config["providers"])
                }
            }
        
        # Save configuration
        with open(config_path, 'w') as f:
            json.dump(cursor_config, f, indent=2)
        
        self.console.print(f"✅ Cursor configured at: {config_path}", style="green")
        
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
                "port": config["port"],
                "name": config["name"],
                "pre_run_commands": config.get("pre_run_commands", [])
            }
            
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