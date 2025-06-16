#!/usr/bin/env python3
"""
Wrapper script for Autocost Controller endpoint: aws
Handles AWS authentication in GUI application environment (Claude Desktop).
"""

import os
import sys
import subprocess
import logging
import time
import json

def setup_logging():
    """Setup logging to stderr to avoid polluting MCP stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    return logging.getLogger(__name__)

def setup_macos_environment(logger):
    """Set up environment variables for macOS GUI applications."""
    try:
        # On macOS, GUI apps don't inherit shell environment
        home_dir = os.path.expanduser("~")
        
        # Common paths that might be missing in GUI environment
        additional_paths = [
            "/opt/homebrew/bin",
            "/usr/local/bin", 
            "/usr/bin",
            "/bin"
        ]
        
        current_path = os.environ.get("PATH", "")
        for path in additional_paths:
            if path not in current_path:
                current_path = f"{path}:{current_path}"
        
        os.environ["PATH"] = current_path
        logger.info(f"🔧 Updated PATH for GUI environment")
        
        # Set up common environment variables
        os.environ["HOME"] = home_dir
        if not os.environ.get("USER"):
            os.environ["USER"] = os.path.basename(home_dir)
        
        # Set TERM for terminal apps
        os.environ["TERM"] = "xterm-256color"
        
        return True
    except Exception as e:
        logger.error(f"Failed to setup macOS environment: {e}")
        return False

def verify_aws_credentials(logger) -> tuple[bool, str]:
    """Verify that AWS credentials are available. Returns (success, error_type)."""
    try:
        logger.info("🧪 Verifying AWS credentials...")
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info("✅ AWS credentials verified successfully")
            try:
                identity = json.loads(result.stdout)
                account = identity.get('Account', 'Unknown')
                user = identity.get('Arn', 'Unknown').split('/')[-1]
                logger.info(f"Account: {account}, User/Role: {user}")
            except:
                logger.info("AWS identity confirmed")
            return True, ""
        else:
            error_msg = result.stderr.strip()
            logger.error(f"❌ AWS credentials not available: {error_msg}")
            
            # Determine error type
            if "ExpiredToken" in error_msg:
                logger.error("🔑 Token expired - need fresh credentials")
                return False, "expired"
            elif "NoCredentialsError" in error_msg or "Unable to locate credentials" in error_msg:
                logger.error("🔑 No credentials found")
                return False, "missing"
            else:
                logger.error("🔑 Unknown credential error")
                return False, "unknown"
            
    except FileNotFoundError:
        logger.error("❌ AWS CLI not found in PATH")
        return False, "no_cli"
    except subprocess.TimeoutExpired:
        logger.error("⏰ AWS credential check timed out")
        return False, "timeout"
    except Exception as e:
        logger.error(f"💥 AWS credential check error: {e}")
        return False, "exception"

def try_quick_assume(logger) -> bool:
    """Try a quick assume command, but don't wait long if it fails."""
    try:
        logger.info("🔄 Attempting quick assume command...")
        
        # Quick attempt with short timeout
        result = subprocess.run(
            "source ~/.zshenv 2>/dev/null; source ~/.zshrc 2>/dev/null; assume billing_read_only.root.okta",
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,  # Short timeout
            executable="/bin/zsh"
        )
        
        if result.returncode == 0:
            logger.info("✅ Quick assume completed successfully")
            # Wait a moment and verify
            time.sleep(3)
            success, _ = verify_aws_credentials(logger)
            return success
        else:
            logger.warning(f"⚠️ Quick assume failed (exit code {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        logger.warning("⏰ Quick assume timed out - likely needs interactive input")
        return False
    except Exception as e:
        logger.warning(f"⚠️ Quick assume error: {e}")
        return False

def show_helpful_instructions(logger, error_type: str):
    """Show helpful instructions based on the error type."""
    logger.error("💡 SOLUTION: Run this command in your terminal, then restart Claude Desktop:")
    logger.error("")
    logger.error("    assume billing_read_only.root.okta")
    logger.error("")
    
    if error_type == "expired":
        logger.error("🔑 Your AWS credentials have expired and need to be refreshed.")
        logger.error("   The 'assume' command will get fresh credentials from your SSO.")
    elif error_type == "missing":
        logger.error("🔑 No AWS credentials found.")
        logger.error("   The 'assume' command will set up credentials for your session.")
    else:
        logger.error("🔑 There's an issue with your AWS credentials.")
        logger.error("   The 'assume' command should resolve it.")
    
    logger.error("")
    logger.error("💻 After running the command:")
    logger.error("   1. Complete any authentication prompts")
    logger.error("   2. Restart Claude Desktop")
    logger.error("   3. The MCP server should start successfully")

def main():
    """Main wrapper function."""
    logger = setup_logging()
    
    logger.info("🚀 Starting Autocost Controller wrapper for endpoint: aws")
    logger.info("🖥️ Setting up macOS GUI application environment...")
    
    # Set up macOS environment for GUI apps
    setup_macos_environment(logger)
    
    # Check if credentials are already available
    credentials_ok, error_type = verify_aws_credentials(logger)
    
    if credentials_ok:
        logger.info("✅ AWS credentials already available, starting MCP server...")
    else:
        # Try a quick assume only for expired tokens
        if error_type == "expired":
            logger.info("🔧 Credentials expired, trying quick automatic refresh...")
            if try_quick_assume(logger):
                logger.info("✅ Quick assume succeeded, starting MCP server...")
            else:
                logger.error("❌ Quick assume failed")
                show_helpful_instructions(logger, error_type)
                sys.exit(1)
        else:
            logger.error("❌ AWS credentials not available")
            show_helpful_instructions(logger, error_type)
            sys.exit(1)
    
    logger.info("✅ AWS authentication verified, starting MCP server...")
    
    try:
        # Execute the main script
        main_args = [
            "/Users/marc.llort/aws-cost-explorer-mcp-server/.venv/bin/python3",
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