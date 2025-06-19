#!/usr/bin/env python3
"""Check GCP project activity and last usage."""

import os
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from autocost_controller.core.config import Config
from autocost_controller.core.logger import AutocostLogger
from autocost_controller.providers.gcp.provider import GCPProvider

def check_project_activity(limit=30):
    """Check activity for GCP projects."""
    # Set up environment
    os.environ['GCP_PROJECT_ID'] = 'scheduling-engine-staging'
    os.environ['GCP_ORGANIZATION_ID'] = '675740110959'
    os.environ['AUTOCOST_PROVIDERS'] = 'gcp'
    os.environ['AUTOCOST_ENDPOINT'] = 'gcp'

    config = Config()
    logger = AutocostLogger('activity-check')
    provider = GCPProvider(config, logger)

    print('📊 **GCP Project Activity Analysis**')
    print('=' * 50)
    print(f'Organization: 675740110959')
    print(f'Checking: {limit} projects')
    print()

    projects = provider.list_available_projects()
    limited_projects = projects[:limit]
    
    active_projects = []
    inactive_projects = []
    error_projects = []
    
    print('🔍 Analyzing projects...')
    
    for i, project_id in enumerate(limited_projects, 1):
        try:
            print(f'  {i:2d}/{limit} - {project_id}', end=' ... ')
            
            # Get project info
            info = provider.get_project_info(project_id)
            
            if not info:
                error_projects.append((project_id, "Failed to get info"))
                print("❌ Error")
                continue
            
            # Check project state
            state = info.get('state', 'Unknown')
            name = info.get('name', 'Unknown')
            create_time = info.get('create_time')
            
            if state != 'ACTIVE':
                inactive_projects.append((project_id, name, f"State: {state}"))
                print(f"⏸️ {state}")
                continue
            
            # For active projects, we can't easily check last usage without more API calls
            # But we can categorize by creation date and naming patterns
            
            # Check if it's a system project (usually auto-generated)
            if project_id.startswith('sys-'):
                inactive_projects.append((project_id, name, "System project (likely auto-generated)"))
                print("🔧 System")
            elif any(keyword in project_id.lower() for keyword in ['test', 'demo', 'staging']):
                active_projects.append((project_id, name, "Development/Test project"))
                print("🧪 Dev/Test")
            elif any(keyword in project_id.lower() for keyword in ['cosmos', 'scheduling', 'nuvolar', 'couplesync']):
                active_projects.append((project_id, name, "Application project"))
                print("🚀 App")
            else:
                active_projects.append((project_id, name, "Active project"))
                print("✅ Active")
                
        except Exception as e:
            error_projects.append((project_id, str(e)[:50]))
            print(f"❌ Error: {str(e)[:30]}...")
    
    print()
    print('📋 **Results Summary:**')
    print('=' * 50)
    
    if active_projects:
        print(f'\n✅ **Likely Active Projects** ({len(active_projects)}):')
        for project_id, name, category in active_projects:
            print(f'  • {name} ({project_id})')
            print(f'    Category: {category}')
    
    if inactive_projects:
        print(f'\n⏸️ **Likely Inactive Projects** ({len(inactive_projects)}):')
        for project_id, name, status in inactive_projects[:10]:
            print(f'  • {name} ({project_id})')
            print(f'    Status: {status}')
        if len(inactive_projects) > 10:
            print(f'  ... and {len(inactive_projects) - 10} more')
    
    if error_projects:
        print(f'\n❌ **Errors** ({len(error_projects)}):')
        for project_id, error in error_projects[:5]:
            print(f'  • {project_id}: {error}')
    
    print(f'\n📊 **Summary:**')
    print(f'• Likely Active: {len(active_projects)} projects')
    print(f'• Likely Inactive: {len(inactive_projects)} projects')
    print(f'• Errors: {len(error_projects)} projects')
    print(f'• Total Analyzed: {len(limited_projects)} of {len(projects)}')
    
    print(f'\n💡 **Note:** This analysis is based on project names, states, and patterns.')
    print(f'For detailed usage metrics, billing data or monitoring APIs would be needed.')

if __name__ == "__main__":
    check_project_activity(30) 