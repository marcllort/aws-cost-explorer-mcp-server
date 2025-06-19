#!/usr/bin/env python3
"""
Autocost Controller - GCP Server Starter

Start the MCP server with saved GCP credentials.
This script is used internally by save_credentials_gcp.py.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    """Main entry point."""
    print("🚀 Starting MCP Server with GCP Credentials")
    print("=" * 40)
    
    if start_server():
        print("\n✅ Server started successfully!")
        print("You can now use GCP cost analysis tools.")
    else:
        print("\n❌ Failed to start server")
        print("💡 Make sure you have:")
        print("   1. Saved GCP credentials using save_credentials_gcp.py")
        print("   2. Have all required dependencies installed")
        sys.exit(1)

if __name__ == "__main__":
    main() 