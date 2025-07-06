import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from document_models import DocumentType, ToneType
from llm_service import LLMService
from export_service import DocumentExporter

# Load environment variables for local dev
load_dotenv()
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_document" not in st.session_state:
    st.session_state.current_document = None
if "document_history" not in st.session_state:
    st.session_state.document_history = []
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False
if "typing" not in st.session_state:
    st.session_state.typing = False
if "input_key" not in st.session_state:
    st.session_state.input_key = 0
if "show_preview" not in st.session_state:
    st.session_state.show_preview = False
if "preview_doc_idx" not in st.session_state:
    st.session_state.preview_doc_idx = None
if "prompt_input" not in st.session_state:
    st.session_state["prompt_input"] = ""

# --- Sidebar: Document Settings & History ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/c/c8/Logo_of_the_Technical_University_of_Munich.svg", width=150)
    st.markdown("### Document Settings")
    doc_type = st.selectbox(
        "📄 Document Type",
        options=[dt.value for dt in DocumentType],
        format_func=lambda x: x.replace("_", " ").title()
    )
    tone = st.selectbox(
        "🎭 Tone",
        options=[t.value for t in ToneType],
        format_func=lambda x: x.replace("_", " ").title()
    )
    sender_name = st.text_input("Sender Name", value="")
    sender_profession = st.text_input("Sender Profession", value="")
    language = st.selectbox("Language", options=["English", "German", "Both"], index=0)
    st.markdown("---")
    st.markdown("### 📜 Document History")
    doc_counts = {}
    for doc in st.session_state.document_history:
        key = (doc.get('type', 'Unknown'), doc.get('tone', 'Neutral'))
        doc_counts[key] = doc_counts.get(key, 0) + 1
        doc['doc_number'] = doc_counts[key]
    for idx, doc in enumerate(reversed(st.session_state.document_history)):
        title = f"[{doc.get('type', 'Unknown')}_{doc.get('tone', 'Neutral')}_{doc['doc_number']}]"
        st.markdown(f"**{title}**\n{doc['content'][:100]}{'...' if len(doc['content']) > 100 else ''}")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("👁️ Preview", key=f"preview_{idx}"):
                st.session_state.show_preview = True
                st.session_state.preview_doc_idx = idx
        with col2:
            exporter = DocumentExporter()
            pdf_bytes = exporter.export_to_pdf(doc['content'], {"doc_type": doc.get('type'), "tone": doc.get('tone')})
            with open(pdf_bytes, "rb") as f:
                st.download_button(
                    label="📑 PDF",
                    data=f,
                    file_name=f"TUM_{doc.get('type', 'Document')}_{doc.get('tone', 'Neutral')}.pdf",
                    mime="application/pdf",
                    key=f"download_pdf_{idx}"
                )
        with col3:
            docx_bytes = exporter.export_to_docx(doc['content'], {"doc_type": doc.get('type'), "tone": doc.get('tone')})
            with open(docx_bytes, "rb") as f:
                st.download_button(
                    label="📘 DOCX",
                    data=f,
                    file_name=f"TUM_{doc.get('type', 'Document')}_{doc.get('tone', 'Neutral')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"download_docx_{idx}"
                )

# --- Document Preview Modal ---
if st.session_state.show_preview and st.session_state.preview_doc_idx is not None:
    doc = st.session_state.document_history[-(st.session_state.preview_doc_idx+1)]
    st.markdown(
        f'''<div style="background: #23272b; border-radius: 1.2rem; box-shadow: 0 12px 48px rgba(0,100,170,0.22); max-width: 900px; margin: 3% auto 2rem auto; padding: 2.7rem 2.5rem 2.2rem 2.5rem; border: 2.5px solid #0064AA;">
        <div style="font-size: 1.5rem; font-weight: 800; color: #fff; letter-spacing: 0.5px; margin-bottom: 1.5rem; text-align: left;">
            📢 Announcement Preview
        </div>
        <div style="background: #181c20; border-radius: 0.9rem; padding: 1.6rem 1.3rem; color: #f5f5f5; font-size: 1.18rem; line-height: 1.8; min-height: 260px; max-height: 600px; overflow-y: auto; white-space: pre-wrap; border: 1px solid #333;">
        {doc['content'].replace('<','&lt;').replace('>','&gt;').rstrip('</div>').rstrip()}</div></div>''',
        unsafe_allow_html=True
    )
    st.button("Close Preview", on_click=lambda: (st.session_state.update({"show_preview": False, "preview_doc_idx": None})), key="close_preview_btn", help="Close this preview")

# --- Main Chat Interface ---
st.title("TUM Admin Assistant 🤖")
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        st.markdown(f"""
        <div style='margin-bottom: 1rem;'><b>{'👤' if message['role'] == 'user' else '🤖'}:</b> {message['content']}</div>
        """, unsafe_allow_html=True)
    if st.session_state.typing:
        st.markdown("<i>Assistant is typing...</i>", unsafe_allow_html=True)

# --- Input Container ---
with st.form("chat_form", clear_on_submit=True):
    prompt = st.text_area("", placeholder="Type your message here...", key="prompt_input", height=50)
    submitted = st.form_submit_button("Send ✉️", disabled=st.session_state.is_generating)

if submitted and prompt:
    st.session_state.is_generating = True
    st.session_state.typing = True
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner(""):
        # If there is a previous document, treat as refinement
        if st.session_state.document_history:
            last_doc = st.session_state.document_history[-1]
            doc_type_val = last_doc.get("type", doc_type)
            tone_val = last_doc.get("tone", tone)
            # Send the full document history for context
            history_docs = [d["content"] for d in st.session_state.document_history]
            llm = LLMService(api_key=GOOGLE_API_KEY)
            refined = llm.generate_document(
                doc_type=DocumentType(doc_type_val),
                tone=ToneType(tone_val),
                prompt=prompt,
                additional_context="\n".join(history_docs),
                sender_name=sender_name,
                sender_profession=sender_profession,
                language=language
            )
            if refined:
                full_response = refined["document"]
                st.session_state.current_document = full_response
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.session_state.document_history.append({
                    "type": doc_type_val,
                    "tone": tone_val,
                    "content": full_response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        else:
            # No previous document, generate new
            llm = LLMService(api_key=GOOGLE_API_KEY)
            result = llm.generate_document(
                doc_type=DocumentType(doc_type),
                tone=ToneType(tone),
                prompt=prompt,
                sender_name=sender_name,
                sender_profession=sender_profession,
                language=language
            )
            if result:
                full_response = result["document"]
                st.session_state.current_document = full_response
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.session_state.document_history.append({
                    "type": doc_type,
                    "tone": tone,
                    "content": full_response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
    st.session_state.is_generating = False
    st.session_state.typing = False
    st.session_state["prompt_input"] = ""  # Clear input after sending
    st.experimental_rerun() 