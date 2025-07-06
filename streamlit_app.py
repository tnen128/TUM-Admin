import streamlit as st
import requests
from dotenv import load_dotenv
import os
import base64
from datetime import datetime
import json
from typing import Dict, Any
import time
import io

from document_models import DocumentType, ToneType
from llm_service import LLMService
from export_service import DocumentExporter

# Load environment variables for local dev
load_dotenv()

# Use Streamlit secrets for deployment, fallback to env vars
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))
BACKEND_URL = st.secrets.get("BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8000"))

# Configure the page
st.set_page_config(
    page_title="TUM Admin Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# # Custom CSS for TUM-branded chat interface
# st.markdown("""
# <style>
#     /* TUM Colors */
#     :root {
#         --tum-blue: #0064AA;
#         --tum-light-blue: #0077B6;
#         --tum-dark-blue: #003359;
#         --tum-gray: #E6E6E6;
#         --tum-dark-gray: #333333;
#     }

#     /* Main container styling */
#     .main {
#         padding: 0;
#         background-color: #f8f9fa;
#         height: 100vh;
#         display: flex;
#         flex-direction: column;
#     }

#     .stApp {
#         max-width: 100%;
#         padding: 0;
#         height: 100vh;
#     }

#     /* Chat container */
#     .chat-container {
#         flex: 1;
#         overflow-y: auto;
#         padding: 1rem;
#         margin-bottom: 80px; /* Space for input container */
#         display: flex;
#         flex-direction: column;
#     }

#     /* Chat messages */
#     .chat-message {
#         padding: 1.5rem;
#         border-radius: 1rem;
#         margin-bottom: 1rem;
#         max-width: 80%;
#         display: flex;
#         flex-direction: column;
#         animation: fadeInUp 0.5s cubic-bezier(0.23, 1, 0.32, 1);
#         transition: box-shadow 0.2s, transform 0.2s;
#     }

#     @keyframes fadeInUp {
#         from { opacity: 0; transform: translateY(30px) scale(0.98); }
#         to { opacity: 1; transform: translateY(0) scale(1); }
#     }

#     .chat-message.user {
#         background-color: var(--tum-blue);
#         color: white;
#         margin-left: auto;
#         border-bottom-right-radius: 0.25rem;
#     }

#     .chat-message.assistant {
#         background-color: var(--tum-gray);
#         color: var(--tum-dark-gray);
#         margin-right: auto;
#         border-bottom-left-radius: 0.25rem;
#     }

#     .chat-message .content {
#         display: flex;
#         align-items: flex-start;
#         gap: 0.75rem;
#     }

#     .chat-message .avatar {
#         width: 36px;
#         height: 36px;
#         border-radius: 50%;
#         display: flex;
#         align-items: center;
#         justify-content: center;
#         font-size: 1.2rem;
#         background-color: white;
#         box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
#         flex-shrink: 0;
#     }

#     .chat-message .message {
#         flex: 1;
#         white-space: pre-wrap;
#         line-height: 1.6;
#         font-size: 1rem;
#     }

#     /* Input container */
#     .input-container {
#         position: fixed;
#         bottom: 0;
#         left: 0;
#         right: 0;
#         padding: 1rem;
#         background-color: white;
#         border-top: 1px solid var(--tum-gray);
#         display: flex;
#         gap: 1rem;
#         align-items: center;
#         box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
#         z-index: 100;
#     }

#     .input-container textarea {
#         flex: 1;
#         background-color: white;
#         color: var(--tum-dark-gray);
#         border: 2px solid var(--tum-gray);
#         border-radius: 1rem;
#         padding: 0.75rem 1rem;
#         resize: none;
#         height: 50px;
#         transition: all 0.3s ease;
#         font-size: 1rem;
#         line-height: 1.5;
#     }

#     .input-container textarea:focus {
#         border-color: var(--tum-blue);
#         box-shadow: 0 0 0 2px rgba(0, 100, 170, 0.1);
#         outline: none;
#     }

#     .input-container button {
#         background-color: var(--tum-blue);
#         color: white;
#         border: none;
#         padding: 0.75rem 1.5rem;
#         border-radius: 1rem;
#         cursor: pointer;
#         display: flex;
#         align-items: center;
#         gap: 0.5rem;
#         transition: all 0.3s ease;
#         font-weight: 600;
#         font-size: 1rem;
#         height: 50px;
#     }

#     .input-container button:hover {
#         background-color: var(--tum-light-blue);
#         transform: translateY(-1px);
#     }

#     .input-container button:disabled {
#         background-color: var(--tum-gray);
#         cursor: not-allowed;
#         transform: none;
#     }

#     /* Typing indicator */
#     .typing-indicator {
#         display: flex;
#         align-items: center;
#         gap: 0.5rem;
#         padding: 0.5rem 1rem;
#         background-color: var(--tum-gray);
#         border-radius: 1rem;
#         margin-bottom: 1rem;
#         animation: fadeIn 0.3s ease-in-out;
#         align-self: flex-start;
#     }

#     .typing-dot {
#         width: 8px;
#         height: 8px;
#         background-color: var(--tum-blue);
#         border-radius: 50%;
#         animation: typingAnimation 1.4s infinite ease-in-out;
#     }

#     .typing-dot:nth-child(1) { animation-delay: 0s; }
#     .typing-dot:nth-child(2) { animation-delay: 0.2s; }
#     .typing-dot:nth-child(3) { animation-delay: 0.4s; }

#     @keyframes typingAnimation {
#         0%, 60%, 100% { transform: translateY(0); }
#         30% { transform: translateY(-4px); }
#     }

#     /* Sidebar styling */
# </style>
# """)

# --- (The rest of your Streamlit UI and logic goes here, adapted from app/web/main.py) ---
# For brevity, only the structure and key logic are shown. You should copy over your UI, chat, and document logic here.

st.title("TUM Admin Assistant")

st.sidebar.header("Settings")
doc_type = st.sidebar.selectbox("Document Type", [e.value for e in DocumentType])
tone = st.sidebar.selectbox("Tone", [e.value for e in ToneType])
sender_name = st.sidebar.text_input("Sender Name", "Prof. Example")
sender_profession = st.sidebar.text_input("Sender Profession", "Professor")
language = st.sidebar.selectbox("Language", ["English", "German"])

prompt = st.text_area("Enter your prompt or announcement details:", value="")

if st.button("Generate Document"):
    if not GOOGLE_API_KEY:
        st.error("Google API key not set. Please configure it in Streamlit secrets or your .env file.")
    else:
        llm = LLMService(api_key=GOOGLE_API_KEY)
        doc_type_enum = DocumentType(doc_type)
        tone_enum = ToneType(tone)
        result = llm.generate_document(
            doc_type=doc_type_enum,
            tone=tone_enum,
            prompt=prompt,
            sender_name=sender_name,
            sender_profession=sender_profession,
            language=language
        )
        st.session_state["generated_doc"] = result["document"]
        st.session_state["generated_metadata"] = result["metadata"]
        # Add to history
        if "history" not in st.session_state:
            st.session_state["history"] = []
        st.session_state["history"].append({
            "document": result["document"],
            "metadata": result["metadata"]
        })
        st.success("Document generated!")

if "generated_doc" in st.session_state:
    st.subheader("Generated Document")
    st.text_area("Document", st.session_state["generated_doc"], height=300)
    # Export options
    exporter = DocumentExporter()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Export as PDF"):
            pdf_path = exporter.export_to_pdf(st.session_state["generated_doc"], st.session_state["generated_metadata"])
            with open(pdf_path, "rb") as f:
                st.download_button("Download PDF", f, file_name=pdf_path.split(os.sep)[-1])
    with col2:
        if st.button("Export as DOCX"):
            docx_path = exporter.export_to_docx(st.session_state["generated_doc"], st.session_state["generated_metadata"])
            with open(docx_path, "rb") as f:
                st.download_button("Download DOCX", f, file_name=docx_path.split(os.sep)[-1])
    with col3:
        if st.button("Export as TXT"):
            txt_path = exporter.export_to_txt(st.session_state["generated_doc"], st.session_state["generated_metadata"])
            with open(txt_path, "rb") as f:
                st.download_button("Download TXT", f, file_name=txt_path.split(os.sep)[-1])

# Document history
if "history" in st.session_state and st.session_state["history"]:
    st.sidebar.subheader("Document History")
    for idx, item in enumerate(reversed(st.session_state["history"])):
        if st.sidebar.button(f"View Document {len(st.session_state['history'])-idx}"):
            st.session_state["generated_doc"] = item["document"]
            st.session_state["generated_metadata"] = item["metadata"] 