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

if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = False
    
if "pending_sql" not in st.session_state:
    st.session_state.pending_sql = ""

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.pending_approval:
    with st.chat_message("assistant"):
        st.warning("⚠️ **Human Confirmation Required**!")
        st.code(st.session_state.pending_sql, language="sql")
        st.markdown("I have a database write operation ready. Please approve or reject below.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve"):
                res = requests.post(f"{API_URL}/approve", json={"approved": True})
                if res.status_code == 200:
                    ans = res.json().get("response")
                    st.session_state.messages.append({"role": "assistant", "content": ans})
                st.session_state.pending_approval = False
                st.rerun()
        with col2:
            if st.button("❌ Reject"):
                res = requests.post(f"{API_URL}/approve", json={"approved": False})
                if res.status_code == 200:
                    ans = res.json().get("response")
                    st.session_state.messages.append({"role": "assistant", "content": ans})
                st.session_state.pending_approval = False
                st.rerun()
    st.stop()

if prompt := st.chat_input("Ask me something (about your files or the world)..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Orchestrating bots..."):
            try:
                response = requests.post(
                    f"{API_URL}/chat", 
                    json={"message": prompt}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "interrupted":
                        st.session_state.pending_approval = True
                        st.session_state.pending_sql = data.get("pending_sql", "")
                        st.rerun()
                    else:
                        answer = data.get("response")
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    error_msg = f"Error: {response.status_code}"
                    st.error(error_msg)
            except Exception as e:
                st.error(f"Connection failed: {e}")
