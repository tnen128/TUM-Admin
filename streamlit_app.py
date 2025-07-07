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
        "message_counter": 0,
        "refinement_mode": False
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

def clean_response_text(text):
    """Clean HTML tags and unwanted formatting from response"""
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
            for idx, doc in enumerate(reversed(st.session_state.document_history)):
                title = f"{doc.get('type', 'Unknown')} - {doc.get('timestamp', 'Unknown')}"
                
                with st.expander(f"📄 {title}", expanded=False):
                    st.text_area(
                        "Content Preview:",
                        value=doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content'],
                        height=80,
                        disabled=True,
                        key=f"preview_text_{idx}"
                    )
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("👁️ View", key=f"preview_btn_{idx}"):
                            open_preview(idx)
                    
                    with col2:
                        try:
                            exporter = DocumentExporter()
                            pdf_bytes = exporter.export_to_pdf(doc['content'], {"doc_type": doc.get('type'), "tone": doc.get('tone')})
                            st.download_button(
                                label="📑 PDF",
                                data=pdf_bytes,
                                file_name=f"TUM_{doc.get('type', 'Document')}.pdf",
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
                                file_name=f"TUM_{doc.get('type', 'Document')}.docx",
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
    if st.session_state.messages:
        for i, message in enumerate(st.session_state.messages):
            role = message['role']
            content = clean_response_text(message['content'])  # Clean the content
            
            if role == 'user':
                with st.chat_message("user"):
                    st.write(content)
            else:
                with st.chat_message("assistant"):
                    st.write(content)

# --- Input UI ---
def render_input(doc_type):
    # Show suggested prompts only for new documents
    suggested = SUGGESTED_PROMPTS.get(doc_type, [])
    if st.session_state.show_suggestions and suggested and not st.session_state.document_history:
        st.markdown("**💡 Suggested prompts:**")
        cols = st.columns(len(suggested))
        for i, suggestion in enumerate(suggested):
            if cols[i].button(suggestion, key=f"suggestion_{i}_{st.session_state.message_counter}"):
                return True, suggestion
    
    # Show refinement mode indicator
    if st.session_state.document_history:
        st.info("🔄 **Refinement Mode**: Your next message will refine the latest document.")
    
    # Input form
    with st.form(key="message_form", clear_on_submit=True):
        if st.session_state.document_history:
            placeholder_text = "Enter your refinement request (e.g., 'change course name to C++', 'make it more formal', etc.)"
        else:
            placeholder_text = "Enter your prompt to generate a new document..."
            
        prompt = st.text_area(
            "Your message:",
            placeholder=placeholder_text,
            height=100,
            key="user_input"
        )
        
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            send_clicked = st.form_submit_button(
                "Send ✉️", 
                disabled=st.session_state.is_generating,
                use_container_width=True
            )
        with col2:
            if st.button("🗑️ Clear Chat", key="clear_chat"):
                st.session_state.messages = []
                st.session_state.document_history = []
                st.session_state.current_document = None
                st.session_state.show_suggestions = True
                st.rerun()
        
        with col3:
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
    
    st.title("📄 TUM Admin Document Generator")
    
    # Initialize session state
    init_session_state()
    
    # Render sidebar and get settings
    doc_type, tone, sender_name, sender_profession, language = render_sidebar()
    
    # Handle document type changes
    if st.session_state.last_doc_type != doc_type:
        st.session_state.show_suggestions = True
        st.session_state.last_doc_type = doc_type
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
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
                        # Refinement mode - get the latest document
                        last_doc = st.session_state.document_history[-1]
                        
                        # Call refine_document with proper parameters
                        result = llm.refine_document(
                            current_document=last_doc["content"],
                            refinement_prompt=prompt,
                            doc_type=DocumentType(last_doc.get("type", doc_type)),
                            tone=ToneType(last_doc.get("tone", tone)),
                            history=[d["content"] for d in st.session_state.document_history[:-1]]  # Exclude current doc from history
                        )
                        
                        # Extract the refined document
                        if isinstance(result, dict) and "document" in result:
                            full_response = result["document"]
                        elif hasattr(result, '__iter__') and not isinstance(result, str):
                            full_response = "".join(chunk.get("document", str(chunk)) for chunk in result)
                        else:
                            full_response = str(result)
                        
                        # Update the latest document in history instead of creating new one
                        st.session_state.document_history[-1] = {
                            "type": last_doc.get("type", doc_type),
                            "tone": last_doc.get("tone", tone),
                            "content": clean_response_text(full_response),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
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
                        
                        if isinstance(result, dict) and "document" in result:
                            full_response = result["document"]
                        else:
                            full_response = str(result)
                        
                        # Add new document to history
                        st.session_state.document_history.append({
                            "type": doc_type,
                            "tone": tone,
                            "content": clean_response_text(full_response),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    
                    # Clean and add assistant response
                    clean_response = clean_response_text(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": clean_response})
                    st.session_state.current_document = clean_response
                    
                    st.success("✅ Document processed successfully!")
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"Sorry, I encountered an error: {str(e)}"
                })
            
            finally:
                st.session_state.is_generating = False
                st.rerun()
    
    with col2:
        # Document preview
        if st.session_state.show_preview and st.session_state.preview_doc_idx is not None:
            doc = st.session_state.document_history[-(st.session_state.preview_doc_idx + 1)]
            
            st.markdown("### 📖 Document Preview")
            st.markdown("---")
            
            st.markdown(f"**Type:** {doc.get('type', 'Unknown')}")
            st.markdown(f"**Tone:** {doc.get('tone', 'Neutral')}")
            st.markdown(f"**Created:** {doc.get('timestamp', 'Unknown')}")
            st.markdown("---")
            
            st.markdown("**Content:**")
            st.markdown(doc['content'])
            
            if st.button("❌ Close", key="close_preview_btn"):
                close_preview()
                st.rerun()
        
        # Current document status
        elif st.session_state.current_document:
            st.markdown("### 📄 Current Status")
            st.success(f"✅ {len(st.session_state.document_history)} document(s) ready")
            
            if st.session_state.document_history:
                latest_doc = st.session_state.document_history[-1]
                st.info(f"**Latest:** {latest_doc.get('type', 'Unknown')}")
                st.info(f"**Words:** {len(latest_doc['content'].split())}")

if __name__ == "__main__":
    main()
