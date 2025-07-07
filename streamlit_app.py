import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from document_models import DocumentType, ToneType
from llm_service import LLMService
from export_service import DocumentExporter
import asyncio
import time

# Load environment variables for local dev
load_dotenv()
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))

# --- Constants ---
SUGGESTED_PROMPTS = {
    "Announcement": [
        "Please write an announcement about a change in lecture schedule for the GenAI course.",
        "Announce the cancellation of tomorrow's seminar due to unforeseen circumstances.",
        "Inform students about the upcoming registration deadline for the summer semester."
    ],
    "Student Communication": [
        "Send a reminder to students about the upcoming exam and required materials.",
        "Communicate the new office hours for the academic advisor.",
        "Notify students about the availability of new course materials on Moodle."
    ],
    "Meeting Summary": [
        "Summarize the key points and action items from today's faculty meeting.",
        "Provide a summary of the decisions made during the student council meeting.",
        "List the main discussion topics from the recent department meeting."
    ]
}

# --- Session State Initialization ---
def init_session_state():
    defaults = {
        "messages": [],
        "current_document": None,
        "document_history": [],
        "is_generating": False,
        "input_key": 0,
        "show_preview": False,
        "preview_doc_idx": None,
        "prompt_input": "",
        "show_suggestions": True,
        "selected_suggestion": None,
        "last_doc_type": None,
        "exported_file": None,
        "exported_file_name": None,
        "exported_file_mime": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# --- Utility Functions ---
def simulate_streaming(text, chunk_size=10):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]
        time.sleep(0.02)

def open_preview(idx):
    st.session_state.show_preview = True
    st.session_state.preview_doc_idx = idx

def close_preview():
    st.session_state.show_preview = False
    st.session_state.preview_doc_idx = None

