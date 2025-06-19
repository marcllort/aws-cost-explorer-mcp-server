#!/usr/bin/env python3
"""
Autocost Controller - GCP Credential Saver

Save current GCP credentials to a secure file that the server can load.

Usage:
1. Set up GCP credentials (gcloud auth application-default login)
   OR set GOOGLE_APPLICATION_CREDENTIALS for service account
2. Run: python save_credentials_gcp.py [project_id]
3. Credentials are saved for the server to use
"""

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from google.cloud.resourcemanager_v3 import ProjectsClient
from google.oauth2 import service_account

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

CREDENTIALS_FILE = project_root / ".gcp_credentials.json"

def get_gcloud_project() -> Optional[str]:
    """Get project ID from gcloud config."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True
        )
        project_id = result.stdout.strip()
        return project_id if project_id != "" else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def validate_project_access(project_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate access to the specified project."""
    try:
        client = ProjectsClient()
        project = client.get_project(name=f"projects/{project_id}")
        return True, project.project_id, project.display_name
    except Exception as e:
        print(f"❌ Error accessing project {project_id}: {e}")
        return False, None, None

def save_current_credentials(project_id: Optional[str] = None) -> bool:
    """Save current GCP credentials to a file."""
    try:
        # Try to get project ID from different sources
        if not project_id:
            # 1. Try environment variable
            project_id = os.environ.get("GCP_PROJECT_ID")
            
            # 2. Try gcloud config
            if not project_id:
                project_id = get_gcloud_project()
                
            # 3. Try service account file
            if not project_id and "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
                service_account_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
                if os.path.exists(service_account_path):
                    with open(service_account_path, "r") as f:
                        service_account_json = json.load(f)
                        project_id = service_account_json.get("project_id")
        
        if not project_id:
            print("❌ No project ID found. Please specify using:")
            print("   1. Command line argument: python save_credentials_gcp.py PROJECT_ID")
            print("   2. Environment variable: GCP_PROJECT_ID")
            print("   3. gcloud config set project PROJECT_ID")
            print("   4. Service account credentials")
            return False

        # Validate project access
        success, confirmed_project_id, project_name = validate_project_access(project_id)
        if not success:
            return False
        
        print("✅ Current GCP credentials are valid")
        print(f"Project ID: {confirmed_project_id}")
        print(f"Project Name: {project_name}")
        
        credentials_data = {}
        
        # Method 1: Service Account JSON file
        if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            service_account_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            if os.path.exists(service_account_path):
                with open(service_account_path, "r") as f:
                    service_account_json = json.load(f)
                
                credentials_data = {
                    "type": "service_account",
                    "credentials_file": service_account_path,
                    "project_id": confirmed_project_id,
                    "client_email": service_account_json.get("client_email"),
                    "source": "service_account"
                }
        
        # Method 2: Application Default Credentials
        if not credentials_data:
            try:
                credentials, _ = default()
                if hasattr(credentials, "token"):
                    credentials_data = {
                        "type": "application_default",
                        "token": credentials.token,
                        "project_id": confirmed_project_id,
                        "source": "application_default"
                    }
            except DefaultCredentialsError:
                print("❌ No application default credentials found")
                print("💡 Run: gcloud auth application-default login")
                return False
        
        if not credentials_data:
            print("❌ Could not extract credentials")
            return False
        
        # Add metadata
        credentials_data["saved_at"] = confirmed_project_id
        credentials_data["project_name"] = project_name
        
        # Save to file with restrictive permissions
        with open(CREDENTIALS_FILE, "w") as f:
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

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Save GCP credentials for Autocost Controller")
    parser.add_argument("project_id", nargs="?", help="GCP project ID (optional)")
    args = parser.parse_args()
    
    print("🔐 GCP Credential Saver")
    print("=" * 40)

    if save_current_credentials(args.project_id):
        print("\n🎯 **Next Steps:**")
        print("1. Credentials are now saved for the server to use")
        print("2. Start the MCP server to use these credentials")
        print("3. Re-run this script after re-authenticating if needed")
    else:
        print("\n❌ Failed to save credentials")
        print("💡 Make sure you have:")
        print("   1. Installed GCP SDK and run: gcloud auth application-default login")
        print("   OR")
        print("   2. Set up a service account and set GOOGLE_APPLICATION_CREDENTIALS")
        sys.exit(1)

if __name__ == "__main__":
    main() 