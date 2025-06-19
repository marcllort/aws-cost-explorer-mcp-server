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
import argparse
from datetime import datetime
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

# =============================================================================
# MCP SERVER FUNCTIONALITY (moved from server_manual.py)
# =============================================================================

def capture_fresh_credentials():
    """Capture fresh AWS credentials from current environment and save them."""
    # Check if we're in MCP mode (quiet operation)
    is_mcp = os.environ.get('AUTOCOST_MCP_MODE') == 'true'
    
    try:
        # Test if current environment has working AWS credentials
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        if not is_mcp:
            print(f"✅ Found working AWS credentials in environment")
            print(f"   Account: {identity['Account']}")
            print(f"   Identity: {identity['Arn']}")
        
        # Get credentials from current session
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials:
            frozen_credentials = credentials.get_frozen_credentials()
            
            # Save the working credentials
            project_root = Path(__file__).parent
            creds_data = {
                'aws_access_key_id': frozen_credentials.access_key,
                'aws_secret_access_key': frozen_credentials.secret_key,
                'aws_region': session.region_name or os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                'captured_at': identity['Arn'],
                'account_id': identity['Account']
            }
            
            if frozen_credentials.token:
                creds_data['aws_session_token'] = frozen_credentials.token
            
            # Save to file for future use
            creds_file = project_root / ".aws_credentials.json"
            creds_file.write_text(json.dumps(creds_data, indent=2))
            
            if not is_mcp:
                print(f"💾 Captured and saved fresh credentials to {creds_file}")
            return True
            
    except Exception as e:
        if not is_mcp:
            print(f"⚠️ Could not capture fresh credentials: {e}")
        return False

def load_saved_credentials():
    """Load saved AWS credentials if available."""
    # Check if we're in MCP mode (quiet operation)
    is_mcp = os.environ.get('AUTOCOST_MCP_MODE') == 'true'
    
    project_root = Path(__file__).parent
    creds_file = project_root / ".aws_credentials.json"
    if creds_file.exists():
        try:
            creds = json.loads(creds_file.read_text())
            
            # Set environment variables from saved credentials
            # Handle both possible key formats for backwards compatibility
            access_key = creds.get('aws_access_key_id') or creds.get('access_key')
            secret_key = creds.get('aws_secret_access_key') or creds.get('secret_key')
            session_token = creds.get('aws_session_token') or creds.get('session_token')
            region = creds.get('aws_region') or creds.get('region')
            
            if access_key and secret_key:
                os.environ['AWS_ACCESS_KEY_ID'] = access_key
                os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
                if session_token:
                    os.environ['AWS_SESSION_TOKEN'] = session_token
                if region:
                    os.environ['AWS_DEFAULT_REGION'] = region
                    
                return True
            else:
                if not is_mcp:
                    print(f"⚠️ Saved credentials missing required keys")
                return False
                
        except Exception as e:
            if not is_mcp:
                print(f"⚠️ Could not load saved credentials: {e}")
            return False
    return False

def setup_aws_credentials():
    """Setup AWS credentials with automatic detection and fallback."""
    # Check if we're in MCP mode (quiet operation)
    is_mcp = os.environ.get('AUTOCOST_MCP_MODE') == 'true'
    
    if not is_mcp:
        print("🔐 Setting up AWS credentials...")
    
    # First, try to capture fresh credentials from environment
    if capture_fresh_credentials():
        return True
    
    # If that fails, try to load saved credentials
    if not is_mcp:
        print("🔄 Trying saved credentials...")
    if load_saved_credentials():
        if not is_mcp:
            print("✅ Loaded saved credentials")
        return True
    
    if not is_mcp:
        print("⚠️ No working credentials found")
        print("💡 To fix this:")
        print("   1. In your terminal, assume your AWS role")
        print("   2. Run: python start.py --configure")
        print("   3. Or run: python start.py --server to restart")
    
    return False

def setup_datadog_credentials():
    """Setup DataDog credentials from environment variables."""
    # Check if we're in MCP mode (quiet operation)
    is_mcp = os.environ.get('AUTOCOST_MCP_MODE') == 'true'
    
    if not is_mcp:
        print("🐕 Setting up DataDog credentials...")
    
    api_key = os.environ.get('DATADOG_API_KEY')
    app_key = os.environ.get('DATADOG_APP_KEY')
    site = os.environ.get('DATADOG_SITE', 'datadoghq.com')
    
    if api_key and app_key:
        if not is_mcp:
            print(f"✅ DataDog credentials found for site: {site}")
        return True
    else:
        missing = []
        if not api_key:
            missing.append("DATADOG_API_KEY")
        if not app_key:
            missing.append("DATADOG_APP_KEY")
        
        if not is_mcp:
            print(f"⚠️ Missing DataDog credentials: {', '.join(missing)}")
            print("💡 To set up DataDog:")
            print("   1. Get your API and App keys from DataDog dashboard")
            print("   2. Set environment variables:")
            print("      export DATADOG_API_KEY=your_api_key")
            print("      export DATADOG_APP_KEY=your_app_key")
            print("      export DATADOG_SITE=datadoghq.com  # optional")
            print("   3. Restart the MCP server")
        
        return False

def get_enabled_providers():
    """Get list of enabled providers from environment."""
    providers_env = os.environ.get('AUTOCOST_PROVIDERS', 'aws')
    return [p.strip() for p in providers_env.split(',')]

def run_mcp_server():
    """Run the MCP server with environment-based configuration."""
    import logging
    import os
    
    # Set MCP mode environment variables to ensure quiet operation
    os.environ['MCP_TRANSPORT'] = 'stdio'
    os.environ['AUTOCOST_MCP_MODE'] = 'true'
    
    # Enable custom tools by default if not explicitly set
    if 'AUTOCOST_ENABLE_CUSTOM_TOOLS' not in os.environ:
        os.environ['AUTOCOST_ENABLE_CUSTOM_TOOLS'] = 'true'
    
    # Setup credentials for enabled providers
    enabled_providers = get_enabled_providers()
    
    # Setup AWS credentials with automatic detection
    aws_ready = setup_aws_credentials() if "aws" in enabled_providers else True
    
    # Setup DataDog credentials if enabled
    datadog_ready = setup_datadog_credentials() if "datadog" in enabled_providers else True
    
    endpoint_name = os.environ.get('AUTOCOST_ENDPOINT', 'unified')
    
    # Add project root to path for imports
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Import MCP components
    try:
        from mcp.server.fastmcp import FastMCP
        from autocost_controller.core.config import Config
        from autocost_controller.core.logger import AutocostLogger
        from autocost_controller.core.provider_manager import ProviderManager
        from autocost_controller.tools import register_all_tools
    except ImportError as e:
        print(f"❌ Failed to import MCP components: {e}", file=sys.stderr)
        print("💡 Make sure dependencies are installed: python start.py --configure", file=sys.stderr)
        return False
    
    # Initialize components
    config = Config()
    logger = AutocostLogger("autocost-server")
    
    # Create FastMCP instance
    mcp = FastMCP("Autocost Controller")
    
    # Initialize provider manager
    provider_manager = ProviderManager(config, logger)
    
    # Register all tools (includes core tools and provider-specific tools)
    register_all_tools(mcp, provider_manager, config, logger)
    
    # Log status to logger only (AutocostLogger will use stderr in MCP mode)
    logger.info(f"🎯 MCP Server ready with {len(enabled_providers)} provider(s)")
    
    # Run the server (stdout is used for JSON-RPC communication)
    try:
        mcp.run()
        return True
    except Exception as e:
        # Log the specific error to stderr for debugging
        import traceback
        print(f"❌ MCP Server error: {e}", file=sys.stderr)
        print(f"📋 Traceback: {traceback.format_exc()}", file=sys.stderr)
        return False

