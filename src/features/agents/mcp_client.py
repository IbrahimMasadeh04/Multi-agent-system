import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client  

from src.helper.config import get_settings  # type: ignore 

class MCPClient:
    def __init__(self, server_url=None): 
        settings = get_settings()
        self.server_url = server_url or settings.CLIENT_URI
        self.session = None
        self.transport = None

    async def connect(self):
        """Initialize a connection to the MCP Server"""
        # Note: streamable_http_client yields (read_stream, write_stream)
        # This connect method would need to maintain the context managers for the streams.
        # It's better to use the context managers inside call_tool directly.
        pass

    async def call_tool(self, tool_name, arguments):
        """communication point to call a tool on the MCP Server"""
        async with streamable_http_client(self.server_url) as (read_stream, write_stream, session_info):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return result.content[0].text

    async def get_prompt(self, prompt_name, arguments=None):
        """communication point to get a prompt from the MCP Server"""
        if arguments is None:
            arguments = {}

        async with streamable_http_client(self.server_url) as (read_stream, write_stream, session_info):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.get_prompt(prompt_name, arguments=arguments)
                return result.messages[0].content.text

    async def list_resources(self):
        """communication point to list all resources from the MCP Server"""
        async with streamable_http_client(self.server_url) as (read_stream, write_stream, session_info):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_resources()
                return result.resources

    async def list_tools(self):
        """communication point to list all tools from the MCP Server"""
        async with streamable_http_client(self.server_url) as (read_stream, write_stream, session_info):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                return result.tools

    async def list_prompts(self):
        """communication point to list all prompts from the MCP Server"""
        async with streamable_http_client(self.server_url) as (read_stream, write_stream, session_info):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_prompts()
                return result.prompts

if __name__ == "__main__":
    client = MCPClient()
    