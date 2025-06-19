#!/usr/bin/env python3
"""
Autocost Controller - GCP Credential Saver

Save current GCP credentials to a secure file that the server can load.

Usage:
1. Set up GCP credentials (gcloud auth application-default login)
   OR set GOOGLE_APPLICATION_CREDENTIALS for service account
2. Run: python save_credentials_gcp.py [project_id] [--org-id ORGANIZATION_ID] [--interactive-org]
   - If no project_id is provided, uses active project from: gcloud config get-value project
   - If no --org-id is provided, auto-detects from config files or environment
   - If organization ID is not found, prompts user to enter it interactively
   - Use --interactive-org to force interactive prompt even if organization ID is detected
   - Automatically detects both project and organization from multiple sources
3. Credentials are saved for the server to use

Auto-detection priority:
Project ID:
1. Command line argument (if provided)
2. gcloud config get-value project (most common)
3. GCP_PROJECT_ID environment variable  
4. Service account file project_id field

Organization ID:
1. Command line argument --org-id (if provided)
2. GCP_ORGANIZATION_ID environment variable
3. Config files (configs/gcp.json, configs/unified.json)
4. Project ancestors via gcloud (gcloud projects get-ancestors PROJECT_ID)
5. Interactive user input if not found automatically
6. Optional - not required for project-level access

Examples:
  python save_credentials_gcp.py                          # Auto-detect everything, prompt for org if not found
  python save_credentials_gcp.py my-project-123           # Specify project, auto-detect org
  python save_credentials_gcp.py --org-id 123456789012    # Auto-detect project, specify org  
  python save_credentials_gcp.py my-project --org-id 123456789012  # Specify both
  python save_credentials_gcp.py --interactive-org        # Auto-detect project, interactive org prompt
  python save_credentials_gcp.py my-project --interactive-org      # Specify project, interactive org prompt
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

def get_organization_id_from_ancestors(project_id: str, quick: bool = True) -> Optional[str]:
    """Get organization ID from project ancestors using gcloud (fast with timeout)."""
    if not quick:
        return None  # Skip if not in quick mode
        
    try:
        # Very short timeout for speed
        result = subprocess.run(
            ["gcloud", "projects", "get-ancestors", project_id, "--format=value(id,type)", "--quiet"],
            capture_output=True,
            text=True,
            timeout=5,  # Reduced to 5 seconds
            check=True
        )
        
        # Quick parse - first organization found
        for line in result.stdout.strip().split('\n'):
            if '\t' in line and 'organization' in line.lower():
                return line.split('\t')[0]
        
        return None
        
    except subprocess.TimeoutExpired:
        return None  # Silent timeout
    except:
        return None  # Silent fail for speed

def get_organization_id(project_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Get organization ID from various sources."""
    org_id = None
    org_source = None
    
    # 1. Try environment variable
    org_id = os.environ.get("GCP_ORGANIZATION_ID")
    if org_id:
        org_source = "GCP_ORGANIZATION_ID environment variable"
        return org_id, org_source
    
    # 2. Try existing config files
    config_files = [
        project_root / "configs" / "gcp.json",
        project_root / "configs" / "unified.json"
    ]
    
    for config_file in config_files:
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    if config_data.get("gcp", {}).get("organization_id"):
                        org_id = config_data["gcp"]["organization_id"]
                        org_source = f"config file ({config_file.name})"
                        return org_id, org_source
            except (json.JSONDecodeError, KeyError):
                continue
    
    # 3. Try to get organization from project ancestors (quick lookup with timeout)
    if project_id:
        org_id = get_organization_id_from_ancestors(project_id)
        if org_id:
            org_source = "project ancestors"
            return org_id, org_source
    
    # 4. Try to detect from gcloud properties (fallback)
    try:
        # Try to get organization from gcloud properties (if set)
        result = subprocess.run(
            ["gcloud", "config", "get-value", "billing/quota_project"],
            capture_output=True,
            text=True
        )
        # This is a fallback - organization ID detection via gcloud is limited
        # Most users will need to set it manually
    except:
        pass
    
    return None, None