def test_setup():
    """Test the current setup and provider status."""
    print("🧪 Testing Autocost Controller setup...")
    
    # Add project root to path for imports
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    try:
        from autocost_controller.core.config import Config
        from autocost_controller.core.logger import AutocostLogger
        from autocost_controller.core.provider_manager import ProviderManager
    except ImportError as e:
        print(f"❌ Failed to import components: {e}")
        print("💡 Run: python start.py --configure to install dependencies")
        return False
    
    # Load saved credentials
    creds_loaded = load_saved_credentials()
    if creds_loaded:
        print("✅ Saved AWS credentials loaded")
    else:
        print("⚠️ No saved credentials found, using environment")
    
    # Test providers
    config = Config()
    logger = AutocostLogger("autocost-test")
    
    enabled_providers = get_enabled_providers()
    print(f"🎯 Enabled providers: {', '.join(enabled_providers)}")
    
    provider_manager = ProviderManager(config, logger)
    
    # Give providers time to initialize
    import time
    time.sleep(2)
    
    statuses = provider_manager.get_all_statuses()
    
    for provider_name in enabled_providers:
        if provider_name in statuses:
            status = statuses[provider_name]
            if status.status == "ready":
                capabilities = ", ".join(status.capabilities)
                print(f"✅ {provider_name.upper()}: ready with capabilities: {capabilities}")
            else:
                error_msg = status.error_message or "Unknown error"
                print(f"❌ {provider_name.upper()}: {status.status} - {error_msg}")
        else:
            print(f"❌ {provider_name.upper()}: not configured")
    
    return True

# =============================================================================
# SETUP CLASS (existing functionality)
# =============================================================================

