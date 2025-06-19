#!/usr/bin/env python3
"""
Autocost Controller - GCP Session Saver

Save current GCP session credentials to a secure file that the server can load.
This script is used internally by save_credentials_gcp.py.
"""

import os
import json
import sys
from pathlib import Path
from google.cloud.resourcemanager_v3 import ProjectsClient
from google.auth import default

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def capture_and_save_credentials():
    """Capture current GCP credentials and save them for the MCP server."""
    try:
        # Test if credentials work by listing projects
        client = ProjectsClient()
        request = {"page_size": 1}
        projects = client.search_projects(request=request)
        project = next(iter(projects), None)
        
        if not project:
            print("❌ No projects found or insufficient permissions")
            return False
        
        print("✅ Current GCP credentials are valid!")
        print(f"Project: {project.project_id}")
        print(f"Name: {project.display_name}")
        
        # Get credentials from the current session
        credentials, project_id = default()
        
        if not credentials:
            print("❌ Could not retrieve credentials from current session")
            return False
        
        # Prepare credentials data
        creds_data = {}
        
        # Check if using service account
        if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
            service_account_path = os.environ['GOOGLE_APPLICATION_CREDENTIALS']
            if os.path.exists(service_account_path):
                creds_data = {
                    'type': 'service_account',
                    'credentials_file': service_account_path,
                    'project_id': project_id
                }
                print("🔑 Service account credentials detected")
        
        # If not service account, try application default credentials
        if not creds_data and hasattr(credentials, 'token'):
            creds_data = {
                'type': 'application_default',
                'token': credentials.token,
                'project_id': project_id
            }
            print("🔑 Application default credentials detected")
        
        if not creds_data:
            print("❌ Could not determine credential type")
            return False
        
        # Save to file that the MCP server will read
        creds_file = project_root / ".gcp_credentials.json"
        creds_file.write_text(json.dumps(creds_data, indent=2))
        
        print(f"💾 Credentials saved to {creds_file.absolute()}")
        print("🚀 You can now start/restart the MCP server - it will use these credentials")
        
        return True
        
    except Exception as e:
        print(f"❌ Error capturing credentials: {e}")
        print("Make sure you have run 'gcloud auth application-default login' or set up a service account")
        return False

def main():
    """Main entry point."""
    print("🔐 GCP Session Saver")
    print("=" * 40)
    
    if capture_and_save_credentials():
        print("\n🎯 **Next Steps:**")
        print("1. Session credentials are now saved for the server to use")
        print("2. Start the MCP server to use these credentials")
        print("3. Re-run this script after re-authenticating if needed")
    else:
        print("\n❌ Failed to save session credentials")
        print("💡 Make sure you have:")
        print("   1. Installed GCP SDK and run: gcloud auth application-default login")
        print("   OR")
        print("   2. Set up a service account and set GOOGLE_APPLICATION_CREDENTIALS")
        sys.exit(1)

if __name__ == "__main__":
    main() 