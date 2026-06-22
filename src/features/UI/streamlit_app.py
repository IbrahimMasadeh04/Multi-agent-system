import streamlit as st

st.set_page_config(page_title="Multi-Agent System", page_icon="🤖", layout="wide")

# Define pages
chat_page = st.Page("chat.py", title="Chat Interface", icon="💬", default=True)
mcp_page = st.Page("mcp_server_info.py", title="MCP Server Info", icon="🚀")

# Setup Navigation
pg = st.navigation(
    {
        "Main App": [chat_page],
        "Tools & Resources": [mcp_page],
    }
)

# Run the selected page
pg.run()
