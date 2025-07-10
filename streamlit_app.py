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
        "all_responses_history": [],  # Store all responses with proper naming
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
        "refinement_mode": False,
        "current_prompt": "",
        "form_key": 0,
        "response_counters": {}  # Track response numbers per doc_type + tone combination
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
    """Comprehensive cleaning to remove all markdown and formatting issues"""
    import re
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    
    # Remove all markdown formatting
    # Bold and italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic*
    text = re.sub(r'__(.*?)__', r'\1', text)      # __bold__
    text = re.sub(r'_(.*?)_', r'\1', text)        # _italic_
    
    # Headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Lists (remove markers but keep content)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)  # Bullet lists
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)  # Numbered lists
    
    # Remove horizontal rules
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*{3,}$', '', text, flags=re.MULTILINE)
    
    # Remove code blocks
    text = re.sub(r'``````', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
    
    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove extra dashes and special characters
    text = re.sub(r'^-+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*-+$', '', text, flags=re.MULTILINE)
    
    # Clean up lines
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        cleaned_line = line.strip()
        # Skip empty dashes or formatting lines
        if cleaned_line and not re.match(r'^[-=*_]+$', cleaned_line):
            cleaned_lines.append(cleaned_line)
        elif not cleaned_line:  # Keep empty lines for paragraph breaks
            cleaned_lines.append('')
    
    # Join and clean up
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 consecutive newlines
    result = result.strip()
    
    return result

def get_response_name(doc_type, tone):
    """Generate a unique response name following the pattern: doctype_tone_response_number"""
    key = f"{doc_type}_{tone}"
    
    if key not in st.session_state.response_counters:
        st.session_state.response_counters[key] = 0
    
    st.session_state.response_counters[key] += 1
    return f"{doc_type}_{tone}_response_{st.session_state.response_counters[key]}"

def add_to_all_responses_history(doc_type, tone, content, sender_name="", sender_profession=""):
    """Add response to the complete history with proper naming"""
    response_name = get_response_name(doc_type, tone)
    
    response_entry = {
        "name": response_name,
        "type": doc_type,
        "tone": tone,
        "content": content,
        "sender_name": sender_name,
        "sender_profession": sender_profession,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    st.session_state.all_responses_history.append(response_entry)

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
        
        # Enhanced mandatory fields with better UX
        sender_name = st.text_input(
            "👤 Sender Name *", 
            value="",
            placeholder="Enter your full name",
            help="Required field - This will appear as the document sender"
        )
        sender_profession = st.text_input(
            "💼 Sender Profession *", 
            value="",
            placeholder="e.g., Professor, Administrator, Dean",
            help="Required field - Your professional title or role"
        )
        
        # Smart validation feedback
        validation_status = []
        if not sender_name.strip():
            validation_status.append("Sender Name")
        if not sender_profession.strip():
            validation_status.append("Sender Profession")
        
        if validation_status:
            st.error(f"⚠️ Required: {', '.join(validation_status)}")
        else:
            st.success("✅ All required fields completed")
        
        language = st.selectbox("Language", options=["English", "German"], index=0)
        
        st.markdown("---")
        st.markdown("### 📜 All Responses History")
        
        if st.session_state.all_responses_history:
            for idx, response in enumerate(reversed(st.session_state.all_responses_history)):
                with st.expander(f"📄 {response['name']}", expanded=False):
                    st.markdown(f"**Type:** {response['type']}")
                    st.markdown(f"**Tone:** {response['tone']}")
                    st.markdown(f"**Created:** {response['timestamp']}")
                    st.markdown("---")
                    
                    st.text_area(
                        "Content Preview:",
                        value=response['content'][:300] + "..." if len(response['content']) > 300 else response['content'],
                        height=100,
                        disabled=True,
                        key=f"all_preview_text_{idx}"
                    )
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("👁️ View Full", key=f"all_preview_btn_{idx}"):
                            st.session_state.show_preview = True
                            st.session_state.preview_doc_idx = len(st.session_state.all_responses_history) - 1 - idx
                    
                    with col2:
                        try:
                            exporter = DocumentExporter()
                            pdf_bytes = exporter.export_to_pdf(response['content'], {"doc_type": response['type'], "tone": response['tone']})
                            st.download_button(
                                label="📑 PDF",
                                data=pdf_bytes,
                                file_name=f"TUM_{response['name']}.pdf",
                                mime="application/pdf",
                                key=f"all_download_pdf_{idx}"
                            )
                        except Exception as e:
                            st.error(f"PDF export error: {str(e)}")
                    
                    with col3:
                        try:
                            exporter = DocumentExporter()
                            docx_bytes = exporter.export_to_docx(response['content'], {"doc_type": response['type'], "tone": response['tone']})
                            st.download_button(
                                label="📘 DOCX",
                                data=docx_bytes,
                                file_name=f"TUM_{response['name']}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"all_download_docx_{idx}"
                            )
                        except Exception as e:
                            st.error(f"DOCX export error: {str(e)}")
        else:
            st.info("No responses generated yet.")
        
        return doc_type, tone, sender_name, sender_profession, language

# --- Chat UI ---
def render_chat():
    if st.session_state.messages:
        for i, message in enumerate(st.session_state.messages):
            role = message['role']
            # Clean the content properly for better alignment and markdown removal
            content = clean_response_text(message['content'])
            
            if role == 'user':
                # User message - aligned right with human icon
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end; margin: 15px 0; align-items: flex-start;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                color: white; 
                                padding: 15px 18px; 
                                border-radius: 18px 18px 4px 18px; 
                                max-width: 70%; 
                                margin-right: 10px;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                font-size: 14px;
                                line-height: 1.5;
                                white-space: pre-line;
                                word-wrap: break-word;">
                        {content}
                    </div>
                    <div style="background: #667eea; 
                                color: white; 
                                border-radius: 50%; 
                                width: 35px; 
                                height: 35px; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center;
                                font-size: 16px;
                                flex-shrink: 0;">
                        👤
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Assistant message - aligned left with robot icon
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start; margin: 15px 0; align-items: flex-start;">
                    <div style="background: #28a745; 
                                color: white; 
                                border-radius: 50%; 
                                width: 35px; 
                                height: 35px; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center;
                                font-size: 16px;
                                flex-shrink: 0;
                                margin-right: 10px;">
                        🤖
                    </div>
                    <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
                                color: #333; 
                                padding: 15px 18px; 
                                border-radius: 18px 18px 18px 4px; 
                                max-width: 70%; 
                                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                                font-size: 14px;
                                line-height: 1.5;
                                border: 1px solid #dee2e6;
                                white-space: pre-line;
                                word-wrap: break-word;">
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# --- Input UI ---
def render_input(doc_type, sender_name="", sender_profession=""):
    # Validation logic
    fields_valid = sender_name.strip() and sender_profession.strip()
    
    # Show suggested prompts only for new documents
    suggested = SUGGESTED_PROMPTS.get(doc_type, [])
    if st.session_state.show_suggestions and suggested and not st.session_state.document_history:
        st.markdown("**💡 Suggested prompts:**")
        cols = st.columns(len(suggested))
        for i, suggestion in enumerate(suggested):
            if cols[i].button(suggestion, key=f"suggestion_{i}_{st.session_state.message_counter}"):
                if fields_valid:
                    # Store suggestion and increment form key to reset form
                    st.session_state.current_prompt = suggestion
                    st.session_state.form_key += 1
                    st.rerun()
                else:
                    st.error("Please complete required fields in the sidebar first.")
    
    # Clear Chat button OUTSIDE the form
    col_clear, col_spacer = st.columns([1, 4])
    with col_clear:
        if st.button("🗑️ Clear Chat", key="clear_chat"):
            st.session_state.messages = []
            st.session_state.document_history = []
            st.session_state.current_document = None
            st.session_state.show_suggestions = True
            st.session_state.current_prompt = ""
            st.session_state.form_key += 1
            st.rerun()
    
    # Input form with dynamic key to handle suggestions properly
    with st.form(key=f"message_form_{st.session_state.form_key}"):
        if st.session_state.document_history:
            placeholder_text = "Enter your refinement request (e.g., 'change course name to C++', 'make it more formal', etc.)"
        else:
            placeholder_text = "Enter your prompt to generate a new document..."
        
        # Get default value from session state
        default_value = st.session_state.get("current_prompt", "")
        
        prompt = st.text_area(
            "Your message:",
            placeholder=placeholder_text,
            height=100,
            value=default_value
        )
        
        # Dynamic button state with helpful messaging
        if not fields_valid:
            st.warning("💡 Complete the required fields in the sidebar to enable document generation.")
            button_label = "Complete Required Fields First"
        else:
            button_label = "Send ✉️"
        
        send_clicked = st.form_submit_button(
            button_label,
            disabled=st.session_state.is_generating or not fields_valid,
            use_container_width=True
        )
        
        if st.session_state.is_generating:
            st.info("🔄 Generating response...")
    
    # Clear current_prompt after form is processed
    if send_clicked:
        st.session_state.current_prompt = ""
    
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
    /* Custom scrollbar for chat */
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 10px;
        margin-bottom: 20px;
    }
    .chat-container::-webkit-scrollbar {
        width: 6px;
    }
    .chat-container::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
    }
    .chat-container::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 3px;
    }
    .chat-container::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    </style>
    """, unsafe_allow_html=True)
    
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
        # Chat interface with custom container
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        render_chat()
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Input interface
        send_clicked, prompt = render_input(doc_type, sender_name, sender_profession)
        
        # Process message - ENHANCED MARKDOWN CLEANING FOR REFINEMENT
        if send_clicked and prompt.strip():
            # Double-check validation (safety net)
            if not sender_name.strip() or not sender_profession.strip():
                st.error("❌ System Error: Required fields validation failed. Please refresh and try again.")
                st.stop()
            
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
                        # REFINEMENT MODE
                        last_doc = st.session_state.document_history[-1]
                        
                        st.info(f"🔄 Refining document: {last_doc.get('type', 'Unknown')}")
                        
                        # Call refinement with correct parameters
                        result = llm.refine_document(
                            current_document=last_doc["content"],
                            refinement_prompt=prompt,
                            doc_type=DocumentType(last_doc.get("type", doc_type)),
                            tone=ToneType(last_doc.get("tone", tone)),
                            history=[]
                        )
                        
                        # Handle different response types from LLM
                        if isinstance(result, dict):
                            if "document" in result:
                                refined_content = result["document"]
                            elif "content" in result:
                                refined_content = result["content"]
                            else:
                                refined_content = str(result)
                        elif isinstance(result, str):
                            refined_content = result
                        elif hasattr(result, '__iter__'):
                            # Handle streaming response
                            refined_content = ""
                            for chunk in result:
                                if isinstance(chunk, dict):
                                    refined_content += chunk.get("document", chunk.get("content", str(chunk)))
                                else:
                                    refined_content += str(chunk)
                        else:
                            refined_content = str(result)
                        
                        # Enhanced cleaning with markdown removal
                        final_content = clean_response_text(refined_content)
                        
                        # Update the existing document instead of creating a new one
                        st.session_state.document_history[-1]["content"] = final_content
                        st.session_state.document_history[-1]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Add to complete history (this creates a new entry for refinement)
                        add_to_all_responses_history(
                            last_doc.get("type", doc_type), 
                            last_doc.get("tone", tone), 
                            final_content, 
                            sender_name, 
                            sender_profession
                        )
                        
                        # Update current document
                        st.session_state.current_document = final_content
                        
                        # Add assistant response
                        st.session_state.messages.append({"role": "assistant", "content": final_content})
                        
                        st.success("✅ Document refined successfully!")
                        
                    else:
                        # NEW DOCUMENT GENERATION
                        st.info("📝 Generating new document...")
                        
                        result = llm.generate_document(
                            doc_type=DocumentType(doc_type),
                            tone=ToneType(tone),
                            prompt=prompt,
                            sender_name=sender_name,
                            sender_profession=sender_profession,
                            language=language
                        )
                        
                        # Handle response
                        if isinstance(result, dict) and "document" in result:
                            full_response = result["document"]
                        else:
                            full_response = str(result)
                        
                        # Enhanced cleaning with markdown removal
                        final_content = clean_response_text(full_response)
                        
                        # Add new document to history
                        st.session_state.document_history.append({
                            "type": doc_type,
                            "tone": tone,
                            "content": final_content,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        # Add to complete history
                        add_to_all_responses_history(doc_type, tone, final_content, sender_name, sender_profession)
                        
                        # Update current document
                        st.session_state.current_document = final_content
                        
                        # Add assistant response
                        st.session_state.messages.append({"role": "assistant", "content": final_content})
                        
                        st.success("✅ New document generated successfully!")
                    
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
        # Document preview for all responses history
        if st.session_state.show_preview and st.session_state.preview_doc_idx is not None:
            if st.session_state.preview_doc_idx < len(st.session_state.all_responses_history):
                response = st.session_state.all_responses_history[st.session_state.preview_doc_idx]
                
                st.markdown("### 📖 Response Preview")
                st.markdown("---")
                
                st.markdown(f"**Name:** {response['name']}")
                st.markdown(f"**Type:** {response['type']}")
                st.markdown(f"**Tone:** {response['tone']}")
                st.markdown(f"**Created:** {response['timestamp']}")
                st.markdown("---")
                
                st.markdown("**Content:**")
                # Display with preserved formatting but proper alignment
                st.text(response['content'])
                
                if st.button("❌ Close", key="close_preview_btn"):
                    close_preview()
                    st.rerun()

if __name__ == "__main__":
    main()
