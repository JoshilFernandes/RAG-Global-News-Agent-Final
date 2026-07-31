import streamlit as st
import requests

API_URL = "http://localhost:8000/chat"

st.title("GDELT RAG Agent Chat")

if "history" not in st.session_state:
    st.session_state["history"] = []

user_input = st.text_input("Ask a question about world news:", "")

if st.button("Send") and user_input.strip():
    st.session_state["history"].append(("user", user_input))
    with st.spinner("Thinking..."):
        try:
            resp = requests.post(API_URL, json={"query": user_input})
            if resp.status_code == 200:
                answer = resp.json().get("response", "[No response]")
            else:
                answer = f"[Error: {resp.status_code}]"
        except Exception as e:
            answer = f"[Error: {e}]"
        st.session_state["history"].append(("agent", answer))

# Display chat history
for role, msg in st.session_state["history"]:
    if role == "user":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Agent:** {msg}") 