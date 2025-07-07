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
        "show_preview": False,
        "preview_doc_idx": None,
        "show_suggestions": True,
        "selected_suggestion": None,
        "last_doc_type": None,
        "exported_file": None,
        "exported_file_name": None,
        "exported_file_mime": None,
        "message_counter": 0  # Add counter for unique keys
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# --- Utility Functions ---
def open_preview(idx):
    st.session_state.show_preview = True
    st.session_state.preview_doc_idx = idx

def close_preview():
    st.session_state.show_preview = False
    st.session_state.preview_doc_idx = None

# --- Sidebar UI ---
def render_sidebar():
    with st.sidebar:
        st.markdown("### TUM Document Generator")
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
        
        if st.session_state.document_history:
            doc_counts = {}
            for doc in st.session_state.document_history:
                key = (doc.get('type', 'Unknown'), doc.get('tone', 'Neutral'))
                doc_counts[key] = doc_counts.get(key, 0) + 1
                doc['doc_number'] = doc_counts[key]
            
            for idx, doc in enumerate(reversed(st.session_state.document_history)):
                title = f"{doc.get('type', 'Unknown')}_{doc.get('tone', 'Neutral')}_{doc['doc_number']}"
                
                with st.expander(f"📄 {title}", expanded=False):
                    st.text_area(
                        "Content Preview:",
                        value=doc['content'][:300] + "..." if len(doc['content']) > 300 else doc['content'],
                        height=100,
                        disabled=True,
                        key=f"preview_text_{idx}"
                    )
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("👁️ Full Preview", key=f"preview_btn_{idx}"):
                            open_preview(idx)
                    
                    with col2:
                        try:
                            exporter = DocumentExporter()
                            pdf_bytes = exporter.export_to_pdf(doc['content'], {"doc_type": doc.get('type'), "tone": doc.get('tone')})
                            st.download_button(
                                label="📑 PDF",
                                data=pdf_bytes,
                                file_name=f"TUM_{doc.get('type', 'Document')}_{doc.get('tone', 'Neutral')}.pdf",
                                mime="application/pdf",
                                key=f"download_pdf_{idx}"
                            )
                        except Exception as e:
                            st.error(f"PDF export error: {str(e)}")
                    
                    with col3:
                        try:
                            exporter = DocumentExporter()
                            docx_bytes = exporter.export_to_docx(doc['content'], {"doc_type": doc.get('type'), "tone": doc.get('tone')})
                            st.download_button(
                                label="📘 DOCX",
                                data=docx_bytes,
                                file_name=f"TUM_{doc.get('type', 'Document')}_{doc.get('tone', 'Neutral')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"download_docx_{idx}"
                            )
                        except Exception as e:
                            st.error(f"DOCX export error: {str(e)}")
        else:
            st.info("No documents generated yet.")
        
        return doc_type, tone, sender_name, sender_profession, language

