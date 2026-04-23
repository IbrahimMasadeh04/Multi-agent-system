import streamlit as st
import requests
import os

st.set_page_config(page_title="BMO Multi-Agent System", page_icon="🤖", layout="wide")

API_URL = "http://localhost:8000/api"

st.title("🤖 Multi-Agent Orchestrator (RAG + Web)")
st.markdown("---")

with st.sidebar:
    st.header("📁 Document Management")
    uploaded_file = st.file_uploader("Upload a PDF to ChromaDB", type="pdf")
    
    if st.button("Process & Index"):
        if uploaded_file:
            with st.spinner("Processing file..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(f"{API_URL}/upload", files=files)
                
                if response.status_code == 200:
                    st.success("✅ File indexed in ChromaDB!")
                else:
                    st.error(f"❌ Error: {response.json().get('detail')}")
        else:
            st.warning("Please select a file first.")

    st.markdown("---")
    st.info("System Components:\n- **Orchestrator**: Routing Logic\n- **Internal Worker**: ChromaDB RAG\n- **External Worker**: Tavily Search")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me something (about your files or the world)..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Orchestrating agents..."):
            try:
                response = requests.post(
                    f"{API_URL}/chat", 
                    json={"message": prompt}
                )
                
                if response.status_code == 200:
                    answer = response.json().get("response")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    error_msg = f"Error: {response.status_code}"
                    st.error(error_msg)
            except Exception as e:
                st.error(f"Connection failed: {e}")
