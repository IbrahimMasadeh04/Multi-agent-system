import sys
import os
import streamlit as st
import asyncio

# Ensure the project root is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.features.agents.mcp_client import MCPClient  # type: ignore

# ==============================================================================
# MCP SERVER SIDE REQUIREMENTS (What you need to make on the server side):
# ------------------------------------------------------------------------------
# In order for this page to fetch and display data successfully, the MCP Server
# must implement the Model Context Protocol appropriately. Specifically, you need to:
# 
# 1. RESOURCES: Register resources on the server side (e.g. `mcp.resources(...)`
#    or overriding resource logic depending on your server framework) so that
#    it successfully responds to a `list_resources` request with a list of items 
#    providing their `uri`, `name`, `mimeType`, and `description`.
#
# 2. TOOLS: Register tools via the `@mcp.tool()` decorator (or equivalent).
#    The server needs to expose the function name, its description, and its
#    inputSchema so `list_tools` can return them.
#
# 3. PROMPTS: Register prompts via the `@mcp.prompt()` decorator (or equivalent).
#    The server must return their `name`, `description`, and `arguments`
#    requirements when `list_prompts` is called.
# ==============================================================================

st.title("MCP Server Explorer")
st.markdown("Use the buttons below to inspect the connected MCP server's exposed endpoints.")

client = MCPClient()

col1, col2, col3 = st.columns(3)

def render_result(title, items):
    st.write(f"### {title}")
    if not items:
        st.info("No items returned.")
        return
    # Safely dump Pydantic objects or standard dicts
    serialized = [item.model_dump() if hasattr(item, "model_dump") else str(item) for item in items]
    st.json(serialized)

if col1.button("Get Resources"):
    with st.spinner("Fetching resources..."):
        try:
            resources = asyncio.run(client.list_resources())
            render_result("Resources", resources)
        except Exception as e:
            st.error(f"Error fetching resources: {e}")

if col2.button("Get Tools"):
    with st.spinner("Fetching tools..."):
        try:
            tools = asyncio.run(client.list_tools())
            render_result("Tools", tools)
        except Exception as e:
            st.error(f"Error fetching tools: {e}")

if col3.button("Get Prompts"):
    with st.spinner("Fetching prompts..."):
        try:
            prompts = asyncio.run(client.list_prompts())
            render_result("Prompts", prompts)
        except Exception as e:
            st.error(f"Error fetching prompts: {e}")