class AutocostSetup:
    def __init__(self):
        self.console = console
        self.project_root = Path(__file__).parent
        self.config_data = {}
        self.provider_endpoints = {}
        
    def get_python_executable(self) -> str:
        """Get the path to the current Python executable."""
        return sys.executable

    def show_banner(self, mode: str = "default"):
        """Display the enhanced startup banner."""
        mode_info = {
            "configure": "🔧 Interactive Setup & Auto-Installation Wizard 🔧",
            "server": "🚀 Starting MCP Server 🚀",
            "verify": "🔍 Setup Verification 🔍",
            "default": "⚡ Quick Setup & Credential Capture ⚡"
        }
        
        banner_text = f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    🚀 AUTOCOST CONTROLLER 🚀                 ║
    ║                                                              ║
    ║           Multi-Cloud Cost Optimization Platform            ║
    ║                                                              ║
    ║  {mode_info.get(mode, mode_info["default"]).center(60)}  ║
    ╚══════════════════════════════════════════════════════════════╝
        """
        
        self.console.print(Panel(
            banner_text,
            style="bold blue",
            border_style="bright_blue"
        ))
        
        if mode in ["configure", "default"]:
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
        """Check and install required dependencies including DataDog support."""
        required_packages = [
            "boto3>=1.37.9", 
            "mcp>=1.3.0", 
            "pydantic>=2.10.6", 
            "python-dotenv>=1.0.0", 
            "rich>=13.7.0",
            "datadog-api-client>=2.26.0",
            "pandas>=2.2.3",
            "tabulate>=0.9.0",
            "colorama>=0.4.6"
        ]
        
        missing_packages = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("🔍 Checking dependencies...", total=len(required_packages))
            
            for package in required_packages:
                package_name = package.split(">=")[0].replace("-", "_")
                try:
                    __import__(package_name)
                    progress.console.print(f"✅ {package.split('>=')[0]}", style="green")
                except ImportError:
                    missing_packages.append(package)
                    progress.console.print(f"❌ {package.split('>=')[0]} - Missing", style="red")
                progress.advance(task)
        
        if missing_packages:
            self.console.print(f"\n📦 Installing missing packages: {', '.join([p.split('>=')[0] for p in missing_packages])}")
            
            try:
                # Install from the project's pyproject.toml to ensure consistency
                if (self.project_root / "pyproject.toml").exists():
                    self.console.print("📋 Installing from pyproject.toml...")
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", "-e", "."
                    ], cwd=self.project_root)
                else:
                    # Fallback to individual package installation
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", "--upgrade"
                    ] + missing_packages)
                
                self.console.print("✅ All dependencies installed successfully!", style="green")
                return True
            except subprocess.CalledProcessError as e:
                self.console.print(f"❌ Failed to install dependencies: {e}", style="red")
                self.console.print("💡 Try running: pip install -e . manually", style="yellow")
                return False
        
        self.console.print("✅ All dependencies are already installed!", style="green")
        return True

    def configure_providers(self) -> Dict[str, bool]:
        """Interactive menu for managing providers."""
        return self.provider_management_menu()

    def provider_management_menu(self) -> Dict[str, bool]:
        """Interactive menu system for provider management."""
        # Load existing configuration
        existing_env = self.load_existing_env()
        current_providers = self.get_current_provider_status(existing_env)
        
        while True:
            self.show_provider_status_table(current_providers)
            
            self.console.print("\n📋 PROVIDER MANAGEMENT MENU", style="bold blue")
            
            choices = [
                "1. Add/Enable Provider",
                "2. Configure Existing Provider", 
                "3. Disable Provider",
                "4. Remove Provider Completely",
                "5. Test Provider Connection",
                "6. View Provider Details",
                "7. Done - Save & Continue"
            ]
            
            for choice in choices:
                self.console.print(f"   {choice}")
            
            action = Prompt.ask("\nSelect an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")
            
            if action == "1":
                self.add_enable_provider_menu(current_providers)
            elif action == "2":
                self.configure_existing_provider_menu(current_providers)
            elif action == "3":
                self.disable_provider_menu(current_providers)
            elif action == "4":
                self.remove_provider_menu(current_providers)
            elif action == "5":
                self.test_provider_menu(current_providers)
            elif action == "6":
                self.view_provider_details_menu(current_providers)
            elif action == "7":
                break
                
        return self.convert_provider_status_to_config(current_providers)

    def get_current_provider_status(self, existing_env: Dict[str, str]) -> Dict[str, Dict]:
        """Get current status of all providers."""
        providers = {
            "aws": {
                "name": "AWS Cost Explorer",
                "icon": "🔶", 
                "status": "disabled",
                "configured": False,
                "working": False,
                "description": "Amazon Web Services cost analysis and optimization"
            },
            "datadog": {
                "name": "DataDog Monitoring", 
                "icon": "🐕",
                "status": "disabled",
                "configured": False,
                "working": False,
                "description": "DataDog logs, metrics, and usage analysis"
            },
            "gcp": {
                "name": "Google Cloud Platform",
                "icon": "🔵", 
                "status": "coming_soon",
                "configured": False,
                "working": False,
                "description": "Google Cloud cost and resource analysis (Coming Soon)"
            },
            "azure": {
                "name": "Microsoft Azure",
                "icon": "🔷",
                "status": "coming_soon", 
                "configured": False,
                "working": False,
                "description": "Azure cost management and optimization (Coming Soon)"
            }
        }
        
        # Check what's actually configured
        if existing_env.get("AUTOCOST_PROVIDERS"):
            enabled_providers = existing_env.get("AUTOCOST_PROVIDERS", "").split(",")
            for provider in enabled_providers:
                provider = provider.strip()
                if provider in providers:
                    providers[provider]["status"] = "enabled"
                    
        # Check AUTOCOST_ENDPOINTS configuration
        endpoints_config = existing_env.get("AUTOCOST_ENDPOINTS", "")
        if endpoints_config:
            try:
                import json
                endpoints = json.loads(endpoints_config)
                for endpoint_id, config in endpoints.items():
                    if "providers" in config:
                        for provider in config["providers"]:
                            if provider in providers:
                                providers[provider]["status"] = "enabled"
            except json.JSONDecodeError:
                pass
        
        # Check if providers are actually configured and working
        # AWS
        if existing_env.get("AWS_ACCESS_KEY_ID") or self.check_aws_credentials_silent():
            providers["aws"]["configured"] = True
            providers["aws"]["working"] = self.check_aws_credentials_silent()
            
        # DataDog  
        if existing_env.get("DATADOG_API_KEY") and existing_env.get("DATADOG_APP_KEY"):
            providers["datadog"]["configured"] = True
            providers["datadog"]["working"] = self.test_datadog_connection_silent(
                existing_env.get("DATADOG_API_KEY"),
                existing_env.get("DATADOG_APP_KEY"), 
                existing_env.get("DATADOG_SITE", "datadoghq.com")
            )
            
        return providers

    def show_provider_status_table(self, providers: Dict[str, Dict]):
        """Show current provider status in a nice table."""
        from rich.table import Table
        
        table = Table(title="🌟 Provider Status", show_header=True, header_style="bold blue")
        table.add_column("Provider", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Configured", justify="center")
        table.add_column("Working", justify="center")
        table.add_column("Description", style="dim")
        
        for provider_id, info in providers.items():
            # Status styling
            if info["status"] == "enabled":
                status = "[green]✅ Enabled[/green]"
            elif info["status"] == "disabled":
                status = "[red]❌ Disabled[/red]"
            elif info["status"] == "coming_soon":
                status = "[yellow]🚧 Coming Soon[/yellow]"
            else:
                status = "[dim]❓ Unknown[/dim]"
                
            # Configured styling
            configured = "[green]✅[/green]" if info["configured"] else "[red]❌[/red]"
            
            # Working styling  
            if info["status"] == "coming_soon":
                working = "[dim]N/A[/dim]"
            else:
                working = "[green]✅[/green]" if info["working"] else "[red]❌[/red]"
            
            table.add_row(
                f"{info['icon']} {info['name']}",
                status,
                configured,
                working,
                info["description"]
            )
            
        self.console.print(table)

    def add_enable_provider_menu(self, providers: Dict[str, Dict]):
        """Menu to add/enable providers."""
        available_providers = {k: v for k, v in providers.items() 
                             if v["status"] != "enabled" and v["status"] != "coming_soon"}
        
        if not available_providers:
            self.console.print("✅ All available providers are already enabled!", style="green")
            return
            
        self.console.print("\n➕ ADD/ENABLE PROVIDER", style="bold green")
        
        provider_choices = []
        for provider_id, info in available_providers.items():
            provider_choices.append(f"{provider_id}")
            self.console.print(f"   {info['icon']} {provider_id}: {info['name']}")
            
        provider_choices.append("cancel")
        self.console.print("   ❌ cancel: Go back to main menu")
        
        choice = Prompt.ask("\nWhich provider to enable?", choices=provider_choices, default="cancel")
        
        if choice == "cancel":
            return
            
        # Enable and configure the provider
        if choice == "aws":
            providers["aws"]["status"] = "enabled"
            self.configure_aws()
            providers["aws"]["configured"] = True
            providers["aws"]["working"] = self.check_aws_credentials_silent()
        elif choice == "datadog":
            providers["datadog"]["status"] = "enabled"
            success = self.configure_datadog_interactive()
            if success:
                providers["datadog"]["configured"] = True
                # Test will be done in configure_datadog_interactive
            else:
                providers["datadog"]["status"] = "disabled"

    def configure_existing_provider_menu(self, providers: Dict[str, Dict]):
        """Menu to reconfigure existing providers."""
        enabled_providers = {k: v for k, v in providers.items() 
                           if v["status"] == "enabled"}
        
        if not enabled_providers:
            self.console.print("❌ No enabled providers to configure.", style="red")
            return
            
        self.console.print("\n⚙️ CONFIGURE EXISTING PROVIDER", style="bold yellow")
        
        provider_choices = []
        for provider_id, info in enabled_providers.items():
            provider_choices.append(f"{provider_id}")
            working_status = "✅ Working" if info["working"] else "❌ Issues"
            self.console.print(f"   {info['icon']} {provider_id}: {info['name']} - {working_status}")
            
        provider_choices.append("cancel")
        
        choice = Prompt.ask("\nWhich provider to reconfigure?", choices=provider_choices, default="cancel")
        
        if choice == "cancel":
            return
            
        if choice == "aws":
            self.configure_aws()
            providers["aws"]["configured"] = True
            providers["aws"]["working"] = self.check_aws_credentials_silent()
        elif choice == "datadog":
            success = self.configure_datadog_interactive()
            if success:
                providers["datadog"]["configured"] = True

    def disable_provider_menu(self, providers: Dict[str, Dict]):
        """Menu to disable providers."""
        enabled_providers = {k: v for k, v in providers.items() 
                           if v["status"] == "enabled"}
        
        if not enabled_providers:
            self.console.print("❌ No enabled providers to disable.", style="red")
            return
            
        self.console.print("\n⏸️ DISABLE PROVIDER", style="bold yellow")
        self.console.print("   (Credentials will be kept, but provider won't be used)")
        
        provider_choices = []
        for provider_id, info in enabled_providers.items():
            provider_choices.append(f"{provider_id}")
            self.console.print(f"   {info['icon']} {provider_id}: {info['name']}")
            
        provider_choices.append("cancel")
        
        choice = Prompt.ask("\nWhich provider to disable?", choices=provider_choices, default="cancel")
        
        if choice != "cancel" and choice in providers:
            providers[choice]["status"] = "disabled"
            self.console.print(f"✅ {providers[choice]['name']} disabled", style="green")

    def remove_provider_menu(self, providers: Dict[str, Dict]):
        """Menu to completely remove providers."""
        configured_providers = {k: v for k, v in providers.items() 
                              if v["configured"] or v["status"] == "enabled"}
        
        if not configured_providers:
            self.console.print("❌ No configured providers to remove.", style="red")
            return
            
        self.console.print("\n🗑️ REMOVE PROVIDER COMPLETELY", style="bold red")
        self.console.print("   ⚠️ This will delete all credentials and configuration!")
        
        provider_choices = []
        for provider_id, info in configured_providers.items():
            provider_choices.append(f"{provider_id}")
            self.console.print(f"   {info['icon']} {provider_id}: {info['name']}")
            
        provider_choices.append("cancel")
        
        choice = Prompt.ask("\nWhich provider to remove completely?", choices=provider_choices, default="cancel")
        
        if choice != "cancel" and choice in providers:
            confirm = Confirm.ask(f"⚠️ Really remove {providers[choice]['name']} completely?", default=False)
            if confirm:
                providers[choice]["status"] = "disabled"
                providers[choice]["configured"] = False
                providers[choice]["working"] = False
                self.console.print(f"🗑️ {providers[choice]['name']} removed completely", style="red")

    def test_provider_menu(self, providers: Dict[str, Dict]):
        """Menu to test provider connections."""
        configured_providers = {k: v for k, v in providers.items() 
                              if v["configured"]}
        
        if not configured_providers:
            self.console.print("❌ No configured providers to test.", style="red")
            return
            
        self.console.print("\n🧪 TEST PROVIDER CONNECTION", style="bold blue")
        
        provider_choices = []
        for provider_id, info in configured_providers.items():
            provider_choices.append(f"{provider_id}")
            self.console.print(f"   {info['icon']} {provider_id}: {info['name']}")
            
        provider_choices.extend(["all", "cancel"])
        self.console.print("   🔄 all: Test all providers")
        
        choice = Prompt.ask("\nWhich provider to test?", choices=provider_choices, default="cancel")
        
        if choice == "cancel":
            return
        elif choice == "all":
            for provider_id in configured_providers:
                self.test_single_provider(provider_id, providers)
        else:
            self.test_single_provider(choice, providers)

    def view_provider_details_menu(self, providers: Dict[str, Dict]):
        """Menu to view detailed provider information."""
        self.console.print("\n📊 PROVIDER DETAILS", style="bold blue")
        
        provider_choices = []
        for provider_id, info in providers.items():
            provider_choices.append(f"{provider_id}")
            self.console.print(f"   {info['icon']} {provider_id}: {info['name']}")
            
        provider_choices.append("cancel")
        
        choice = Prompt.ask("\nWhich provider details to view?", choices=provider_choices, default="cancel")
        
        if choice != "cancel" and choice in providers:
            self.show_detailed_provider_info(choice, providers[choice])

    def configure_datadog_interactive(self) -> bool:
        """Interactive DataDog configuration."""
        self.console.print("\n🐕 DATADOG CONFIGURATION", style="bold blue")
        
        # Check for existing credentials
        existing_env = self.load_existing_env()
        existing_api_key = existing_env.get("DATADOG_API_KEY")
        existing_app_key = existing_env.get("DATADOG_APP_KEY")
        existing_site = existing_env.get("DATADOG_SITE", "datadoghq.com")
        
        if existing_api_key and existing_app_key:
            self.console.print("📄 Found existing DataDog credentials", style="blue")
            if Confirm.ask("Use existing credentials?", default=True):
                datadog_api_key = existing_api_key
                datadog_app_key = existing_app_key
                datadog_site = existing_site
                self.console.print("✅ Using existing credentials", style="green")
            else:
                datadog_api_key = Prompt.ask("Enter DataDog API Key", password=True)
                datadog_app_key = Prompt.ask("Enter DataDog Application Key", password=True)
                datadog_site = Prompt.ask("Enter DataDog Site", default=existing_site)
        else:
            self.console.print("💡 Get API keys from: https://app.datadoghq.com/organization-settings/api-keys")
            datadog_api_key = Prompt.ask("Enter DataDog API Key", password=True)
            datadog_app_key = Prompt.ask("Enter DataDog Application Key", password=True)
            datadog_site = Prompt.ask("Enter DataDog Site", default="datadoghq.com")
        
        # Test connection
        if Confirm.ask("🧪 Test connection?", default=True):
            if not self.test_datadog_connection(datadog_api_key, datadog_app_key, datadog_site):
                if not Confirm.ask("⚠️ Test failed. Save anyway?", default=False):
                    return False
        
        # Save configuration temporarily (will be saved to .env later)
        self.temp_datadog_config = {
            "api_key": datadog_api_key,
            "app_key": datadog_app_key,
            "site": datadog_site
        }
        
        return True

    def check_aws_credentials_silent(self) -> bool:
        """Check AWS credentials without printing output."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            session = boto3.Session()
            sts_client = session.client('sts')
            sts_client.get_caller_identity()
            return True
        except:
            return False

    def test_datadog_connection_silent(self, api_key: str, app_key: str, site: str) -> bool:
        """Test DataDog connection without printing output."""
        try:
            from datadog_api_client import ApiClient, Configuration
            from datadog_api_client.v1.api.authentication_api import AuthenticationApi
            import ssl
            
            # Try with SSL verification first
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = api_key
            configuration.api_key["appKeyAuth"] = app_key
            configuration.server_variables["site"] = site
            
            try:
                with ApiClient(configuration) as api_client:
                    api_instance = AuthenticationApi(api_client)
                    response = api_instance.validate()
                    return response.valid
            except ssl.SSLError:
                # Try without SSL verification for corporate environments
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    configuration_no_ssl = Configuration()
                    configuration_no_ssl.api_key["apiKeyAuth"] = api_key
                    configuration_no_ssl.api_key["appKeyAuth"] = app_key
                    configuration_no_ssl.server_variables["site"] = site
                    configuration_no_ssl.verify_ssl = False
                    
                    with ApiClient(configuration_no_ssl) as api_client:
                        api_instance = AuthenticationApi(api_client)
                        response = api_instance.validate()
                        return response.valid
                except:
                    return False
        except:
            return False

    def test_single_provider(self, provider_id: str, providers: Dict[str, Dict]):
        """Test a single provider and update its status."""
        info = providers[provider_id]
        self.console.print(f"\n🧪 Testing {info['icon']} {info['name']}...")
        
        if provider_id == "aws":
            working = self.check_aws_credentials()
        elif provider_id == "datadog":
            existing_env = self.load_existing_env()
            working = self.test_datadog_connection(
                existing_env.get("DATADOG_API_KEY"),
                existing_env.get("DATADOG_APP_KEY"),
                existing_env.get("DATADOG_SITE", "datadoghq.com")
            )
        else:
            self.console.print("❌ Testing not implemented for this provider", style="red")
            return
            
        providers[provider_id]["working"] = working

    def show_detailed_provider_info(self, provider_id: str, info: Dict):
        """Show detailed information about a provider."""
        from rich.panel import Panel
        
        status_text = f"Status: {info['status']}\n"
        status_text += f"Configured: {'✅ Yes' if info['configured'] else '❌ No'}\n"
        status_text += f"Working: {'✅ Yes' if info['working'] else '❌ No'}\n"
        status_text += f"\nDescription: {info['description']}"
        
        if provider_id == "aws":
            status_text += "\n\nRequired Permissions:\n• Cost Explorer access\n• Billing read permissions"
        elif provider_id == "datadog":
            status_text += "\n\nRequired: API Key + App Key\nOptional: Custom site (default: datadoghq.com)"
            
        panel = Panel(status_text, title=f"{info['icon']} {info['name']}", border_style="blue")
        self.console.print(panel)

    def convert_provider_status_to_config(self, providers: Dict[str, Dict]) -> Dict[str, bool]:
        """Convert provider status back to the expected config format."""
        config = {}
        
        for provider_id, info in providers.items():
            config[provider_id] = (info["status"] == "enabled")
            
        # Add DataDog config if it was configured
        if hasattr(self, 'temp_datadog_config') and config.get("datadog"):
            config["datadog_config"] = self.temp_datadog_config
            
        return config

    def configure_aws(self):
        """Configure AWS with enhanced credential checking."""
        self.console.print("\n🔶 AWS CONFIGURATION", style="bold yellow")
        
        # Check for existing environment variables first
        existing_env = self.load_existing_env()
        aws_env_vars = {k: v for k, v in existing_env.items() if k.startswith("AWS_")}
        
        if aws_env_vars:
            self.console.print("📄 Found existing AWS environment variables:", style="blue")
            for key in sorted(aws_env_vars.keys()):
                if "SECRET" in key or "TOKEN" in key:
                    self.console.print(f"   {key}=***", style="blue")
                else:
                    self.console.print(f"   {key}={aws_env_vars[key]}", style="blue")
        
        # Check for existing credentials
        aws_configured = self.check_aws_credentials()
        
        if aws_configured:
            self.console.print("✅ AWS credentials are working!", style="green")
            
            # Check if user wants to update/change credentials
            if Confirm.ask("🔄 AWS credentials found. Update or change them?", default=False):
                setup_method = Prompt.ask(
                    "Choose AWS setup method",
                    choices=["profile", "environment", "role", "refresh"],
                    default="refresh"
                )
                
                if setup_method == "refresh":
                    self.console.print("💡 To refresh credentials:")
                    self.console.print("   • For assumed roles: re-run your assume role command")
                    self.console.print("   • Then run: python save_current_session.py")
                elif setup_method == "profile":
                    self.setup_aws_profile()
                elif setup_method == "environment":
                    self.setup_aws_env()
                elif setup_method == "role":
                    self.setup_aws_role()
            else:
                self.console.print("✅ Using existing AWS credentials", style="green")
        else:
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
        
        # Show required permissions if requested
        if Confirm.ask("📋 Show required AWS IAM permissions?", default=False):
            self.show_iam_instructions()
        
        # Save current credentials for Claude Desktop (if working)
        if aws_configured or self.check_aws_credentials():
            if Confirm.ask("💾 Save current credentials for Claude Desktop?", default=True):
                try:
                    subprocess.run([sys.executable, "save_credentials.py"], 
                                 cwd=self.project_root, check=True)
                    self.console.print("✅ Credentials saved for Claude Desktop", style="green")
                except Exception as e:
                    self.console.print(f"⚠️ Could not save credentials: {e}", style="yellow")
                    self.console.print("💡 You can run 'python save_credentials.py' manually later", style="blue")

    def check_aws_credentials(self) -> bool:
        """Enhanced AWS credential validation with lighter checks."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # First, check if credentials are available at all
            session = boto3.Session()
            
            # Test with STS first (lighter call)
            sts_client = session.client('sts')
            identity = sts_client.get_caller_identity()
            
            self.console.print(f"✅ AWS Account: {identity.get('Account', 'Unknown')}", style="green")
            self.console.print(f"✅ User/Role: {identity.get('Arn', 'Unknown').split('/')[-1]}", style="green")
            
            # Check if credentials are from .env, environment, or profile
            creds = session.get_credentials()
            if creds:
                if creds.token:
                    self.console.print("✅ Using session credentials (temporary)", style="green")
                else:
                    self.console.print("✅ Using long-term credentials", style="green")
            
            # Optional: Test Cost Explorer permissions (but don't fail if it doesn't work)
            try:
                from datetime import datetime, timedelta
                
                ce_client = session.client('ce', region_name='us-east-1')
                
                # Use recent dates that are more likely to have data and pass validation
                end_date = datetime.now().date() - timedelta(days=1)  # Yesterday
                start_date = end_date - timedelta(days=1)  # Day before yesterday
                
                ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='DAILY',
                    Metrics=['BlendedCost']
                )
                self.console.print("✅ Cost Explorer permissions confirmed", style="green")
            except ClientError as ce_error:
                error_code = ce_error.response['Error']['Code']
                if error_code == 'UnauthorizedOperation':
                    self.console.print("⚠️ Limited Cost Explorer permissions (some features may be unavailable)", style="yellow")
                elif error_code == 'AccessDenied':
                    self.console.print("⚠️ No Cost Explorer access (basic features available)", style="yellow")
                else:
                    self.console.print(f"⚠️ Cost Explorer test failed: {error_code}", style="yellow")
                # Don't return False here - credentials work, just limited permissions
            
            return True
            
        except NoCredentialsError:
            self.console.print("❌ No AWS credentials found", style="red")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'TokenRefreshRequired':
                self.console.print("❌ AWS credentials expired - run 'python save_current_session.py'", style="red")
            elif error_code == 'InvalidUserID.NotFound':
                self.console.print("❌ AWS credentials invalid", style="red")
            else:
                self.console.print(f"❌ AWS authentication error: {error_code}", style="red")
            return False
        except Exception as e:
            self.console.print(f"❌ AWS connection error: {str(e)}", style="red")
            return False

    def test_datadog_connection(self, api_key: str, app_key: str, site: str) -> bool:
        """Test DataDog API connection with SSL fallback handling."""
        try:
            from datadog_api_client import ApiClient, Configuration
            from datadog_api_client.v1.api.authentication_api import AuthenticationApi
            import ssl
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("🧪 Testing DataDog connection...", total=1)
                
                # Try normal SSL verification first
                configuration = Configuration()
                configuration.api_key["apiKeyAuth"] = api_key
                configuration.api_key["appKeyAuth"] = app_key
                configuration.server_variables["site"] = site
                
                try:
                    # Test connection with validation endpoint
                    with ApiClient(configuration) as api_client:
                        api_instance = AuthenticationApi(api_client)
                        response = api_instance.validate()
                        
                        if response.valid:
                            self.console.print("✅ DataDog connection successful!", style="green")
                            progress.advance(task)
                            return True
                        else:
                            self.console.print("❌ DataDog validation failed", style="red")
                            return False
                            
                except ssl.SSLError as ssl_error:
                    if "CERTIFICATE_VERIFY_FAILED" in str(ssl_error):
                        self.console.print("⚠️ SSL certificate verification failed (corporate network detected)", style="yellow")
                        self.console.print("🔒 Automatically retrying with SSL verification disabled...", style="blue")
                        
                        try:
                            # Configure with SSL verification disabled
                            import urllib3
                            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                            
                            # Create configuration with SSL verification disabled
                            configuration_no_ssl = Configuration()
                            configuration_no_ssl.api_key["apiKeyAuth"] = api_key
                            configuration_no_ssl.api_key["appKeyAuth"] = app_key
                            configuration_no_ssl.server_variables["site"] = site
                            configuration_no_ssl.verify_ssl = False
                            
                            with ApiClient(configuration_no_ssl) as api_client:
                                api_instance = AuthenticationApi(api_client)
                                response = api_instance.validate()
                                
                                if response.valid:
                                    self.console.print("✅ DataDog connection successful (SSL verification disabled)!", style="green")
                                    self.console.print("💡 Note: SSL verification disabled for corporate network compatibility", style="cyan")
                                    progress.advance(task)
                                    return True
                                else:
                                    self.console.print("❌ DataDog validation failed even without SSL verification", style="red")
                                    return False
                                    
                        except Exception as e2:
                            self.console.print(f"❌ Connection failed even without SSL verification: {str(e2)}", style="red")
                            return False
                    else:
                        # Re-raise other SSL errors
                        raise
                        
        except ImportError:
            self.console.print("❌ DataDog API client not installed", style="red")
            self.console.print("💡 Run: pip install datadog-api-client", style="yellow")
            return False
        except Exception as e:
            error_str = str(e)
            if "CERTIFICATE_VERIFY_FAILED" in error_str:
                # SSL error at the outer level - try without SSL verification
                self.console.print("⚠️ SSL certificate verification failed (corporate network detected)", style="yellow")
                self.console.print("🔒 Automatically retrying with SSL verification disabled...", style="blue")
                
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    # Create configuration with SSL verification disabled
                    configuration_no_ssl = Configuration()
                    configuration_no_ssl.api_key["apiKeyAuth"] = api_key
                    configuration_no_ssl.api_key["appKeyAuth"] = app_key
                    configuration_no_ssl.server_variables["site"] = site
                    configuration_no_ssl.verify_ssl = False
                    
                    with ApiClient(configuration_no_ssl) as api_client:
                        api_instance = AuthenticationApi(api_client)
                        response = api_instance.validate()
                        
                        if response.valid:
                            self.console.print("✅ DataDog connection successful (SSL verification disabled)!", style="green")
                            self.console.print("💡 Note: SSL verification disabled for corporate network compatibility", style="cyan")
                            progress.advance(task)
                            return True
                        else:
                            self.console.print("❌ DataDog validation failed even without SSL verification", style="red")
                            return False
                            
                except Exception as e2:
                    self.console.print(f"❌ Connection failed even without SSL verification: {str(e2)}", style="red")
                    return False
            else:
                self.console.print(f"❌ DataDog connection error: {error_str}", style="red")
            return False

    def capture_aws_credentials(self) -> bool:
        """Capture current AWS session credentials and save them for the MCP server."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            self.console.print("🔐 Capturing current AWS session credentials...", style="blue")
            
            # Test if credentials work by getting caller identity
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            
            self.console.print("✅ Current AWS credentials are valid!", style="green")
            self.console.print(f"   Account: {identity['Account']}", style="green")
            self.console.print(f"   User/Role: {identity['Arn'].split('/')[-1]}", style="green")
            
            # Get credentials from the current session
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if credentials is None:
                self.console.print("❌ Could not retrieve credentials from current session", style="red")
                return False
            
            # Get the frozen credentials (includes session token if using assumed role)
            frozen_credentials = credentials.get_frozen_credentials()
            
            # Prepare credentials data
            creds_data = {
                'aws_access_key_id': frozen_credentials.access_key,
                'aws_secret_access_key': frozen_credentials.secret_key,
                'aws_region': session.region_name or os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            }
            
            # Add session token if available (for assumed roles)
            if frozen_credentials.token:
                creds_data['aws_session_token'] = frozen_credentials.token
                self.console.print("🔑 Session token detected (assumed role credentials)", style="cyan")
            
            # Save to file that the MCP server will read
            creds_file = self.project_root / ".aws_credentials.json"
            creds_file.write_text(json.dumps(creds_data, indent=2))
            
            self.console.print(f"💾 Credentials saved to {creds_file.name}", style="green")
            
            return True
            
        except NoCredentialsError:
            self.console.print("❌ No AWS credentials found in current session", style="red")
            self.console.print("💡 Run 'aws configure' or assume a role first", style="yellow")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ExpiredToken':
                self.console.print("❌ AWS credentials expired", style="red")
                self.console.print("💡 Re-run your AWS authentication command", style="yellow")
            else:
                self.console.print(f"❌ AWS error: {error_code}", style="red")
            return False
        except Exception as e:
            self.console.print(f"❌ Error capturing credentials: {e}", style="red")
            return False

    def verify_setup(self) -> bool:
        """Verify that the current setup is working properly."""
        self.console.print("\n🔍 VERIFYING SETUP", style="bold blue")
        
        issues = []
        warnings = []
        
        # Check environment file
        env_file = self.project_root / ".env"
        if env_file.exists():
            existing_env = self.load_existing_env()
            self.console.print("✅ Environment file found", style="green")
            
            # Check providers - handle both simple and endpoint configurations
            providers = []
            
            # Check for simple AUTOCOST_PROVIDERS first
            simple_providers = existing_env.get("AUTOCOST_PROVIDERS", "").split(",")
            if simple_providers and simple_providers != [""]:
                providers.extend(simple_providers)
            
            # Check for AUTOCOST_ENDPOINTS configuration
            endpoints_config = existing_env.get("AUTOCOST_ENDPOINTS", "")
            if endpoints_config:
                try:
                    import json
                    endpoints = json.loads(endpoints_config)
                    for endpoint_id, config in endpoints.items():
                        if "providers" in config:
                            providers.extend(config["providers"])
                except json.JSONDecodeError:
                    warnings.append("AUTOCOST_ENDPOINTS contains invalid JSON")
            
            # Remove duplicates and empty strings
            providers = list(set([p.strip() for p in providers if p.strip()]))
            
            if providers:
                self.console.print(f"✅ Enabled providers: {', '.join(providers)}", style="green")
            else:
                issues.append("No providers configured in .env")
        else:
            issues.append("No .env file found - run with --configure first")
        
        # Check AWS credentials
        if self.check_aws_credentials():
            self.console.print("✅ AWS credentials working", style="green")
        else:
            warnings.append("AWS credentials not working - consider refreshing them")
        
        # Check DataDog credentials if configured
        if env_file.exists() and existing_env.get("DATADOG_API_KEY"):
            try:
                datadog_api_key = existing_env.get("DATADOG_API_KEY")
                datadog_app_key = existing_env.get("DATADOG_APP_KEY")
                datadog_site = existing_env.get("DATADOG_SITE", "datadoghq.com")
                
                if self.test_datadog_connection(datadog_api_key, datadog_app_key, datadog_site):
                    self.console.print("✅ DataDog credentials working", style="green")
                else:
                    warnings.append("DataDog credentials not working")
            except Exception:
                warnings.append("DataDog credentials configured but untestable")
        
        # Check server functionality (now integrated into start.py)
        server_script = self.project_root / "start.py"
        if server_script.exists():
            self.console.print("✅ Server functionality integrated in start.py", style="green")
        else:
            issues.append("Start script (start.py) not found")
        
        # Check config files
        config_dir = self.project_root / "configs"
        if config_dir.exists() and list(config_dir.glob("*.json")):
            configs = list(config_dir.glob("*.json"))
            self.console.print(f"✅ Found {len(configs)} endpoint configurations", style="green")
        else:
            warnings.append("No endpoint configurations found")
        
        # Show results
        if issues:
            self.console.print("\n❌ ISSUES FOUND:", style="red")
            for issue in issues:
                self.console.print(f"   • {issue}", style="red")
        
        if warnings:
            self.console.print("\n⚠️ WARNINGS:", style="yellow")
            for warning in warnings:
                self.console.print(f"   • {warning}", style="yellow")
        
        if not issues and not warnings:
            self.console.print("\n🎉 Everything looks good!", style="bold green")
            return True
        elif not issues:
            self.console.print("\n✅ Setup is functional with minor warnings", style="green")
            return True
        else:
            self.console.print("\n❌ Setup has issues that need to be resolved", style="red")
            return False

    def start_server(self) -> bool:
        """Start the MCP server (now integrated into this script)."""
        # Don't print startup message when running MCP server as it interferes with JSON-RPC
        
        try:
            # Use the integrated server function
            return run_mcp_server()
        except KeyboardInterrupt:
            # Don't print messages during MCP server operation
            return True
        except Exception as e:
            # For debugging, write to stderr only
            import sys
            sys.stderr.write(f"Server error: {e}\n")
            return False

    def quick_setup(self) -> bool:
        """Quick setup mode - capture credentials and verify setup."""
        self.console.print("\n🚀 QUICK SETUP MODE", style="bold blue")
        self.console.print("Capturing credentials and verifying setup...\n")
        
        # Try to capture AWS credentials
        aws_captured = self.capture_aws_credentials()
        
        # Verify overall setup
        setup_ok = self.verify_setup()
        
        if aws_captured and setup_ok:
            self.console.print("\n✅ Quick setup completed successfully!", style="bold green")
            self.console.print("🚀 You can now start the server with: python start.py --server", style="green")
            return True
        elif setup_ok:
            self.console.print("\n⚠️ Setup verified but AWS credentials need attention", style="yellow")
            self.console.print("💡 Refresh your AWS credentials and try again", style="yellow")
            return True
        else:
            self.console.print("\n❌ Setup needs configuration", style="red")
            self.console.print("🔧 Run: python start.py --configure", style="yellow")
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
        
        # Detect Claude Desktop config location based on platform
        platform_name = platform.system().lower()
        
        if platform_name == "darwin":  # macOS
            claude_config_path = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
        elif platform_name == "linux":
            claude_config_path = Path.home() / ".config/claude/claude_desktop_config.json"
        elif platform_name == "windows":
            claude_config_path = Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json"
        else:
            self.console.print(f"❌ Unsupported platform: {platform_name}", style="red")
            return
        
        # Create config directory if it doesn't exist
        claude_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create new
        claude_config = {}
        if claude_config_path.exists():
            try:
                claude_config = json.loads(claude_config_path.read_text())
                self.console.print(f"📄 Found existing Claude Desktop config", style="blue")
            except Exception as e:
                self.console.print(f"⚠️ Could not read existing config: {e}", style="yellow")
                claude_config = {}
        
        # Ensure mcpServers section exists
        if "mcpServers" not in claude_config:
            claude_config["mcpServers"] = {}
        
        # Get the correct Python executable path
        python_executable = self.get_python_executable()
        server_script = str(self.project_root / "start.py")
        
        # Add configurations for each endpoint
        added_configs = []
        for endpoint_id, endpoint_config in endpoints.items():
            config_name = endpoint_config["name"]
            
            # Create environment variables for this endpoint
            endpoint_env = {
                "AUTOCOST_ENDPOINT": endpoint_id,
                "AUTOCOST_PROVIDERS": ",".join(endpoint_config["providers"]),
                **endpoint_config.get("environment", {})
            }
            
            # Add credentials from .env file if they exist
            env_file = self.project_root / ".env"
            if env_file.exists():
                existing_env = self.load_existing_env()
                for key, value in existing_env.items():
                    if key.startswith(("AWS_", "DATADOG_", "GCP_", "AZURE_")):
                        endpoint_env[key] = value
            
            mcp_config = {
                "command": python_executable,
                "args": [server_script, "--server"],
                "env": endpoint_env
            }
            
            # Check if config already exists and ask about overwriting
            if config_name in claude_config["mcpServers"]:
                if Confirm.ask(f"🔄 Configuration '{config_name}' already exists. Overwrite?", default=True):
                    claude_config["mcpServers"][config_name] = mcp_config
                    added_configs.append(f"🔄 Updated: {config_name}")
                else:
                    self.console.print(f"⏭️ Skipped: {config_name}", style="yellow")
                    continue
            else:
                claude_config["mcpServers"][config_name] = mcp_config
                added_configs.append(f"✅ Added: {config_name}")
        
        # Save configuration
        try:
            claude_config_path.write_text(json.dumps(claude_config, indent=2))
            self.console.print(f"✅ Claude Desktop configured: {claude_config_path}", style="green")
            
            # Show what was added/updated
            if added_configs:
                for config_info in added_configs:
                    self.console.print(config_info, style="green")
            
            # Show summary table
            table = Table(title="📋 Claude Desktop MCP Servers")
            table.add_column("Server Name", style="cyan")
            table.add_column("Providers", style="magenta")
            table.add_column("Status", style="green")
            
            for endpoint_id, endpoint_config in endpoints.items():
                config_name = endpoint_config["name"]
                providers = ", ".join(endpoint_config["providers"])
                status = "✅ Configured" if config_name in claude_config["mcpServers"] else "⏭️ Skipped"
                table.add_row(config_name, providers, status)
            
            self.console.print(table)
            
            # Show restart instruction
            self.console.print(Panel(
                "🔄 **RESTART CLAUDE DESKTOP** to load new configurations\n\n"
                "Your MCP servers will be available in Claude Desktop after restart.",
                title="🎉 Setup Complete",
                style="green"
            ))
            
            # Show credential setup reminder
            aws_endpoints = [ep for ep in endpoints.values() if "aws" in ep["providers"]]
            datadog_endpoints = [ep for ep in endpoints.values() if "datadog" in ep["providers"]]
            
            if aws_endpoints or datadog_endpoints:
                reminder_text = ["💾 **CREDENTIAL SETUP REMINDERS:**", ""]
                
                if aws_endpoints:
                    reminder_text.extend([
                        "🔶 **For AWS endpoints:**",
                        "1. Authenticate to AWS (aws sso login, aws configure, etc.)",
                        "2. Credentials will be captured automatically when starting the server",
                        ""
                    ])
                
                if datadog_endpoints:
                    reminder_text.extend([
                        "🐕 **For DataDog endpoints:**",
                        "1. Ensure DATADOG_API_KEY and DATADOG_APP_KEY are set",
                        "2. Check your .env file for correct values",
                        ""
                    ])
                
                self.console.print(Panel(
                    "\n".join(reminder_text),
                    title="🔑 Credential Setup",
                    style="yellow"
                ))
                
        except PermissionError:
            self.console.print(f"❌ Permission denied: {claude_config_path}", style="red")
            self.console.print("💡 Try running with elevated permissions or check file ownership", style="yellow")
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
                self.console.print(f"📄 Found existing Cursor MCP config", style="blue")
            except json.JSONDecodeError:
                self.console.print("⚠️ Existing mcp.json is invalid, creating new", style="yellow")
                mcp_config = {"mcpServers": {}}
        
        # Get the correct Python executable
        python_executable = self.get_python_executable()
        
        # Add each endpoint
        added_configs = []
        for endpoint_id, config in endpoints.items():
            server_name = config["name"]  # Use endpoint name for better identification
            
            # Create environment variables for this endpoint
            endpoint_env = {
                "AUTOCOST_ENDPOINT": endpoint_id,
                "AUTOCOST_PROVIDERS": ",".join(config["providers"]),
                "AUTOCOST_ENABLE_CUSTOM_TOOLS": "true",
                "PYTHONPATH": str(self.project_root)
            }
            
            # Add credentials from .env file if they exist
            env_file = self.project_root / ".env"
            if env_file.exists():
                existing_env = self.load_existing_env()
                for key, value in existing_env.items():
                    if key.startswith(("AWS_", "DATADOG_", "GCP_", "AZURE_", "LOG_LEVEL")):
                        endpoint_env[key] = value
            
            # Use wrapper script if pre-run commands exist, otherwise use main script
            if config.get("pre_run_commands"):
                command_script = str(self.project_root / "scripts" / f"run_{endpoint_id}.py")
                args = []  # Wrapper script handles the endpoint argument
            else:
                command_script = str(self.project_root / "start.py")
                args = ["--server"]
            
            server_config = {
                "command": python_executable,
                "args": [command_script] + args,
                "env": endpoint_env,
                "cwd": str(self.project_root)
            }
            
            # Check if config already exists and ask about overwriting
            if server_name in mcp_config["mcpServers"]:
                if Confirm.ask(f"🔄 Cursor server '{server_name}' already exists. Overwrite?", default=True):
                    mcp_config["mcpServers"][server_name] = server_config
                    added_configs.append(f"🔄 Updated: {server_name}")
                else:
                    self.console.print(f"⏭️ Skipped: {server_name}", style="yellow")
                    continue
            else:
                mcp_config["mcpServers"][server_name] = server_config
                added_configs.append(f"✅ Added: {server_name}")
        
        # Save configuration
        try:
            mcp_config_file.write_text(json.dumps(mcp_config, indent=2))
            self.console.print(f"✅ Created Cursor MCP config at: {mcp_config_file}", style="green")
            
            # Show what was added/updated
            if added_configs:
                for config_info in added_configs:
                    self.console.print(config_info, style="green")
            
            # Show summary table
            table = Table(title="📋 Cursor MCP Servers")
            table.add_column("Server Name", style="cyan")
            table.add_column("Providers", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Script Type", style="yellow")
            
            for endpoint_id, config in endpoints.items():
                server_name = config["name"]
                providers = ", ".join(config["providers"])
                status = "✅ Configured" if server_name in mcp_config["mcpServers"] else "⏭️ Skipped"
                script_type = "Wrapper" if config.get("pre_run_commands") else "Direct"
                table.add_row(server_name, providers, status, script_type)
            
            self.console.print(table)
            
            # Show restart instruction
            self.console.print(Panel(
                "🔄 **RESTART CURSOR** to load new configurations\n\n"
                "Your MCP servers will be available in Cursor after restart.\n"
                "Look for them in the MCP server list in Cursor settings.",
                title="🎉 Setup Complete",
                style="green"
            ))
            
        except PermissionError:
            self.console.print(f"❌ Permission denied: {mcp_config_file}", style="red")
            self.console.print("💡 Try running with elevated permissions or check file ownership", style="yellow")
        except Exception as e:
            self.console.print(f"❌ Error saving Cursor MCP config: {e}", style="red")
            self.console.print(f"💡 Manual path: {mcp_config_file}")
            
            # Show manual configuration
            self.console.print("\n📝 **MANUAL CONFIGURATION:**")
            config_json = json.dumps(mcp_config, indent=2)
            syntax = Syntax(config_json, "json", theme="monokai", line_numbers=True)
            self.console.print(syntax)

    def load_existing_env(self) -> Dict[str, str]:
        """Load existing .env file if it exists."""
        env_file = self.project_root / ".env"
        existing_env = {}
        
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            existing_env[key.strip()] = value.strip()
                
                self.console.print(f"📄 Found existing .env with {len(existing_env)} variables", style="blue")
                return existing_env
            except Exception as e:
                self.console.print(f"⚠️ Could not read existing .env: {e}", style="yellow")
        
        return existing_env

    def save_configuration(self, providers_config: Dict[str, bool], endpoints: Dict[str, Dict]):
        """Save configuration to .env file and endpoint configs, preserving existing settings."""
        env_file = self.project_root / ".env"
        
        # Load existing environment variables
        existing_env = self.load_existing_env()
        
        # Prepare new environment variables
        new_env = {}
        
        # Add logging configuration
        new_env["LOG_LEVEL"] = existing_env.get("LOG_LEVEL", "INFO")
        
        # Add provider configuration
        enabled_providers = []
        for provider, enabled in providers_config.items():
            if enabled and provider != "datadog_config":
                enabled_providers.append(provider)
                new_env[f"ENABLE_{provider.upper()}"] = "true"
        
        # Set the main providers list
        new_env["AUTOCOST_PROVIDERS"] = ",".join(enabled_providers)
        
        # Add DataDog configuration if provided
        if "datadog_config" in providers_config:
            datadog_config = providers_config["datadog_config"]
            new_env["DATADOG_API_KEY"] = datadog_config["api_key"]
            new_env["DATADOG_APP_KEY"] = datadog_config["app_key"] 
            new_env["DATADOG_SITE"] = datadog_config["site"]
        
        # Add AWS configuration if provided
        if self.config_data:
            for key, value in self.config_data.items():
                if key.startswith("AWS_") or key.startswith("aws_"):
                    new_env[key.upper()] = str(value)
        
        # Merge with existing environment variables (new ones take precedence)
        final_env = {**existing_env, **new_env}
        
        # Prepare content for writing
        env_content = [
            "# Autocost Controller Configuration",
            f"# Updated by setup script on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "# Core Configuration",
            f"LOG_LEVEL={final_env.get('LOG_LEVEL', 'INFO')}",
            f"AUTOCOST_PROVIDERS={final_env.get('AUTOCOST_PROVIDERS', 'aws')}",
            "",
            "# Provider Configuration"
        ]
        
        # Add provider-specific environment variables
        provider_vars = {}
        datadog_vars = {}
        aws_vars = {}
        other_vars = {}
        
        for key, value in final_env.items():
            if key.startswith("DATADOG_"):
                datadog_vars[key] = value
            elif key.startswith("AWS_") or key.startswith("aws_"):
                aws_vars[key] = value
            elif key.startswith("ENABLE_"):
                provider_vars[key] = value
            elif key not in ["LOG_LEVEL", "AUTOCOST_PROVIDERS"]:
                other_vars[key] = value
        
        # Add provider enable flags
        for key, value in sorted(provider_vars.items()):
            env_content.append(f"{key}={value}")
        
        # Add AWS configuration section
        if aws_vars:
            env_content.extend(["", "# AWS Configuration"])
            for key, value in sorted(aws_vars.items()):
                env_content.append(f"{key}={value}")
        
        # Add DataDog configuration section
        if datadog_vars:
            env_content.extend(["", "# DataDog Configuration"])
            for key, value in sorted(datadog_vars.items()):
                env_content.append(f"{key}={value}")
        
        # Add other configuration
        if other_vars:
            env_content.extend(["", "# Other Configuration"])
            for key, value in sorted(other_vars.items()):
                env_content.append(f"{key}={value}")
        
        # Save .env file
        try:
            with open(env_file, 'w') as f:
                f.write("\n".join(env_content))
            self.console.print(f"✅ Configuration saved to: {env_file}", style="green")
            
            # Show what was updated
            new_keys = set(new_env.keys()) - set(existing_env.keys())
            updated_keys = set(new_env.keys()) & set(existing_env.keys())
            
            if new_keys:
                self.console.print(f"📝 Added {len(new_keys)} new environment variables", style="green")
            if updated_keys:
                self.console.print(f"🔄 Updated {len(updated_keys)} existing environment variables", style="blue")
                
        except Exception as e:
            self.console.print(f"❌ Error saving .env file: {e}", style="red")
            return
        
        # Save endpoint-specific configs
        config_dir = self.project_root / "configs"
        config_dir.mkdir(exist_ok=True)
        
        for endpoint_id, config in endpoints.items():
            endpoint_config = {
                "endpoint_id": endpoint_id,
                "providers": config["providers"],
                "name": config["name"],
                "description": config["description"],
                "environment": config.get("environment", {}),
                "pre_run_commands": config.get("pre_run_commands", [])
            }
            
            config_file = config_dir / f"{endpoint_id}.json"
            try:
                with open(config_file, 'w') as f:
                    json.dump(endpoint_config, f, indent=2)
            except Exception as e:
                self.console.print(f"❌ Error saving endpoint config {endpoint_id}: {e}", style="red")
        
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
        table.add_column("Type", style="magenta")
        
        for endpoint_id, config in endpoints.items():
            command = f"python start.py --server"
            endpoint_type = "Wrapper" if config.get("pre_run_commands") else "Direct"
            table.add_row(
                config["name"],
                command,
                ", ".join(config["providers"]),
                endpoint_type
            )
        
        self.console.print(table)
        
        # Show environment setup summary
        env_file = self.project_root / ".env"
        if env_file.exists():
            existing_env = self.load_existing_env()
            
            env_summary = []
            if any(key.startswith("AWS_") for key in existing_env.keys()):
                env_summary.append("🔶 AWS credentials configured")
            if any(key.startswith("DATADOG_") for key in existing_env.keys()):
                env_summary.append("🐕 DataDog credentials configured")
            if existing_env.get("AUTOCOST_PROVIDERS"):
                env_summary.append(f"🎯 Providers: {existing_env['AUTOCOST_PROVIDERS']}")
            
            if env_summary:
                self.console.print(Panel(
                    "\n".join(env_summary),
                    title="📊 Environment Summary",
                    style="blue"
                ))
        
        # Next steps
        next_steps = [
            "🔄 Restart Claude Desktop and/or Cursor if auto-installed",
            "🧪 Test your setup with: python start.py --test",
            "📊 Start analyzing costs with your MCP client",
            "📖 Check README.md for advanced usage examples",
            "🔧 Customize settings in .env file as needed"
        ]
        
        # Add provider-specific next steps
        providers = set()
        for config in endpoints.values():
            providers.update(config["providers"])
        
        if "aws" in providers:
            next_steps.append("🔶 For AWS: Credentials will be captured automatically when you start the server")
        if "datadog" in providers:
            next_steps.append("🐕 For DataDog: Verify API keys in .env file are correct")
        
        self.console.print(Panel(
            "\n".join(next_steps),
            title="📋 Next Steps",
            style="blue"
        ))
        
        # Quick start command
        self.console.print(f"\n🚀 Quick start: python start.py --server", style="bold green")
        
        # Show file locations
        config_info = [
            f"📄 Environment: {env_file}",
            f"📁 Configs: {self.project_root / 'configs'}",
        ]
        
        if (self.project_root / "scripts").exists():
            config_info.append(f"📜 Scripts: {self.project_root / 'scripts'}")
        
        self.console.print(Panel(
            "\n".join(config_info),
            title="📂 Configuration Files",
            style="cyan"
        ))

    def run_setup(self):
        """Run the complete setup process."""
        try:
            # Show banner
            self.show_banner()
            
            # Check Python version
            if not self.check_python_version():
                return False
            
            # Always check and install dependencies first
            self.console.print("\n📦 DEPENDENCY MANAGEMENT", style="bold blue")
            if not self.check_and_install_dependencies():
                self.console.print("❌ Cannot proceed without required dependencies", style="red")
                return False
            
            # Configure providers
            providers_config = self.configure_providers()
            
            # Validate at least one provider is enabled
            enabled_providers = [name for name, enabled in providers_config.items() 
                               if enabled and name != "datadog_config"]
            
            if not enabled_providers:
                self.console.print("❌ No providers enabled. Please enable at least one provider.", style="red")
                return False
            
            self.console.print(f"✅ Enabled providers: {', '.join(enabled_providers)}", style="green")
            
            # Configure endpoints
            endpoints = self.configure_endpoints(providers_config)
            
            # Configure pre-run scripts if needed
            if any(config.get("pre_run_commands") for config in endpoints.values()):
                self.configure_pre_run_scripts(endpoints)
                
                # Create wrapper scripts for endpoints with pre-run commands
                self.create_wrapper_scripts(endpoints)
            
            # Auto-install integrations
            self.auto_install_integrations(endpoints)
            
            # Save configuration (this preserves existing .env settings)
            self.save_configuration(providers_config, endpoints)
            
            # Show completion summary
            self.show_completion_summary(endpoints)
            
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n\n👋 Setup cancelled by user", style="yellow")
            return False
        except Exception as e:
            self.console.print(f"\n❌ Setup failed: {str(e)}", style="red")
            self.console.print("💡 Check the error details above and try again", style="yellow")
            return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autocost Controller - Multi-Cloud Cost Optimization Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start.py                    # Quick setup: capture credentials and verify
  python start.py --configure        # Run full configuration wizard
  python start.py --server           # Start the MCP server
  python start.py --verify           # Verify current setup
  python start.py --test             # Test provider setup and status
        """
    )
    
    parser.add_argument(
        '--configure', '-c',
        action='store_true',
        help='Run the full configuration wizard'
    )
    
    parser.add_argument(
        '--server', '-s',
        action='store_true',
        help='Start the MCP server'
    )
    
    parser.add_argument(
        '--verify', '-v',
        action='store_true',
        help='Verify current setup without making changes'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Test provider setup and show status'
    )
    
    return parser.parse_args()

def main():
    """Main entry point - single script for all operations."""
    args = parse_arguments()
    
    try:
        if args.configure:
            # Full configuration mode
            setup = AutocostSetup()
            setup.show_banner("configure")
            success = setup.run_setup()
            
            if success:
                console.print("\n✨ Autocost Controller is ready to optimize your cloud costs! ✨", style="bold green")
            else:
                console.print("\n💔 Setup incomplete. Please check the errors above and try again.", style="red")
                sys.exit(1)
                
        elif args.server:
            # Server mode - start the integrated MCP server
            # Don't print startup message as it interferes with JSON-RPC communication
            success = run_mcp_server()
            sys.exit(0 if success else 1)
            
        elif args.verify:
            # Verify mode
            setup = AutocostSetup()
            setup.show_banner("verify")
            success = setup.verify_setup()
            
            if success:
                console.print("\n✅ Verification complete - setup is working!", style="bold green")
            else:
                console.print("\n❌ Verification failed - run --configure to fix issues", style="red")
                sys.exit(1)
                
        elif args.test:
            # Test mode - check provider status
            success = test_setup()
            sys.exit(0 if success else 1)
                
        else:
            # Default mode: quick setup
            setup = AutocostSetup()
            setup.show_banner("default")
            success = setup.quick_setup()
            
            if success:
                console.print("\n🎯 Quick Actions:", style="bold blue")
                console.print("   python start.py --server      # Start the MCP server", style="green")
                console.print("   python start.py --configure   # Full configuration", style="blue")
                console.print("   python start.py --verify      # Verify setup", style="cyan")
                console.print("   python start.py --test        # Test provider status", style="yellow")
            else:
                sys.exit(1)
                
    except KeyboardInterrupt:
        console.print("\n\n👋 Cancelled by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ Unexpected error: {str(e)}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main() 