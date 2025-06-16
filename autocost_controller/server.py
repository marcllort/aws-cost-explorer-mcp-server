"""
Autocost Controller - Multi-Cloud Cost Analysis and Optimization Server

A comprehensive MCP server for multi-cloud cost analysis with performance insights
and optimization recommendations across AWS, GCP, Azure, and more.

Enhanced with provider-specific endpoint support and TCP transport.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP
from mcp.server import Server
from mcp.types import (
    Resource, Tool, Prompt,
    GetPromptResult, ReadResourceResult, CallToolResult,
    ListToolsResult, ListPromptsResult, ListResourcesResult
)

from .core.config import Config
from .core.provider_manager import ProviderManager
from .tools import register_all_tools


class AutocostServer:
    """Enhanced Autocost Controller MCP Server with TCP support."""
    
    def __init__(self, endpoint: str = "unified", logger: Optional[logging.Logger] = None):
        """Initialize the Autocost Controller server."""
        self.endpoint = endpoint
        self.logger = logger or logging.getLogger(__name__)
        self.config = Config()
        self.provider_manager = ProviderManager(self.config, self.logger)
        self.mcp_server = Server("autocost-controller")
        self._setup_handlers()
    
    async def _setup_handlers(self):
        """Setup MCP server handlers."""
        # We'll register tools and handlers here
        pass
    
    async def run(self):
        """Run the server with stdio transport (default MCP mode)."""
        from mcp.server.stdio import stdio_server
        
        self.logger.info("🚀 Starting Autocost Controller with stdio transport")
        self.logger.info(f"🌐 Endpoint: {self.endpoint}")
        
        # Providers are already initialized in constructor
        
        # Register tools with the provider manager
        await self._register_tools()
        
        # Run with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            await self.mcp_server.run(
                read_stream, write_stream,
                self.mcp_server.create_initialization_options()
            )
    
    async def run_tcp(self, host: str = "localhost", port: int = 8000):
        """Run the server with TCP transport."""
        import socket
        from mcp.server.sse import SseServerTransport
        from contextlib import asynccontextmanager
        
        self.logger.info(f"🌐 Starting Autocost Controller TCP server on {host}:{port}")
        self.logger.info(f"🌐 Endpoint: {self.endpoint}")
        
        # Providers are already initialized in constructor
        
        # Register tools
        await self._register_tools()
        
        # Create FastMCP for easier TCP handling
        mcp = FastMCP(f"autocost-controller-{self.endpoint}")
        
        # Register tools with FastMCP
        await self._register_fastmcp_tools(mcp)
        
        # Run TCP server
        try:
            # Use FastMCP's built-in TCP support if available, otherwise fallback
            if hasattr(mcp, 'run_tcp'):
                await mcp.run_tcp(host=host, port=port)
            else:
                # Manual TCP server implementation
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((host, port))
                server_socket.listen(1)
                server_socket.setblocking(False)
                
                self.logger.info(f"✅ TCP server listening on {host}:{port}")
                self.logger.info("💡 Configure Claude Desktop to connect using TCP transport")
                
                loop = asyncio.get_event_loop()
                
                while True:
                    try:
                        client_socket, addr = await loop.sock_accept(server_socket)
                        self.logger.info(f"🔌 Client connected from {addr}")
                        
                        # Handle client in background
                        asyncio.create_task(self._handle_tcp_client(client_socket, mcp))
                        
                    except Exception as e:
                        self.logger.error(f"❌ Error accepting connection: {e}")
                        
        except Exception as e:
            self.logger.error(f"❌ TCP server error: {e}")
            raise
    
    async def _handle_tcp_client(self, client_socket, mcp):
        """Handle a TCP client connection."""
        try:
            # This is a simplified handler - you'd need to implement
            # the full MCP protocol over TCP here
            reader, writer = await asyncio.open_connection(sock=client_socket)
            
            # For now, just log the connection
            self.logger.info("🔌 TCP client handler started")
            
            # Keep connection alive
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                    
                # Echo back for now (implement MCP protocol here)
                writer.write(data)
                await writer.drain()
                
        except Exception as e:
            self.logger.error(f"❌ Error handling TCP client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    async def _register_tools(self):
        """Register tools with the MCP server."""
        # Register list handlers
        @self.mcp_server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List available tools."""
            tools = []
            
            # Get tools from provider manager
            ready_providers = self.provider_manager.get_ready_providers()
            
            for provider_name in ready_providers:
                provider = self.provider_manager.get_provider(provider_name)
                if provider:
                    provider_tools = await provider.get_tools()
                    tools.extend(provider_tools)
            
            return ListToolsResult(tools=tools)
        
        @self.mcp_server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls."""
            # Route to appropriate provider
            for provider_name in self.provider_manager.get_ready_providers():
                provider = self.provider_manager.get_provider(provider_name)
                if provider and await provider.has_tool(name):
                    return await provider.call_tool(name, arguments)
            
            return CallToolResult(
                content=[{
                    "type": "text",
                    "text": f"Tool '{name}' not found in any ready provider."
                }],
                isError=True
            )
        
        @self.mcp_server.list_prompts()
        async def handle_list_prompts() -> ListPromptsResult:
            """List available prompts."""
            prompts = [
                Prompt(
                    name="system_prompt",
                    description="System prompt for multi-cloud cost analysis"
                )
            ]
            return ListPromptsResult(prompts=prompts)
        
        @self.mcp_server.get_prompt()
        async def handle_get_prompt(name: str, arguments: Dict[str, Any]) -> GetPromptResult:
            """Get prompt content."""
            if name == "system_prompt":
                content = await self._generate_system_prompt()
                return GetPromptResult(
                    description="System prompt for multi-cloud cost analysis",
                    messages=[{
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": content
                        }
                    }]
                )
            
            raise ValueError(f"Unknown prompt: {name}")
    
    async def _register_fastmcp_tools(self, mcp: FastMCP):
        """Register tools with FastMCP for TCP mode."""
        # Register system prompt
        @mcp.prompt()
        def system_prompt_for_agent(provider: str = "aws") -> str:
            """Generate a system prompt for a multi-cloud cost analysis agent."""
            # Return the same system prompt as in the original
            return asyncio.run(self._generate_system_prompt())
        
        # Register tools from providers
        register_all_tools(mcp, self.provider_manager, self.config, self.logger)
    
    async def _generate_system_prompt(self) -> str:
        """Generate system prompt based on current provider status."""
        ready_providers = self.provider_manager.get_ready_providers()
        
        if not ready_providers:
            return f"""