def prompt_for_organization_id() -> Optional[str]:
    """Interactively prompt user for organization ID if not detected."""
    print("\n🏢 **Organization ID Setup**")
    print("=" * 40)
    print("Organization ID is optional but recommended for:")
    print("  • Organization-level billing analysis")
    print("  • Cross-project cost analysis")
    print("  • Organization policies and quotas")
    print()
    print("💡 **How to find your Organization ID:**")
    print("  1. Go to: https://console.cloud.google.com/iam-admin/settings")
    print("  2. Look for 'Organization ID' at the top")
    print("  3. Or run: gcloud organizations list")
    print()
    
    while True:
        try:
            response = input("Enter your Organization ID (or press Enter to skip): ").strip()
            
            if not response:
                print("⏭️ Skipping organization ID (you can add it later)")
                return None
            
            # Basic validation - organization IDs are typically numeric
            if response.isdigit() and len(response) >= 10:
                confirm = input(f"✅ Confirm Organization ID: {response} (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return response
                else:
                    print("❌ Organization ID not confirmed, please try again")
                    continue
            else:
                print("⚠️ Organization ID should be a numeric value (typically 12+ digits)")
                print("Example: 123456789012")
                
                # Allow user to proceed anyway if they're sure
                confirm = input(f"Use '{response}' anyway? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return response
                else:
                    continue
                    
        except KeyboardInterrupt:
            print("\n\n⏭️ Skipping organization ID setup")
            return None
        except EOFError:
            print("\n⏭️ Skipping organization ID setup")
            return None

def prompt_for_organization_id_with_default(current_org_id: str) -> Optional[str]:
    """Interactively prompt user for organization ID with a default value."""
    print(f"\n🏢 **Organization ID Confirmation**")
    print("=" * 40)
    print(f"Current Organization ID: {current_org_id}")
    print()
    print("You can:")
    print("  • Press Enter to keep the current Organization ID")
    print("  • Enter a new Organization ID to override")
    print("  • Type 'none' to remove the Organization ID")
    print()
    
    while True:
        try:
            response = input(f"Organization ID [{current_org_id}]: ").strip()
            
            if not response:
                # Keep current value
                return None
            
            if response.lower() in ['none', 'null', 'skip']:
                print("⏭️ Removing organization ID")
                return ""  # Empty string to indicate removal
            
            # Basic validation - organization IDs are typically numeric
            if response.isdigit() and len(response) >= 10:
                confirm = input(f"✅ Confirm new Organization ID: {response} (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return response
                else:
                    print("❌ Organization ID not confirmed, please try again")
                    continue
            else:
                print("⚠️ Organization ID should be a numeric value (typically 12+ digits)")
                print("Example: 123456789012")
                
                # Allow user to proceed anyway if they're sure
                confirm = input(f"Use '{response}' anyway? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return response
                else:
                    continue
                    
        except KeyboardInterrupt:
            print(f"\n\n✅ Keeping current Organization ID: {current_org_id}")
            return None
        except EOFError:
            print(f"\n✅ Keeping current Organization ID: {current_org_id}")
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

def save_current_credentials(project_id: Optional[str] = None, organization_id: Optional[str] = None, interactive_org: bool = False, check_ancestors: bool = True) -> bool:
    """Save current GCP credentials to a file."""
    try:
        project_source = None
        
        # Try to get project ID from different sources
        if not project_id:
            print("🔍 No project ID specified, auto-detecting...")
            
            # 1. Try gcloud config (most common)
            project_id = get_gcloud_project()
            if project_id:
                project_source = "gcloud config"
                print(f"✅ Using project from gcloud config: {project_id}")
            
            # 2. Try environment variable
            if not project_id:
                project_id = os.environ.get("GCP_PROJECT_ID")
                if project_id:
                    project_source = "GCP_PROJECT_ID environment variable"
                    print(f"✅ Using project from environment: {project_id}")
                
            # 3. Try service account file
            if not project_id and "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
                service_account_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
                if os.path.exists(service_account_path):
                    with open(service_account_path, "r") as f:
                        service_account_json = json.load(f)
                        project_id = service_account_json.get("project_id")
                    if project_id:
                        project_source = "service account file"
                        print(f"✅ Using project from service account: {project_id}")
        else:
            project_source = "command line argument"
            print(f"✅ Using project from command line: {project_id}")
        
        if not project_id:
            print("❌ No project ID found. Please specify using:")
            print("   1. Command line argument: python save_credentials_gcp.py PROJECT_ID")
            print("   2. Set active project: gcloud config set project YOUR_PROJECT_ID")  
            print("   3. Environment variable: export GCP_PROJECT_ID=YOUR_PROJECT_ID")
            print("   4. Service account credentials with project_id")
            return False

        # Validate project access
        success, confirmed_project_id, project_name = validate_project_access(project_id)
        if not success:
            return False
        
        print("✅ Current GCP credentials are valid")
        print(f"Project ID: {confirmed_project_id}")
        print(f"Project Name: {project_name}")
        if project_source:
            print(f"Project Source: {project_source}")
        
        # Detect organization ID
        org_source = None
        if not organization_id:
            print("🔍 Auto-detecting organization ID...")
            organization_id, org_source = get_organization_id(confirmed_project_id if check_ancestors else None)
            if organization_id and not interactive_org:
                print(f"✅ Using organization ID from {org_source}: {organization_id}")
            elif organization_id and interactive_org:
                print(f"ℹ️ Found organization ID from {org_source}: {organization_id}")
                print("🔄 Interactive mode enabled - prompting for confirmation/override...")
                # Prompt user to confirm or override the detected organization ID
                user_org_id = prompt_for_organization_id_with_default(organization_id)
                if user_org_id == "":
                    # User chose to remove organization ID
                    organization_id = None
                    org_source = None
                    print("✅ Organization ID removed by user")
                elif user_org_id:
                    organization_id = user_org_id
                    org_source = "user input (override)"
                    print(f"✅ Using organization ID from user input: {organization_id}")
                else:
                    print(f"✅ Keeping auto-detected organization ID: {organization_id}")
            else:
                print("ℹ️ No organization ID found (optional for project-level access)")
                # Prompt user to manually enter organization ID
                organization_id = prompt_for_organization_id()
                if organization_id:
                    org_source = "user input"
                    print(f"✅ Using organization ID from user input: {organization_id}")
        else:
            org_source = "command line argument"
            print(f"✅ Using organization ID from command line: {organization_id}")
            if interactive_org:
                print("🔄 Interactive mode enabled - prompting for confirmation/override...")
                user_org_id = prompt_for_organization_id_with_default(organization_id)
                if user_org_id == "":
                    # User chose to remove organization ID
                    organization_id = None
                    org_source = None
                    print("✅ Organization ID removed by user")
                elif user_org_id:
                    organization_id = user_org_id
                    org_source = "user input (override)"
                    print(f"✅ Using organization ID from user input: {organization_id}")
                else:
                    print(f"✅ Keeping command-line organization ID: {organization_id}")
        
        credentials_data = {}
        
        print("🔍 Detecting credential type...")
        
        # Method 1: Service Account JSON file
        if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            service_account_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            print(f"🔑 Found GOOGLE_APPLICATION_CREDENTIALS: {service_account_path}")
            if os.path.exists(service_account_path):
                print("✅ Service account file exists")
                with open(service_account_path, "r") as f:
                    service_account_json = json.load(f)
                
                credentials_data = {
                    "type": "service_account",
                    "credentials_file": service_account_path,
                    "project_id": confirmed_project_id,
                    "client_email": service_account_json.get("client_email"),
                    "source": "service_account"
                }
                print("✅ Using service account credentials")
            else:
                print(f"❌ Service account file not found: {service_account_path}")
        
        # Method 2: Application Default Credentials (simplified approach)
        if not credentials_data:
            print("🔍 Checking for application default credentials...")
            
            # Check common locations for application default credentials
            adc_paths = [
                os.path.expanduser("~/.config/gcloud/application_default_credentials.json"),
                os.path.expanduser("~/.config/gcloud/legacy_credentials"),
            ]
            
            adc_found = False
            for adc_path in adc_paths:
                if os.path.exists(adc_path):
                    print(f"✅ Found application default credentials at: {adc_path}")
                    adc_found = True
                    break
            
            if adc_found:
                # Don't call default() as it can hang - just trust that ADC exists
                credentials_data = {
                    "type": "application_default",
                    "project_id": confirmed_project_id,
                    "source": "application_default",
                    "adc_path": adc_path
                }
                print("✅ Using application default credentials")
            else:
                print("❌ No application default credentials found")
                print("💡 Run: gcloud auth application-default login")
                return False
        
        if not credentials_data:
            print("❌ Could not extract credentials")
            return False
        
        # Add metadata
        credentials_data["saved_at"] = confirmed_project_id
        credentials_data["project_name"] = project_name
        
        # Add organization ID if available
        if organization_id:
            credentials_data["organization_id"] = organization_id
            credentials_data["organization_source"] = org_source
        
        # Save to file with restrictive permissions
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(credentials_data, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)
        
        print(f"✅ Credentials saved to: {CREDENTIALS_FILE}")
        print(f"🔒 File permissions set to owner-only")
        print(f"📊 Credential Source: {credentials_data['source']}")
        if organization_id:
            print(f"🏢 Organization ID: {organization_id} (from {org_source})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Save GCP credentials for Autocost Controller")
    parser.add_argument("project_id", nargs="?", help="GCP project ID (optional - auto-detects from gcloud config)")
    parser.add_argument("--org-id", "--organization-id", dest="organization_id", 
                        help="GCP organization ID (optional - auto-detects from config files)")
    parser.add_argument("--interactive-org", action="store_true",
                        help="Force interactive prompt for organization ID even if detected")
    parser.add_argument("--skip-ancestors", action="store_true",
                        help="Skip automatic organization ID lookup via project ancestors (faster)")
    args = parser.parse_args()
    
    print("🔐 GCP Credential Saver")
    print("=" * 40)

    if save_current_credentials(args.project_id, args.organization_id, args.interactive_org, not args.skip_ancestors):
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