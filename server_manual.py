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

def capture_fresh_credentials():
    """Capture fresh AWS credentials from current environment and save them."""
    try:
        # Test if current environment has working AWS credentials
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        print(f"✅ Found working AWS credentials in environment")
        print(f"   Account: {identity['Account']}")
        print(f"   Identity: {identity['Arn']}")
        
        # Get credentials from current session
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials:
            frozen_credentials = credentials.get_frozen_credentials()
            
            # Save the working credentials
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
            import json
            creds_file.write_text(json.dumps(creds_data, indent=2))
            
            print(f"💾 Captured and saved fresh credentials to {creds_file}")
            return True
            
    except Exception as e:
        print(f"⚠️ Could not capture fresh credentials: {e}")
        return False

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

def setup_aws_credentials():
    """Setup AWS credentials with automatic detection and fallback."""
    print("🔐 Setting up AWS credentials...")
    
    # First, try to capture fresh credentials from environment
    if capture_fresh_credentials():
        return True
    
    # If that fails, try to load saved credentials
    print("🔄 Trying saved credentials...")
    if load_saved_credentials():
        print("✅ Loaded saved credentials")
        return True
    
    print("⚠️ No working credentials found")
    print("💡 To fix this:")
    print("   1. In your terminal, assume your AWS role")
    print("   2. Run: python save_current_session.py")
    print("   3. Restart the MCP server")
    
    return False

def get_enabled_providers():
    """Get list of enabled providers from environment."""
    providers_env = os.environ.get('AUTOCOST_PROVIDERS', 'aws')
    return [p.strip() for p in providers_env.split(',')]

def main():
    """Main server entry point with environment-based configuration."""
    
    # Enable custom tools by default if not explicitly set
    if 'AUTOCOST_ENABLE_CUSTOM_TOOLS' not in os.environ:
        os.environ['AUTOCOST_ENABLE_CUSTOM_TOOLS'] = 'true'
    
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
                        error_msg = status.error_message or "Unknown error"
                        print(f"❌ {provider_name.upper()}: {status.status} - {error_msg}")
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
    
    # Setup AWS credentials with automatic detection
    creds_ready = setup_aws_credentials()
    
    # Get enabled providers from environment
    enabled_providers = get_enabled_providers()
    endpoint_name = os.environ.get('AUTOCOST_ENDPOINT', 'manual')
    
    # Initialize components
    config = Config()
    logger = AutocostLogger("autocost-server")
    
    print(f"🚀 Starting Autocost Controller MCP Server")
    print(f"🎯 Endpoint: {endpoint_name}")
    print(f"🔧 Enabled providers: {', '.join(enabled_providers)}")
    print(f"🔐 AWS credentials: {'✅ Ready' if creds_ready else '⚠️ Not ready'}")
    
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