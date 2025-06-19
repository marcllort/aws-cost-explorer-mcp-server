#!/usr/bin/env python3
"""
Autocost Controller MCP Server - Credential-aware version
Automatically loads saved credentials and configures providers based on environment variables.
"""

import asyncio
import sys
import os
import json
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP
from autocost_controller.core.config import Config
from autocost_controller.core.logger import AutocostLogger
from autocost_controller.core.provider_manager import ProviderManager
from autocost_controller.tools import register_all_tools

def capture_fresh_credentials(provider='aws'):
    """Capture fresh credentials from current environment and save them."""
    if provider == 'aws':
        return capture_fresh_aws_credentials()
    elif provider == 'gcp':
        return capture_fresh_gcp_credentials()
    return False

def capture_fresh_aws_credentials():
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
            
            print(f"💾 Captured and saved fresh AWS credentials to {creds_file}")
            return True
            
    except Exception as e:
        print(f"⚠️ Could not capture fresh AWS credentials: {e}")
        return False

def capture_fresh_gcp_credentials():
    """Capture fresh GCP credentials from current environment."""
    try:
        # Check for application default credentials
        gcp_creds_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
        if not os.path.exists(gcp_creds_path):
            print("❌ No GCP application default credentials found")
            return False
            
        # Verify GCP project ID is set
        if 'GCP_PROJECT_ID' not in os.environ:
            print("❌ GCP project ID not set. Please set GCP_PROJECT_ID in config or environment")
            return False
            
        # Copy the credentials to our location
        import shutil
        target_creds = project_root / ".gcp_credentials.json"
        shutil.copy2(gcp_creds_path, target_creds)
        
        print(f"💾 Captured and saved fresh GCP credentials to {target_creds}")
        print(f"📝 Using GCP project: {os.environ.get('GCP_PROJECT_ID')}")
        return True
        
    except Exception as e:
        print(f"⚠️ Could not capture fresh GCP credentials: {e}")
        return False

def load_saved_credentials(provider='aws'):
    """Load saved credentials if available."""
    if provider == 'aws':
        return load_saved_aws_credentials()
    elif provider == 'gcp':
        return load_saved_gcp_credentials()
    return False

def load_saved_aws_credentials():
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
                print(f"⚠️ Saved AWS credentials missing required keys")
                return False
                
        except Exception as e:
            print(f"⚠️ Could not load saved AWS credentials: {e}")
            return False
    return False

def load_saved_gcp_credentials():
    """Load saved GCP credentials if available."""
    creds_file = project_root / ".gcp_credentials.json"
    if creds_file.exists():
        try:
            # Set the application credentials path
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_file)
            return True
        except Exception as e:
            print(f"⚠️ Could not load saved GCP credentials: {e}")
            return False
    return False

def setup_credentials(provider='aws'):
    """Setup credentials with automatic detection and fallback."""
    print(f"🔐 Setting up {provider.upper()} credentials...")
    
    # First, try to capture fresh credentials from environment
    if capture_fresh_credentials(provider):
        return True
    
    # If that fails, try to load saved credentials
    print(f"🔄 Trying saved {provider.upper()} credentials...")
    if load_saved_credentials(provider):
        print(f"✅ Loaded saved {provider.upper()} credentials")
        return True
    
    print(f"⚠️ No working {provider.upper()} credentials found")
    if provider == 'aws':
        print("💡 To fix this:")
        print("   1. In your terminal, assume your AWS role")
        print("   2. Run: python save_credentials.py --provider aws")
        print("   3. Restart the MCP server")
    elif provider == 'gcp':
        print("💡 To fix this:")
        print("   1. Run: gcloud auth application-default login")
        print("   2. Run: python save_credentials.py --provider gcp")
        print("   3. Restart the MCP server")
    
    return False

def get_enabled_providers():
    """Get list of enabled providers from environment."""
    providers_env = os.environ.get('AUTOCOST_PROVIDERS', 'aws')
    return [p.strip() for p in providers_env.split(',')]

