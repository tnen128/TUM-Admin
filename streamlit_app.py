import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from document_models import DocumentType, ToneType
from llm_service import LLMService
from export_service import DocumentExporter
import asyncio

# Load environment variables for local dev
load_dotenv()
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))

# --- Session State Initialization ---
def init_session_state():
    defaults = {
        "messages": [],
        "current_document": None,
        "document_history": [],
        "is_generating": False,
        "typing": False,
        "input_key": 0,
        "show_preview": False,
        "preview_doc_idx": None,
        "prompt_input": "",
        "show_suggestions": True,
        "selected_suggestion": None,
        "clear_prompt_input": False,
        "last_doc_type": None,
        "exported_file": None,
        "exported_file_name": None,
        "exported_file_mime": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# --- Sidebar UI ---
def render_sidebar():
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
        return doc_type, tone, sender_name, sender_profession, language

# --- Chat UI ---
def render_chat():
    st.markdown('<div class="tum-chat-container">', unsafe_allow_html=True)
    st.markdown('<div class="tum-chat-title">TUM Admin Assistant <span>🎓</span></div>', unsafe_allow_html=True)
    for message in st.session_state.messages:
        role = message["role"]
        avatar = "👤" if role == "user" else "🤖"
        bubble_class = "user" if role == "user" else "assistant"
        st.markdown(f"""
        <div class="tum-chat-message {bubble_class}">
            <div class="tum-chat-avatar">{avatar}</div>
            <div class="tum-chat-bubble">{message['content']}</div>
        </div>
        """, unsafe_allow_html=True)
    if st.session_state.get("typing", False):
        st.markdown("""
        <div class="tum-chat-message assistant" style="max-width: 300px; min-width: 80px; min-height: 50px; height: 50px; display: flex; align-items: center; justify-content: center; padding: 0.2rem 0.7rem;">
            <div class="content" style="width:100%; height:100%; display: flex; align-items: center; justify-content: center;">
                <div class="tum-chat-avatar">🤖</div>
                <div class="tum-chat-bubble" style="font-size: 1.05rem; font-weight: 500; margin-left: 0.5rem; display: flex; align-items: center; justify-content: center; height: 100%; width: 100%;">
                    <span style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%;">Agent typing <span class="typing-indicator-dots" style="margin-left: 0.2rem;"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span></span>
                </div>
            </div>
        </div>
        <style>
        @keyframes blink {
            0% { opacity: 0.2; }
            20% { opacity: 1; }
            100% { opacity: 0.2; }
        }
        .typing-indicator-dots .dot {
            font-size: 1.2rem;
            opacity: 0.2;
            animation: blink 1.4s infinite both;
        }
        .typing-indicator-dots .dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        .typing-indicator-dots .dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        </style>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- Input UI ---
def render_input(doc_type):
    with st.container():
        suggested_prompts = {
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
        suggested = suggested_prompts.get(doc_type, [])
        if st.session_state["show_suggestions"] and suggested:
            st.markdown("<div style='margin-bottom: 0.5rem; font-weight: 600;'>Suggested prompts:</div>", unsafe_allow_html=True)
            cols = st.columns(len(suggested))
            for i, suggestion in enumerate(suggested):
                if cols[i].button(suggestion, key=f"suggestion_{i}"):
                    st.session_state["prompt_input"] = suggestion
                    st.session_state["selected_suggestion"] = i
        if st.session_state.get("clear_prompt_input", False):
            st.session_state["prompt_input"] = ""
            st.session_state["clear_prompt_input"] = False
        prompt = st.text_area("", placeholder="Type your message here...", key="prompt_input", height=68)
        send_clicked = st.button("Send ✉️", key="send_button", disabled=st.session_state.is_generating)
        return send_clicked, prompt

# --- Main App Logic ---
def main():
    st.markdown("""
    <style>
    .tum-chat-container {
        max-width: 700px;
        margin: 2rem auto 1rem auto;
        padding: 1.5rem 2rem;
        background: #f8f9fa;
        border-radius: 1.5rem;
        box-shadow: 0 4px 32px rgba(0,100,170,0.08);
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
    </style>
    """, unsafe_allow_html=True)
    init_session_state()
    doc_type, tone, sender_name, sender_profession, language = render_sidebar()
    if st.session_state["last_doc_type"] != doc_type:
        st.session_state["show_suggestions"] = True
        st.session_state["selected_suggestion"] = None
        st.session_state["last_doc_type"] = doc_type
        st.session_state["prompt_input"] = ""
    render_chat()
    send_clicked, prompt = render_input(doc_type)
    if send_clicked and prompt:
        st.session_state["show_suggestions"] = False
        st.session_state["selected_suggestion"] = None
        st.session_state["clear_prompt_input"] = True
        st.session_state.is_generating = True
        st.session_state["typing"] = True
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.experimental_rerun()
    if st.session_state.get("typing", False) and st.session_state.is_generating:
        message_placeholder = st.empty()
        with st.spinner(""):
            llm = LLMService()
            if st.session_state.document_history:
                last_doc = st.session_state.document_history[-1]
                doc_type_val = last_doc.get("type", doc_type)
                tone_val = last_doc.get("tone", tone)
                history_docs = [d["content"] for d in st.session_state.document_history]
                async def get_refined_chunks():
                    chunks = []
                    async for chunk in llm.refine_document(
                        current_document=last_doc["content"],
                        refinement_prompt=st.session_state["messages"][-1]["content"],
                        doc_type=DocumentType(doc_type_val),
                        tone=ToneType(tone_val),
                        history=history_docs
                    ):
                        chunks.append(chunk["document"])
                        message_placeholder.markdown(f"""
                        <div class=\"tum-chat-message assistant\">
                            <div class=\"tum-chat-avatar\">🤖</div>
                            <div class=\"tum-chat-bubble\">{''.join(chunks)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    return "".join(chunks)
                full_response = asyncio.run(get_refined_chunks())
                st.session_state.current_document = full_response
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.session_state.document_history.append({
                    "type": doc_type_val,
                    "tone": tone_val,
                    "content": full_response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            else:
                llm = LLMService()
                result = llm.generate_document(
                    doc_type=DocumentType(doc_type),
                    tone=ToneType(tone),
                    prompt=st.session_state["messages"][-1]["content"],
                    sender_name=sender_name,
                    sender_profession=sender_profession,
                    language=language
                )
                if result:
                    full_response = result["document"]
                    for i in range(0, len(full_response), 50):
                        chunk = full_response[:i+50]
                        message_placeholder.markdown(f"""
                        <div class=\"tum-chat-message assistant\">
                            <div class=\"tum-chat-avatar\">🤖</div>
                            <div class=\"tum-chat-bubble\">{chunk}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    st.session_state.current_document = full_response
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.session_state.document_history.append({
                        "type": doc_type,
                        "tone": tone,
                        "content": full_response,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        st.session_state.is_generating = False
        st.session_state["typing"] = False
        st.experimental_rerun()

if __name__ == "__main__":
    main() 