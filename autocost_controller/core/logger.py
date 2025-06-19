"""Enhanced logging system for Autocost Controller."""

import logging
import sys
import os
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from rich.panel import Panel
from rich.table import Table


def is_mcp_mode() -> bool:
    """Detect if we're running in MCP mode where stdout is used for JSON communication."""
    # Explicit MCP mode flag
    if os.environ.get("AUTOCOST_MCP_MODE") == "true":
        return True
    
    # Check if we're running with stdio transport (default for MCP)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    
    # If stdout is not a TTY and we're using stdio transport, likely MCP mode
    if transport == "stdio" and not sys.stdout.isatty():
        return True
    
    # Check for MCP-specific environment variables
    if "AUTOCOST_ENDPOINT" in os.environ and "AUTOCOST_PROVIDERS" in os.environ:
        return True
    
    return False


class AutocostLogger:
    """Enhanced logger with emojis and rich formatting."""
    
    def __init__(self, name: str, level: str = "INFO"):
        # In MCP mode, use stderr to avoid polluting stdout JSON communication
        console_file = sys.stderr if is_mcp_mode() else sys.stdout
        self.console = Console(file=console_file)
        self.is_mcp_mode = is_mcp_mode()
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Add rich handler with stderr in MCP mode
        rich_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True
        )
        rich_handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(rich_handler)
    
    def startup_banner(self, config_dict: dict):
        """Display startup banner with configuration."""
        # Skip rich banners in MCP mode to avoid JSON pollution
        if self.is_mcp_mode:
            self.logger.info("Autocost Controller starting...")
            return
            
        banner = Panel.fit(
            "[bold blue]🚀 Autocost Controller[/bold blue]\n"
            "[dim]Multi-Cloud Cost Analysis & Optimization[/dim]",
            border_style="blue"
        )
        self.console.print(banner)
        
        # Configuration table
        table = Table(title="🔧 Configuration", show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in config_dict.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    table.add_row(f"{key}.{sub_key}", str(sub_value))
            else:
                table.add_row(key, str(value))
        
        self.console.print(table)
    
    def provider_status(self, provider: str, status: str, details: Optional[str] = None):
        """Log provider status with appropriate emoji."""
        emoji_map = {
            'ready': '✅',
            'error': '❌',
            'warning': '⚠️',
            'loading': '🔄',
            'disabled': '⏸️'
        }
        
        emoji = emoji_map.get(status, '📋')
        message = f"{emoji} {provider.upper()}: {status}"
        if details:
            message += f" - {details}"
        
        if status == 'error':
            self.logger.error(message)
        elif status == 'warning':
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def request_received(self, tool_name: str, provider: str, params: dict):
        """Log incoming MCP requests."""
        self.logger.info(
            f"📥 [bold cyan]{tool_name}[/bold cyan] request for [yellow]{provider}[/yellow] "
            f"with {len(params)} parameters"
        )
    
    def request_completed(self, tool_name: str, provider: str, duration: float, success: bool = True):
        """Log completed requests."""
        emoji = "✅" if success else "❌"
        status = "completed" if success else "failed"
        self.logger.info(
            f"{emoji} [bold cyan]{tool_name}[/bold cyan] {status} for [yellow]{provider}[/yellow] "
            f"in {duration:.2f}s"
        )
    
    def cost_analysis_summary(self, provider: str, total_cost: float, period_days: int, 
                            recommendations_count: int):
        """Log cost analysis summary."""
        daily_avg = total_cost / period_days
        self.logger.info(
            f"💰 [bold green]{provider.upper()}[/bold green] Analysis: "
            f"${total_cost:.2f} total, ${daily_avg:.2f}/day avg, "
            f"{recommendations_count} recommendations"
        )
    
    def optimization_found(self, provider: str, category: str, potential_savings: float):
        """Log optimization opportunities."""
        annual_savings = potential_savings * 365
        self.logger.info(
            f"💡 [bold yellow]{provider.upper()}[/bold yellow] {category}: "
            f"${potential_savings:.2f}/day (${annual_savings:.2f}/year) potential savings"
        )
    
    def error(self, message: str, provider: Optional[str] = None):
        """Log errors with context."""
        prefix = f"[red]{provider.upper()}[/red] " if provider else ""
        self.logger.error(f"❌ {prefix}{message}")
    
    def warning(self, message: str, provider: Optional[str] = None):
        """Log warnings with context."""
        prefix = f"[yellow]{provider.upper()}[/yellow] " if provider else ""
        self.logger.warning(f"⚠️ {prefix}{message}")
    
    def info(self, message: str, provider: Optional[str] = None):
        """Log info messages with context."""
        prefix = f"[blue]{provider.upper()}[/blue] " if provider else ""
        self.logger.info(f"ℹ️ {prefix}{message}")
    
    def debug(self, message: str, provider: Optional[str] = None):
        """Log debug messages with context."""
        prefix = f"[dim]{provider.upper()}[/dim] " if provider else ""
        self.logger.debug(f"🔍 {prefix}{message}")


def setup_logger(name: str = "autocost_controller", level: str = "INFO") -> AutocostLogger:
    """Setup and return the enhanced logger."""
    return AutocostLogger(name, level)