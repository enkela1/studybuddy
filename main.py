"""
Study Buddy - AI-powered study assistant for document learning.
Main application file using Streamlit.
"""

import os
import logging
import streamlit as st
from dotenv import load_dotenv

# Import our modules
from config import SUPPORTED_EXTS, ASSISTANT_INSTRUCTIONS
from file_manager import FileManager
from openai_client import StudyBuddyClient
from utils import process_message_with_citations

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize session state
if "file_manager" not in st.session_state:
    st.session_state.file_manager = FileManager()
if "openai_client" not in st.session_state:
    st.session_state.openai_client = None
if "start_chat" not in st.session_state:
    st.session_state.start_chat = False
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "quiz_thread_id" not in st.session_state:
    st.session_state.quiz_thread_id = None
if "files_processed" not in st.session_state:
    st.session_state.files_processed = set()
if "last_uploader_state" not in st.session_state:
    st.session_state.last_uploader_state = set()
if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0



# Set up the page
st.set_page_config(
    page_title="Study Buddy - Chat and Learn", 
    page_icon=":books:",
    layout="wide"
)

def initialize_openai_client():
    """Initialize the OpenAI client if not already done."""
    if st.session_state.openai_client is None:
        try:
            st.session_state.openai_client = StudyBuddyClient()
        except Exception as e:
            st.error(f"Failed to initialize OpenAI client: {e}")
            st.stop()

def handle_file_upload(uploaded_files):
    """Handle file uploads and processing."""
    if not uploaded_files:
        return

    for uploaded_file in uploaded_files:
        try:
            # Skip if already present by name
            if st.session_state.file_manager.has_file_with_name(uploaded_file.name):
                continue

            # Add to manager (creates a temp copy)
            file_info = st.session_state.file_manager.add_file(uploaded_file)

            # Upload to OpenAI Files API and record file_id
            file_id = st.session_state.openai_client.upload_file(file_info.temp_path)
            st.session_state.file_manager.update_file_id(file_info.original_name, file_id)

            # If a vector store already exists, attach this file_id to it now
            if st.session_state.file_manager.vector_store_id:
                st.session_state.openai_client.attach_file_to_vector_store(
                    st.session_state.file_manager.vector_store_id, file_id
                )

            st.sidebar.success(f"✅ {uploaded_file.name} uploaded successfully!")

        except Exception as e:
            st.sidebar.error(f"Failed to upload {uploaded_file.name}: {e}")
            logger.error(f"File upload failed: {e}")


def setup_vector_store_and_assistant():
    """Set up vector store and assistant for uploaded files."""
    if not st.session_state.file_manager.has_files():
        return

    # Already set up? Bail.
    if (st.session_state.file_manager.vector_store_id and
        st.session_state.file_manager.assistant_id):
        return

    try:
        # Create vector store
        vector_store_id = st.session_state.openai_client.create_vector_store()
        st.session_state.file_manager.vector_store_id = vector_store_id

        # Attach current files by file_id (no re-upload of paths)
        file_ids = st.session_state.file_manager.get_all_file_ids()
        if file_ids:
            st.session_state.openai_client.attach_files_to_vector_store(vector_store_id, file_ids)

        # Create assistant
        assistant_id = st.session_state.openai_client.create_assistant(
            name="Study Buddy",
            instructions=ASSISTANT_INSTRUCTIONS,
            vector_store_ids=[vector_store_id]
        )
        st.session_state.file_manager.assistant_id = assistant_id

        st.sidebar.success("🤖 AI Assistant ready!")

    except Exception as e:
        st.sidebar.error(f"Failed to create vector store or assistant: {e}")
        logger.error(f"Vector store/assistant creation failed: {e}")

def generate_quiz():
    """Generate a quiz from the uploaded documents."""
    if not st.session_state.file_manager.has_files():
        st.warning("Please upload files before generating a quiz.")
        return
    
    try:
        # Create or reuse quiz thread
        if not st.session_state.quiz_thread_id:
            st.session_state.quiz_thread_id = st.session_state.openai_client.create_thread()
        
        with st.spinner("Generating quiz..."):
            quiz_data = st.session_state.openai_client.generate_quiz(
                st.session_state.quiz_thread_id,
                st.session_state.file_manager.assistant_id
            )
            st.session_state.quiz_data = quiz_data
            st.success("Quiz generated successfully!")
            
    except Exception as e:
        st.error(f"Error generating quiz: {e}")
        logger.error(f"Quiz generation failed: {e}")

def start_chat():
    """Start a new chat session."""
    if not st.session_state.file_manager.has_files():
        st.warning("No files found. Please upload at least one file to get started.")
        return
    
    try:
        st.session_state.start_chat = True
        st.session_state.thread_id = st.session_state.openai_client.create_thread()
        st.success("Chat started!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to start chat: {e}")
        logger.error(f"Chat start failed: {e}")

