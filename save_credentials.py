#!/usr/bin/env python3
"""
Autocost Controller - Credential Saver

Save current cloud provider credentials to secure files that the server can load.

Usage:
1. For AWS: 
   - In terminal: assume billing_read_only.root.okta  
   - In same terminal: python save_credentials.py --provider aws
2. For GCP:
   - Set up application default credentials or service account
   - Run: python save_credentials.py --provider gcp
3. Credentials are saved for the server to use
4. Start Claude Desktop normally
"""

import os
import sys
import json
import stat
from pathlib import Path
import argparse
import boto3

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Provider-specific credential files
CREDENTIALS_FILES = {
    'aws': project_root / ".aws_credentials.json",
    'gcp': project_root / ".gcp_credentials.json"
}

def save_aws_credentials():
    """Save current AWS credentials to a file."""
    try:
        # Test current credentials
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        print("✅ Current AWS credentials are valid")
        print(f"Account: {identity.get('Account')}")
        print(f"User/Role: {identity.get('Arn', 'Unknown')}")
        
        # Get credentials from environment or default credential chain
        credentials_data = {}
        
        # Method 1: Environment variables
        if 'AWS_ACCESS_KEY_ID' in os.environ:
            credentials_data = {
                'aws_access_key_id': os.environ['AWS_ACCESS_KEY_ID'],
                'aws_secret_access_key': os.environ['AWS_SECRET_ACCESS_KEY'],
                'aws_session_token': os.environ.get('AWS_SESSION_TOKEN'),
                'aws_profile': os.environ.get('AWS_PROFILE'),
                'aws_region': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                'source': 'environment'
            }
        
        # Method 2: Profile-based (check if profile is set)
        elif 'AWS_PROFILE' in os.environ:
            credentials_data = {
                'aws_profile': os.environ['AWS_PROFILE'],
                'aws_region': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                'source': 'profile'
            }
            
            # Try to get temporary credentials from the profile
            session = boto3.Session(profile_name=os.environ['AWS_PROFILE'])
            creds = session.get_credentials()
            if creds:
                credentials_data.update({
                    'aws_access_key_id': creds.access_key,
                    'aws_secret_access_key': creds.secret_key,
                    'aws_session_token': creds.token,
                })
        
        # Method 3: Get from current session
        else:
            session = boto3.Session()
            creds = session.get_credentials()
            if creds:
                credentials_data = {
                    'aws_access_key_id': creds.access_key,
                    'aws_secret_access_key': creds.secret_key,
                    'aws_session_token': creds.token,
                    'aws_region': session.region_name or 'us-east-1',
                    'source': 'session'
                }
        
        if not credentials_data:
            print("❌ Could not extract AWS credentials")
            return False
        
        # Add metadata
        credentials_data['saved_at'] = identity.get('Arn', 'Unknown')
        credentials_data['account'] = identity.get('Account')
        
        # Save to file with restrictive permissions
        with open(CREDENTIALS_FILES['aws'], 'w') as f:
            json.dump(credentials_data, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(CREDENTIALS_FILES['aws'], stat.S_IRUSR | stat.S_IWUSR)
        
        print(f"✅ AWS credentials saved to: {CREDENTIALS_FILES['aws']}")
        print(f"🔒 File permissions set to owner-only")
        print(f"📊 Source: {credentials_data['source']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving AWS credentials: {e}")
        return False

def save_gcp_credentials():
    """Save current GCP credentials to a file."""
    try:
        # For now, we'll just check if the credentials file exists
        # This will be expanded in future versions
        gcp_creds_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
        if not os.path.exists(gcp_creds_path):
            print("❌ No GCP application default credentials found")
            print("Please run 'gcloud auth application-default login' first")
            return False
            
        # Copy the credentials to our secure location
        with open(gcp_creds_path, 'r') as f:
            creds_data = json.load(f)
            
        # Add metadata
        creds_data['source'] = 'application_default'
        creds_data['saved_at'] = os.path.getmtime(gcp_creds_path)
        
        # Save to file with restrictive permissions
        with open(CREDENTIALS_FILES['gcp'], 'w') as f:
            json.dump(creds_data, f, indent=2)
            
        # Set restrictive permissions
        os.chmod(CREDENTIALS_FILES['gcp'], stat.S_IRUSR | stat.S_IWUSR)
        
        print(f"✅ GCP credentials saved to: {CREDENTIALS_FILES['gcp']}")
        print(f"🔒 File permissions set to owner-only")
        print(f"📊 Source: application_default")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving GCP credentials: {e}")
        return False

def load_saved_credentials(provider='aws'):
    """Load and set saved credentials as environment variables."""
    creds_file = CREDENTIALS_FILES.get(provider)
    if not creds_file or not creds_file.exists():
        return False, f"No saved {provider.upper()} credentials file found"
    
    try:
        with open(creds_file, 'r') as f:
            creds = json.load(f)
        
        if provider == 'aws':
            # Set AWS environment variables
        if 'aws_access_key_id' in creds and creds['aws_access_key_id']:
            os.environ['AWS_ACCESS_KEY_ID'] = creds['aws_access_key_id']
            os.environ['AWS_SECRET_ACCESS_KEY'] = creds['aws_secret_access_key']
            if creds.get('aws_session_token'):
                os.environ['AWS_SESSION_TOKEN'] = creds['aws_session_token']
        
        if 'aws_profile' in creds and creds['aws_profile']:
            os.environ['AWS_PROFILE'] = creds['aws_profile']
        
        if 'aws_region' in creds and creds['aws_region']:
            os.environ['AWS_DEFAULT_REGION'] = creds['aws_region']
        
        # Test if credentials work
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
            return True, f"Loaded AWS credentials for {identity.get('Account')}"
        
        elif provider == 'gcp':
            # For GCP, we'll just verify the file exists
            return True, "Loaded GCP credentials"
        
    except Exception as e:
        return False, f"Error loading {provider.upper()} credentials: {e}"

def show_status(provider=None):
    """Show credential status."""
    print("🔍 **CREDENTIAL STATUS**")
    print("=" * 30)
    
    providers_to_check = [provider] if provider else CREDENTIALS_FILES.keys()
    
    for prov in providers_to_check:
        print(f"\n{prov.upper()} Status:")
        creds_file = CREDENTIALS_FILES[prov]
    
    # Check saved file
        if creds_file.exists():
        try:
                with open(creds_file, 'r') as f:
                creds = json.load(f)
            
                print(f"✅ Saved credentials: {creds_file}")
            print(f"📊 Source: {creds.get('source', 'unknown')}")
                if prov == 'aws':
            print(f"🔑 Account: {creds.get('account', 'unknown')}")
            print(f"👤 Saved by: {creds.get('saved_at', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Error reading saved credentials: {e}")
    else:
            print(f"❌ No saved {prov.upper()} credentials found")
    
    # Check current environment
        if prov == 'aws':
            print("\n🌍 Current AWS Environment:")
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Current AWS credentials work")
        print(f"🔑 Account: {identity.get('Account')}")
        print(f"👤 User/Role: {identity.get('Arn', 'Unknown')}")
    except Exception as e:
        print(f"❌ Current AWS credentials: {e}")

def clear_credentials(provider=None):
    """Clear saved credentials."""
    providers_to_clear = [provider] if provider else CREDENTIALS_FILES.keys()
    
    for prov in providers_to_clear:
        creds_file = CREDENTIALS_FILES[prov]
        if creds_file.exists():
            creds_file.unlink()
            print(f"✅ Cleared saved {prov.upper()} credentials: {creds_file}")
    else:
            print(f"❌ No saved {prov.upper()} credentials to clear")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Autocost Controller - Credential Management"
    )
    
    parser.add_argument(
        "--provider",
        choices=['aws', 'gcp'],
        help="Cloud provider to manage credentials for"
    )
    
    parser.add_argument(
        "--load",
        action="store_true",
        help="Load saved credentials (for testing)"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show credential status"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear saved credentials"
    )
    
    args = parser.parse_args()
    
    if args.load:
        success, message = load_saved_credentials(args.provider)
        print(f"{'✅' if success else '❌'} {message}")
        sys.exit(0 if success else 1)
    
    elif args.status:
        show_status(args.provider)
        sys.exit(0)
    
    elif args.clear:
        clear_credentials(args.provider)
        sys.exit(0)
    
    else:
        # Save current credentials based on provider
        if args.provider == 'aws':
            success = save_aws_credentials()
        elif args.provider == 'gcp':
            success = save_gcp_credentials()
        else:
            print("❌ Please specify a provider with --provider [aws|gcp]")
            sys.exit(1)
            
        if success:
            print(f"\n🎯 **Next Steps:**")
            print(f"1. {args.provider.upper()} credentials are now saved for the server to use")
            print("2. Start Claude Desktop - the server will load these credentials")
            print(f"3. Use 'python save_credentials.py --provider {args.provider} --status' to check status")
            print("4. Re-run this script after re-authenticating")
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 