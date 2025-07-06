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

# --- (The rest of your Streamlit UI and logic goes here, adapted from app/web/main.py) ---
# For brevity, only the structure and key logic are shown. You should copy over your UI, chat, and document logic here.

st.title("TUM Admin Assistant")

st.sidebar.header("Settings")
doc_type = st.sidebar.selectbox("Document Type", [e.value for e in DocumentType])
tone = st.sidebar.selectbox("Tone", [e.value for e in ToneType])
sender_name = st.sidebar.text_input("Sender Name", "Prof. Example")
sender_profession = st.sidebar.text_input("Sender Profession", "Professor")
language = st.sidebar.selectbox("Language", ["English", "German"])

prompt = st.text_area("Enter your prompt or announcement details:")

if st.button("Generate Document"):
    if not GOOGLE_API_KEY:
        st.error("Google API key not set. Please configure it in Streamlit secrets or your .env file.")
    else:
        llm = LLMService(api_key=GOOGLE_API_KEY)
        doc_type_enum = DocumentType([k for k in DocumentType if DocumentType[k].value == doc_type][0])
        tone_enum = ToneType([k for k in ToneType if ToneType[k].value == tone][0])
        result = llm.generate_document(
            doc_type=doc_type_enum,
            tone=tone_enum,
            prompt=prompt,
            sender_name=sender_name,
            sender_profession=sender_profession,
            language=language
        )
        st.session_state["generated_doc"] = result["document"]
        st.success("Document generated!")

if "generated_doc" in st.session_state:
    st.subheader("Generated Document")
    st.text_area("Document", st.session_state["generated_doc"], height=300)
    st.download_button(
        label="Download as TXT",
        data=st.session_state["generated_doc"],
        file_name="TUM_Document.txt"
    )
    # Add export options for PDF/DOCX using DocumentExporter if needed 