# --- Sidebar UI ---
def render_sidebar():
    with st.sidebar:
        st.markdown('<div class="sidebar-header">', unsafe_allow_html=True)
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
            st.markdown(f"""
            <div class="history-item">
                <div class="history-item-header">
                    <span class="history-item-title">{title}</span>
                </div>
                <div class="history-item-content">{doc['content'][:200]}{'...' if len(doc['content']) > 200 else ''}</div>
                <div class="history-item-actions">
            """, unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                if st.button("👁️ Preview", key=f"preview_{idx}"):
                    open_preview(idx)
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
            st.markdown("</div></div>", unsafe_allow_html=True)
        return doc_type, tone, sender_name, sender_profession, language

# --- Chat UI ---
def render_chat():
    for message in st.session_state.messages:
        role = message['role']
        avatar = '👤' if role == 'user' else '🤖'
        bubble_class = 'user' if role == 'user' else 'assistant'
        st.markdown(f'''
        <div class="tum-chat-message {bubble_class}">
            <div class="tum-chat-avatar">{avatar}</div>
            <div class="tum-chat-bubble">{message['content']}</div>
        </div>
        ''', unsafe_allow_html=True)

# --- Input UI ---
def render_input(doc_type):
    # ✅ Clear input BEFORE rendering the widget
    if st.session_state.get("clear_prompt_input", False):
        st.session_state["prompt_input"] = ""
        st.session_state["clear_prompt_input"] = False

    with st.container():
        st.markdown('<div class="input-container">', unsafe_allow_html=True)
        suggested = SUGGESTED_PROMPTS.get(doc_type, [])
        if st.session_state["show_suggestions"] and suggested:
            st.markdown("<div style='margin-bottom: 0.5rem; font-weight: 600;'>Suggested prompts:</div>", unsafe_allow_html=True)
            cols = st.columns(len(suggested))
            for i, suggestion in enumerate(suggested):
                if cols[i].button(suggestion, key=f"suggestion_{i}"):
                    st.session_state["prompt_input"] = suggestion
                    st.session_state["selected_suggestion"] = i
        prompt = st.text_area(
            "Your prompt",
            placeholder="Type your message here...",
            key="prompt_input",
            height=68,
            label_visibility="collapsed"
        )
        send_clicked = st.button("Send ✉️", key="send_button", disabled=st.session_state.is_generating)
        st.markdown('</div>', unsafe_allow_html=True)
        return send_clicked, prompt

# --- Main App Logic ---
def main():
    st.title("TUM Admin")
    st.markdown("""
    <style>
    .tum-chat-container {
        max-width: 700px;
        margin: 2rem auto 1rem auto;
        padding: 1.5rem 2rem;
        background: #f8f9fa;
        border-radius: 1.5rem;
        box-shadow: 0 4px 32px rgba(0,100,170,0.08);
        height: 65vh;
        overflow-y: auto;
    }
    .tum-chat-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0064AA;
        margin-bottom: 1.2rem;
        text-align: center;
        letter-spacing: 0.5px;
    }
    .tum-chat-message {
        display: flex;
        align-items: flex-start;
        margin-bottom: 1.2rem;
    }
    .tum-chat-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #0064AA;
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        font-weight: bold;
        margin-right: 0.8rem;
        flex-shrink: 0;
    }
    .tum-chat-bubble {
        padding: 1.1rem 1.3rem;
        border-radius: 1.2rem;
        font-size: 1.08rem;
        line-height: 1.7;
        background: #fff;
        color: #222;
        box-shadow: 0 2px 8px rgba(0,100,170,0.07);
        max-width: 80%;
        word-break: break-word;
    }
    .tum-chat-message.user .tum-chat-bubble {
        background: #0064AA;
        color: #fff;
        margin-left: auto;
    }
    .tum-chat-message.user .tum-chat-avatar {
        background: #e6e6e6;
        color: #0064AA;
        margin-left: 0.8rem;
        margin-right: 0;
    }
    .tum-chat-message.assistant .tum-chat-bubble {
        background: #e6e6e6;
        color: #222;
    }
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 1rem;
        background-color: white;
        border-top: 1px solid #E6E6E6;
        display: flex;
        gap: 1rem;
        align-items: center;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
        z-index: 100;
        max-width: 900px;
        margin: 0 auto;
    }
    </style>
    """, unsafe_allow_html=True)
    init_session_state()
    doc_type, tone, sender_name, sender_profession, language = render_sidebar()
    if st.session_state["last_doc_type"] != doc_type:
        st.session_state["show_suggestions"] = True
        st.session_state["selected_suggestion"] = None
        st.session_state["last_doc_type"] = doc_type
        st.session_state["prompt_input"] = ""
    send_clicked, prompt = render_input(doc_type)
    if send_clicked and prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.is_generating = True
        st.session_state["show_suggestions"] = False
        st.session_state["selected_suggestion"] = None
        st.session_state["clear_prompt_input"] = True
        with st.spinner("Generating response..."):
            llm = LLMService()
            if st.session_state.document_history:
                last_doc = st.session_state.document_history[-1]
                doc_type_val = last_doc.get("type", doc_type)
                tone_val = last_doc.get("tone", tone)
                history_docs = [d["content"] for d in st.session_state.document_history]
                result = llm.refine_document(
                    current_document=last_doc["content"],
                    refinement_prompt=prompt,
                    doc_type=DocumentType(doc_type_val),
                    tone=ToneType(tone_val),
                    history=history_docs
                )
                if hasattr(result, '__iter__') and not isinstance(result, str):
                    full_response = "".join(chunk["document"] for chunk in result)
                else:
                    full_response = result["document"] if isinstance(result, dict) else str(result)
            else:
                result = llm.generate_document(
                    doc_type=DocumentType(doc_type),
                    tone=ToneType(tone),
                    prompt=prompt,
                    sender_name=sender_name,
                    sender_profession=sender_profession,
                    language=language
                )
                full_response = result["document"] if result else "[Error: No response]"
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.session_state.current_document = full_response
            st.session_state.document_history.append({
                "type": doc_type,
                "tone": tone,
                "content": full_response,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        st.session_state.is_generating = False
    render_chat()
    # Document Preview Modal (use expander for robust refresh)
    if st.session_state.show_preview and st.session_state.preview_doc_idx is not None:
        doc = st.session_state.document_history[-(st.session_state.preview_doc_idx+1)]
        with st.expander("Document Preview", expanded=True):
            st.markdown(doc['content'])
            if st.button("Close Preview"):
                st.session_state.show_preview = False
    if st.session_state.exported_file:
        st.download_button(
            label=f"Download {st.session_state.exported_file_name}",
            data=st.session_state.exported_file,
            file_name=st.session_state.exported_file_name,
            mime=st.session_state.exported_file_mime,
            key="download_btn"
        )

if __name__ == "__main__":
    main() 