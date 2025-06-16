"""
Autocost Controller - Multi-Cloud Cost Analysis and Optimization

A comprehensive Model Context Protocol (MCP) server for multi-cloud cost analysis
with performance insights and optimization recommendations across AWS, GCP, Azure, and more.
"""

__version__ = "1.0.0"
__author__ = "Autocost Controller Team"

from .server import AutocostServer

__all__ = ["AutocostServer"] 