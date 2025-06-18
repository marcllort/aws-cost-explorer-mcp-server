#!/usr/bin/env python3
"""
Convenience script to capture current AWS credentials and start the MCP server.
Run this in the terminal where you've already assumed your AWS role.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Capture credentials and start server."""
    
    # First, capture current session credentials
    print("🔐 Capturing current AWS session...")
    result = subprocess.run([sys.executable, "save_current_session.py"], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Credentials captured successfully!")
        print(result.stdout)
        
        print("\n🚀 Starting MCP server with captured credentials...")
        # Start the server
        subprocess.run([sys.executable, "server_manual.py"])
    else:
        print("❌ Failed to capture credentials:")
        print(result.stderr)
        print("\n💡 Make sure you have valid AWS credentials in this terminal session.")
        print("   Try running: aws sts get-caller-identity")

if __name__ == "__main__":
    main() 