# --- Chat UI ---
def render_chat():
    st.markdown("### 💬 Chat Interface")
    
    # Create a container for messages with proper styling
    chat_container = st.container()
    
    with chat_container:
        for i, message in enumerate(st.session_state.messages):
            role = message['role']
            content = message['content']
            
            if role == 'user':
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end; margin: 10px 0;">
                    <div style="background-color: #0066cc; color: white; padding: 10px 15px; 
                                border-radius: 15px 15px 5px 15px; max-width: 70%; 
                                word-wrap: break-word;">
                        <strong>You:</strong><br>{content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start; margin: 10px 0;">
                    <div style="background-color: #f0f0f0; color: black; padding: 10px 15px; 
                                border-radius: 15px 15px 15px 5px; max-width: 70%; 
                                word-wrap: break-word;">
                        <strong>Assistant:</strong><br>{content}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# --- Input UI ---
def render_input(doc_type):
    st.markdown("### ✍️ Your Message")
    
    # Show suggested prompts
    suggested = SUGGESTED_PROMPTS.get(doc_type, [])
    if st.session_state.show_suggestions and suggested:
        st.markdown("**Suggested prompts:**")
        cols = st.columns(len(suggested))
        for i, suggestion in enumerate(suggested):
            if cols[i].button(suggestion, key=f"suggestion_{i}_{st.session_state.message_counter}"):
                return True, suggestion
    
    # Input form
    with st.form(key="message_form", clear_on_submit=True):
        prompt = st.text_area(
            "Type your message here:",
            placeholder="Enter your prompt or refinement request...",
            height=100,
            key="user_input"
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            send_clicked = st.form_submit_button(
                "Send ✉️", 
                disabled=st.session_state.is_generating,
                use_container_width=True
            )
        with col2:
            if st.session_state.is_generating:
                st.info("🔄 Generating response...")
    
    return send_clicked, prompt

# --- Main App Logic ---
def main():
    # Page configuration
    st.set_page_config(
        page_title="TUM Admin Document Generator",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main > div {
        padding-top: 2rem;
    }
    .stForm {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e9ecef;
    }
    .stExpander {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 5px;
        margin-bottom: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📄 TUM Admin Document Generator")
    st.markdown("Generate and refine administrative documents with AI assistance.")
    
    # Initialize session state
    init_session_state()
    
    # Render sidebar and get settings
    doc_type, tone, sender_name, sender_profession, language = render_sidebar()
    
    # Handle document type changes
    if st.session_state.last_doc_type != doc_type:
        st.session_state.show_suggestions = True
        st.session_state.selected_suggestion = None
        st.session_state.last_doc_type = doc_type
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Chat interface
        render_chat()
        
        # Input interface
        send_clicked, prompt = render_input(doc_type)
        
        # Process message
        if send_clicked and prompt.strip():
            # Increment message counter for unique keys
            st.session_state.message_counter += 1
            
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.is_generating = True
            st.session_state.show_suggestions = False
            
            # Generate response
            try:
                with st.spinner("🤖 Generating response..."):
                    llm = LLMService()
                    
                    if st.session_state.document_history:
                        # Refinement mode
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
                        
                        # Handle different result types
                        if hasattr(result, '__iter__') and not isinstance(result, str):
                            full_response = "".join(chunk.get("document", str(chunk)) for chunk in result)
                        elif isinstance(result, dict) and "document" in result:
                            full_response = result["document"]
                        else:
                            full_response = str(result)
                    else:
                        # New document generation
                        result = llm.generate_document(
                            doc_type=DocumentType(doc_type),
                            tone=ToneType(tone),
                            prompt=prompt,
                            sender_name=sender_name,
                            sender_profession=sender_profession,
                            language=language
                        )
                        full_response = result.get("document", str(result)) if isinstance(result, dict) else str(result)
                    
                    # Add assistant response
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.session_state.current_document = full_response
                    
                    # Add to document history
                    st.session_state.document_history.append({
                        "type": doc_type,
                        "tone": tone,
                        "content": full_response,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    st.success("✅ Document generated successfully!")
                    
            except Exception as e:
                st.error(f"❌ Error generating document: {str(e)}")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"Sorry, I encountered an error: {str(e)}"
                })
            
            finally:
                st.session_state.is_generating = False
                st.rerun()
    
    with col2:
        # Document preview modal
        if st.session_state.show_preview and st.session_state.preview_doc_idx is not None:
            doc = st.session_state.document_history[-(st.session_state.preview_doc_idx + 1)]
            
            st.markdown("### 📖 Document Preview")
            st.markdown("---")
            
            # Document metadata
            st.markdown(f"**Type:** {doc.get('type', 'Unknown')}")
            st.markdown(f"**Tone:** {doc.get('tone', 'Neutral')}")
            st.markdown(f"**Created:** {doc.get('timestamp', 'Unknown')}")
            st.markdown("---")
            
            # Document content
            st.markdown("**Content:**")
            st.markdown(doc['content'])
            
            if st.button("❌ Close Preview", key="close_preview_btn"):
                close_preview()
                st.rerun()
        
        # Current document info
        if st.session_state.current_document:
            st.markdown("### 📄 Current Document")
            st.info(f"Document ready! ({len(st.session_state.document_history)} total documents)")
            
            if st.button("🔄 Clear All Documents", key="clear_all_btn"):
                st.session_state.document_history = []
                st.session_state.current_document = None
                st.session_state.messages = []
                st.success("All documents cleared!")
                st.rerun()

if __name__ == "__main__":
    main()
