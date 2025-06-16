#!/usr/bin/env python3
"""
Autocost Controller - Credential Saver

Save current AWS credentials to a secure file that the server can load.

Usage:
1. In terminal: assume billing_read_only.root.okta  
2. In same terminal: python save_credentials.py
3. Credentials are saved for the server to use
4. Start Claude Desktop normally
"""

import os
import sys
import json
import stat
from pathlib import Path
import boto3

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

CREDENTIALS_FILE = project_root / ".aws_credentials.json"

def save_current_credentials():
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
            print("❌ Could not extract credentials")
            return False
        
        # Add metadata
        credentials_data['saved_at'] = identity.get('Arn', 'Unknown')
        credentials_data['account'] = identity.get('Account')
        
        # Save to file with restrictive permissions
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials_data, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)
        
        print(f"✅ Credentials saved to: {CREDENTIALS_FILE}")
        print(f"🔒 File permissions set to owner-only")
        print(f"📊 Source: {credentials_data['source']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return False

def load_saved_credentials():
    """Load and set saved credentials as environment variables."""
    
    if not CREDENTIALS_FILE.exists():
        return False, "No saved credentials file found"
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
        
        # Set environment variables
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
        
        return True, f"Loaded credentials for {identity.get('Account')}"
        
    except Exception as e:
        return False, f"Error loading credentials: {e}"

def show_status():
    """Show credential status."""
    print("🔍 **CREDENTIAL STATUS**")
    print("=" * 30)
    
    # Check saved file
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                creds = json.load(f)
            
            print(f"✅ Saved credentials: {CREDENTIALS_FILE}")
            print(f"📊 Source: {creds.get('source', 'unknown')}")
            print(f"🔑 Account: {creds.get('account', 'unknown')}")
            print(f"👤 Saved by: {creds.get('saved_at', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Error reading saved credentials: {e}")
    else:
        print("❌ No saved credentials found")
    
    # Check current environment
    print("\n🌍 **CURRENT ENVIRONMENT:**")
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Current AWS credentials work")
        print(f"🔑 Account: {identity.get('Account')}")
        print(f"👤 User/Role: {identity.get('Arn', 'Unknown')}")
    except Exception as e:
        print(f"❌ Current AWS credentials: {e}")

def clear_credentials():
    """Clear saved credentials."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
        print(f"✅ Cleared saved credentials: {CREDENTIALS_FILE}")
    else:
        print("❌ No saved credentials to clear")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Autocost Controller - Credential Management"
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
        success, message = load_saved_credentials()
        print(f"{'✅' if success else '❌'} {message}")
        sys.exit(0 if success else 1)
    
    elif args.status:
        show_status()
        sys.exit(0)
    
    elif args.clear:
        clear_credentials()
        sys.exit(0)
    
    else:
        # Save current credentials
        success = save_current_credentials()
        if success:
            print("\n🎯 **Next Steps:**")
            print("1. Credentials are now saved for the server to use")
            print("2. Start Claude Desktop - the server will load these credentials")
            print("3. Use 'python save_credentials.py --status' to check status")
            print("4. Re-run this script after re-authenticating")
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 