🚨 **AUTOCOST CONTROLLER - CONFIGURATION REQUIRED** (Endpoint: {self.endpoint})

No cloud providers are currently configured and ready. Please check your configuration:

1. **AWS**: Ensure AWS credentials are configured and Cost Explorer access is available
2. **GCP**: Set up GCP credentials and enable Cloud Billing API (coming soon)
3. **Azure**: Configure Azure credentials and Cost Management access (coming soon)
4. **DataDog**: Provide API and App keys for usage analysis (coming soon)

Use environment variables or .env file to configure providers.
"""
        
        provider_list = ", ".join(ready_providers)
        
        # Provider-specific context
        provider_context = ""
        if len(ready_providers) == 1:
            provider_context = f"\n🎯 **FOCUSED ANALYSIS**: This endpoint is optimized for {ready_providers[0].upper()} cost analysis."
        
        return f"""
🚀 **AUTOCOST CONTROLLER - MULTI-CLOUD COST OPTIMIZATION AGENT**
📡 **Endpoint**: {self.endpoint}

You are an expert multi-cloud cost analyst AI agent with access to {provider_list}.
Your purpose is to help users understand and optimize their cloud spending across multiple providers.
{provider_context}

## 🎯 **CORE CAPABILITIES**
1. **Universal Cost Discovery**: Analyze costs across any supported cloud provider
2. **Cross-Provider Comparison**: Compare costs and efficiency between providers
3. **Service-Specific Analysis**: Deep dive into compute, storage, database, and other services
4. **Performance-Cost Correlation**: Analyze performance metrics for optimization
5. **Intelligent Recommendations**: Provide actionable cost reduction strategies

## 📊 **ANALYSIS WORKFLOW**
1. **Provider Selection**: Choose the appropriate cloud provider for analysis
2. **Discovery Phase**: Use dimension/service discovery tools to understand cost structure
3. **Deep Analysis**: Drill down into specific services, tags, or dimensions
4. **Performance Review**: Analyze metrics for optimization opportunities
5. **Recommendations**: Provide specific, actionable optimization strategies

## 💡 **KEY FOCUS AREAS**
- Identify underutilized resources and right-sizing opportunities
- ARM/Graviton migration potential and savings calculations
- Spot instance and Reserved Instance opportunities
- Cross-provider cost comparison and migration analysis
- Tag-based cost allocation and governance
- Performance-cost optimization strategies

## 🎯 **OPTIMIZATION PRIORITIES**
1. **Quick Wins**: Low effort, high impact optimizations
2. **Strategic Moves**: Long-term cost reduction strategies
3. **Performance Gains**: Cost-effective performance improvements
4. **Governance**: Cost visibility and control mechanisms

Always provide specific, actionable recommendations with estimated savings, implementation guidance, and risk assessment.
Ready providers: **{provider_list.upper()}**
""" 