def load_config(config_path=None):
    """Load configuration from file if provided."""
    if not config_path:
        return None
        
    try:
        with open(config_path) as f:
            config_data = json.load(f)
            
        # Set environment variables from config
        if 'providers' in config_data:
            os.environ['AUTOCOST_PROVIDERS'] = ','.join(config_data['providers'])
        if 'endpoint' in config_data:
            os.environ['AUTOCOST_ENDPOINT'] = config_data['endpoint']
            
        # Handle provider-specific configurations
        if 'gcp' in config_data:
            gcp_config = config_data['gcp']
            if 'project_id' in gcp_config:
                os.environ['GCP_PROJECT_ID'] = gcp_config['project_id']
                print(f"📝 Set GCP project ID: {gcp_config['project_id']}")
            if 'organization_id' in gcp_config:
                os.environ['GCP_ORGANIZATION_ID'] = gcp_config['organization_id']
                print(f"🏢 Set GCP organization ID: {gcp_config['organization_id']}")
                
        return config_data
    except Exception as e:
        print(f"⚠️ Error loading config from {config_path}: {e}")
        return None

def main():
    """Main server entry point with environment-based configuration."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Autocost Controller MCP Server")
    parser.add_argument("--test", action="store_true", help="Test setup and credentials")
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()
    
    # Enable custom tools by default if not explicitly set
    if 'AUTOCOST_ENABLE_CUSTOM_TOOLS' not in os.environ:
        os.environ['AUTOCOST_ENABLE_CUSTOM_TOOLS'] = 'true'
    
    # Load configuration if provided
    config_data = None
    if args.config:
        config_data = load_config(args.config)
        if config_data:
            print(f"📝 Loaded configuration from {args.config}")
            
            # Set environment variables from config
            if 'providers' in config_data:
                os.environ['AUTOCOST_PROVIDERS'] = ','.join(config_data['providers'])
            if 'endpoint' in config_data:
                os.environ['AUTOCOST_ENDPOINT'] = config_data['endpoint']
            
            # Handle GCP organization ID from config
            if 'gcp' in config_data and 'organization_id' in config_data['gcp']:
                os.environ['GCP_ORGANIZATION_ID'] = config_data['gcp']['organization_id']
                print(f"🏢 Set GCP organization ID: {config_data['gcp']['organization_id']}")
    
    # Also check for GCP organization ID in environment variables
    if 'GCP_ORGANIZATION_ID' in os.environ:
        print(f"🏢 Using GCP organization ID: {os.environ['GCP_ORGANIZATION_ID']}")
    elif 'GCP_PROJECT_ID' in os.environ:
        print(f"📝 Using GCP project ID: {os.environ['GCP_PROJECT_ID']}")
    elif 'gcp' in get_enabled_providers():
        print("⚠️ No GCP project or organization ID configured")
    
    if args.test:
        # Test mode - check credentials and providers
        print("🧪 Testing Autocost Controller setup...")
        
        enabled_providers = get_enabled_providers()
        print(f"🎯 Enabled providers: {', '.join(enabled_providers)}")
        
        # Test credentials for each provider
        for provider in enabled_providers:
            creds_loaded = load_saved_credentials(provider)
            if creds_loaded:
                print(f"✅ Saved {provider.upper()} credentials loaded")
            else:
                print(f"⚠️ No saved {provider.upper()} credentials found, using environment")
            
            # Test providers
            config = Config()
            logger = AutocostLogger("autocost-test")
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
    
    # Setup credentials for each enabled provider
    enabled_providers = get_enabled_providers()
    creds_status = {}
    for provider in enabled_providers:
        creds_status[provider] = setup_credentials(provider)
    
    endpoint_name = os.environ.get('AUTOCOST_ENDPOINT', 'manual')
    
    # Initialize components
    config = Config()
    logger = AutocostLogger("autocost-server")
    
    print(f"🚀 Starting Autocost Controller MCP Server")
    print(f"🎯 Endpoint: {endpoint_name}")
    print(f"🔧 Enabled providers: {', '.join(enabled_providers)}")
    for provider in enabled_providers:
        print(f"🔐 {provider.upper()} credentials: {'✅ Ready' if creds_status[provider] else '⚠️ Not ready'}")
    
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