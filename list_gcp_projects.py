#!/usr/bin/env python3
"""List GCP projects under the organization."""

import os
import sys
sys.path.insert(0, '.')

from autocost_controller.core.config import Config
from autocost_controller.core.logger import AutocostLogger
from autocost_controller.providers.gcp.provider import GCPProvider

def main():
    # Set up environment like the MCP server
    os.environ['GCP_PROJECT_ID'] = 'scheduling-engine-staging'
    os.environ['GCP_ORGANIZATION_ID'] = '675740110959'
    os.environ['AUTOCOST_PROVIDERS'] = 'gcp'
    os.environ['AUTOCOST_ENDPOINT'] = 'gcp'

    config = Config()
    logger = AutocostLogger('gcp-list')
    provider = GCPProvider(config, logger)

    print('📋 **Available GCP Projects:**')
    print('=' * 50)

    projects = provider.list_available_projects()
    print(f'🔍 Found {len(projects)} projects under organization 675740110959:')
    print()

    # Show first 20 projects with details
    for i, project_id in enumerate(projects[:20]):
        try:
            info = provider.get_project_info(project_id)
            if info:
                print(f'{i+1:2d}. {info["name"]} ({project_id})')
                print(f'    State: {info["state"]}')
                if info.get('labels'):
                    labels = ', '.join(f'{k}={v}' for k, v in list(info['labels'].items())[:3])
                    print(f'    Labels: {labels}')
            else:
                print(f'{i+1:2d}. {project_id} (Error getting details)')
        except Exception as e:
            print(f'{i+1:2d}. {project_id} (Error: {str(e)[:50]}...)')
        print()

    if len(projects) > 20:
        print(f'... and {len(projects) - 20} more projects')

    print(f'📊 **Total**: {len(projects)} projects accessible')

if __name__ == "__main__":
    main() 