def handle_chat_message(prompt):
    """Handle a chat message and generate response (no duplicate user append)."""
    try:
        # ✅ Do NOT append the user message here—it's already added in the chat_input block.

        # Get response from OpenAI
        response = st.session_state.openai_client.chat_with_assistant(
            st.session_state.thread_id,
            st.session_state.file_manager.assistant_id,
            prompt,
            instructions=(
                "Answer directly and concisely using only information grounded in the uploaded document(s). "
                "When summarizing, provide 5–8 bullet points plus key terms. "
                "Include inline citations like [1], [2] where the assistant provides references. "
                "Do not ask clarifying questions unless strictly necessary."
            ),
        )

        # Process citations
        full_response = process_message_with_citations(
            type('MockMessage', (), {
                'content': [type('MockContent', (), {'text': type('MockText', (), {'value': response})()})()]
            })(),
            filename=", ".join([f.original_name for f in st.session_state.file_manager.uploaded_files]),
        )

        # Append assistant reply once
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    except Exception as e:
        st.error(f"Failed to generate response: {e}")
        logger.error(f"Response generation failed: {e}")




# ==== Sidebar Section ====

st.sidebar.title("📁 File Management")

# File uploader
uploaded_files = st.sidebar.file_uploader(
    f"Upload documents (supported: .pdf, .txt, .md, .docx, .pptx, .csv, .json, .html, .py, .java, .rb, .tex, .c, .cpp)",
    type=list(SUPPORTED_EXTS),
    accept_multiple_files=True,
    key=f"file_upload_{st.session_state.uploader_version}",  # versioned key
    help="Upload new documents to analyze. Files already uploaded will be skipped automatically."
)

# Handle file uploads (only process files not already stored)
if uploaded_files:
    processed_names = {f.original_name for f in st.session_state.file_manager.uploaded_files}
    new_files = [f for f in uploaded_files if f.name not in processed_names]
    if new_files:
        handle_file_upload(new_files)


# Initialize OpenAI client
initialize_openai_client()

# Setup vector store and assistant
if st.session_state.file_manager.has_files():
    setup_vector_store_and_assistant()
elif st.session_state.file_manager.needs_vector_store_update():
    st.session_state.file_manager.clear_vector_store_info()
    st.session_state.start_chat = False
    st.session_state.messages = []
    st.session_state.quiz_data = None
    st.session_state.quiz_thread_id = None
    st.session_state.uploader_version += 1   # reset uploader key
    st.rerun()


# Display uploaded files
if st.session_state.file_manager.has_files():
    st.sidebar.subheader("📄 Uploaded Files")
    file_summary = st.session_state.file_manager.get_file_summary()
    for idx, file_info in enumerate(file_summary):
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            st.write(f"**{file_info['name']}**")
            st.caption(f"{file_info['size']} • {file_info['type']} • {file_info['uploaded']}")
        with col2:
            # Use index to make keys unique, even for files with same name
            if st.button("🗑️", key=f"remove_{idx}_{file_info['name']}", help="Remove file"):
                try:
                    # Remove from vector store & Files API, then locally
                    success = st.session_state.file_manager.remove_file_completely(
                        file_info['name'],
                        st.session_state.openai_client
                    )
                    if success:
                        st.sidebar.success(f"🗑️ {file_info['name']} removed successfully!")
                    else:
                        st.sidebar.warning(f"⚠️ {file_info['name']} removed locally; remote cleanup may have failed.")

                    # 🔄 Reset uploader so a deleted file isn't re-added on rerun
                    st.session_state.uploader_version += 1
                    st.session_state.last_uploader_state = set()

                    st.rerun()

                except Exception as e:
                    st.sidebar.error(f"❌ Failed to remove {file_info['name']}: {e}")
                    logger.error(f"File removal failed for {file_info['name']}: {e}")

# ==== Main Interface Section ====

st.title("Study Buddy 🧠")
st.write("Learn fast by chatting with your documents or take a quiz!")

# Tabs
chat_tab, quiz_tab = st.tabs(["💬 Chat", "🧪 Quiz"])

with chat_tab:
    if not st.session_state.start_chat:
        st.info("Start a chat to ask questions about your uploaded documents.")
        if st.button("🚀 Start Chatting…"):
            start_chat()
    else:
        # Show history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Single input → single append → single response
        prompt = st.chat_input("Ask about your documents…")
        if prompt:
            # Append the user message ONCE here
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Get the assistant reply
            with st.spinner("🤔 Thinking..."):
                handle_chat_message(prompt)

            # Rerun once to render the new assistant message
            st.rerun()


with quiz_tab:
    st.caption("Generate a quick quiz from your uploaded documents.")
    
    if st.button("🎯 Generate Quiz"):
        generate_quiz()
    
    if st.session_state.quiz_data:
        with st.form("quiz_form"):
            user_answers = {}
            for idx, question in enumerate(st.session_state.quiz_data):
                user_answers[idx] = st.radio(
                    f"**Question {idx + 1}:** {question['question']}",
                    question["options"],
                    key=f"quiz_{idx}"
                )
            submit_quiz = st.form_submit_button("📝 Submit Quiz")
        
        if submit_quiz:
            score = 0
            results = []
            for idx, question in enumerate(st.session_state.quiz_data):
                correct_answer = question["correct"]
                user_answer = user_answers[idx]
                if user_answer == correct_answer:
                    score += 1
                    results.append(f"✅ Question {idx + 1}: Correct!")
                else:
                    results.append(f"❌ Question {idx + 1}: Incorrect. The correct answer is: {correct_answer}")
            
            st.success(f"🎉 Your score: {score} out of {len(st.session_state.quiz_data)}")
            for res in results:
                st.write(res)

# Footer
st.markdown("---")
st.caption("Built️ using Streamlit and OpenAI GPT-4")
