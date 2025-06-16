#!/usr/bin/env python3
"""
Autocost Controller MCP Server - Credential-aware version
Automatically loads saved credentials and configures providers based on environment variables.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP
from autocost_controller.core.config import Config
from autocost_controller.core.logger import AutocostLogger
from autocost_controller.core.provider_manager import ProviderManager
from autocost_controller.tools import register_all_tools

def load_saved_credentials():
    """Load saved AWS credentials if available."""
    creds_file = project_root / ".aws_credentials.json"
    if creds_file.exists():
        try:
            import json
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
                print(f"⚠️ Saved credentials missing required keys")
                return False
                
        except Exception as e:
            print(f"⚠️ Could not load saved credentials: {e}")
            return False
    return False

def get_enabled_providers():
    """Get list of enabled providers from environment."""
    providers_env = os.environ.get('AUTOCOST_PROVIDERS', 'aws')
    return [p.strip() for p in providers_env.split(',')]

def main():
    """Main server entry point with environment-based configuration."""
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Test mode - check credentials and providers
            print("🧪 Testing Autocost Controller setup...")
            
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
                        print(f"❌ {provider_name.upper()}: {status.status} - {status.error}")
                else:
                    print(f"❌ {provider_name.upper()}: not configured")
            
            return
        elif sys.argv[1] == "--help":
            print("Autocost Controller MCP Server")
            print("Usage:")
            print("  python server_manual.py          # Start MCP server")
            print("  python server_manual.py --test   # Test setup and credentials")
            print("\nEnvironment Variables:")
            print("  AUTOCOST_PROVIDERS    # Comma-separated list of providers (default: aws)")
            print("  AUTOCOST_ENDPOINT     # Endpoint identifier (optional)")
            return
    
    # Load saved credentials first
    creds_loaded = load_saved_credentials()
    
    # Get enabled providers from environment
    enabled_providers = get_enabled_providers()
    endpoint_name = os.environ.get('AUTOCOST_ENDPOINT', 'manual')
    
    # Initialize components
    config = Config()
    logger = AutocostLogger("autocost-server")
    
    print(f"🚀 Starting Autocost Controller MCP Server")
    print(f"🎯 Endpoint: {endpoint_name}")
    print(f"🔧 Enabled providers: {', '.join(enabled_providers)}")
    
    if creds_loaded:
        print("✅ Loaded saved AWS credentials")
    
    # Create FastMCP instance
    mcp = FastMCP("Autocost Controller")
    
    # Initialize provider manager
    provider_manager = ProviderManager(config, logger)
    
    # Register all tools (includes core tools and provider-specific tools)
    register_all_tools(mcp, provider_manager, config, logger)
    
    logger.info(f"🎯 MCP Server ready with {len(enabled_providers)} provider(s)")
    
    # Run the server
    mcp.run()

if __name__ == "__main__":
    main() 