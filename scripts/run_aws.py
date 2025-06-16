#!/usr/bin/env python3
"""
Wrapper script for Autocost Controller endpoint: aws
Executes pre-run commands before starting the MCP server.
"""

import os
import sys
import subprocess
import logging

def setup_logging():
    """Setup logging to stderr to avoid polluting MCP stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    return logging.getLogger(__name__)

def run_command(command: str, logger) -> bool:
    """Run a shell command and return success status."""
    try:
        logger.info(f"🔧 Running pre-command: {command}")
        
        # Run command in shell to support shell built-ins and aliases
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Command succeeded: {command}")
            if result.stdout.strip():
                logger.info(f"Output: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"❌ Command failed: {command}")
            logger.error(f"Error: {result.stderr.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ Command timed out: {command}")
        return False
    except Exception as e:
        logger.error(f"💥 Command error: {command} - {e}")
        return False

def main():
    """Main wrapper function."""
    logger = setup_logging()
    
    logger.info("🚀 Starting Autocost Controller wrapper for endpoint: aws")
    
    # Pre-run commands
    pre_commands = ['assume billing_read_only.root.okta', 'unset AWS_SESSION_TOKEN']
    
    if pre_commands:
        logger.info(f"🔧 Executing {len(pre_commands)} pre-run commands...")
        
        for i, command in enumerate(pre_commands, 1):
            logger.info(f"📝 Step {i}/{len(pre_commands)}: {command}")
            
            if not run_command(command, logger):
                logger.error(f"❌ Pre-command failed, aborting startup")
                sys.exit(1)
        
        logger.info("✅ All pre-commands completed successfully")
    
    # Start the main MCP server
    logger.info("🌐 Starting Autocost Controller MCP server...")
    
    try:
        # Execute the main script with the same arguments
        main_args = [
            "/Users/marc.llort/aws-cost-explorer-mcp-server/.venv/bin/python",
            "/Users/marc.llort/aws-cost-explorer-mcp-server/main.py",
            "--endpoint", "aws"
        ]
        
        # Add any additional arguments passed to this wrapper
        main_args.extend(sys.argv[1:])
        
        # Replace current process with the main script
        os.execvp(main_args[0], main_args)
        
    except Exception as e:
        logger.error(f"💥 Failed to start main server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
