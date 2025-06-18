#!/usr/bin/env python3
"""
Save current AWS session credentials for MCP server.
Run this script in the terminal where you've already assumed your AWS role.
"""

import os
import json
import boto3
from pathlib import Path

def capture_and_save_credentials():
    """Capture current AWS credentials and save them for the MCP server."""
    try:
        # Test if credentials work by getting caller identity
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        print("✅ Current AWS credentials are valid!")
        print(f"Account: {identity['Account']}")
        print(f"User/Role: {identity['Arn']}")
        
        # Get credentials from the current session
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials is None:
            print("❌ Could not retrieve credentials from current session")
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
            print("🔑 Session token detected (assumed role credentials)")
        
        # Save to file that the MCP server will read
        creds_file = Path(".aws_credentials.json")
        creds_file.write_text(json.dumps(creds_data, indent=2))
        
        print(f"💾 Credentials saved to {creds_file.absolute()}")
        print("🚀 You can now start/restart the MCP server - it will use these credentials")
        
        return True
        
    except Exception as e:
        print(f"❌ Error capturing credentials: {e}")
        print("Make sure you have run 'aws configure' or assumed a role in this terminal")
        return False

if __name__ == "__main__":
    print("🔐 AWS Credential Capture Tool")
    print("=" * 40)
    
    if capture_and_save_credentials():
        print("\n✅ Success! The MCP server will now use your current AWS session.")
    else:
        print("\n❌ Failed to capture credentials. Please check your AWS setup.") 