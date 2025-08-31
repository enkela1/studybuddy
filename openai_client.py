"""
OpenAI client operations for Study Buddy application.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import openai
from config import OPENAI_MODEL, ASSISTANT_INSTRUCTIONS, QUIZ_GENERATION_PROMPT, QUIZ_GENERATION_TIMEOUT, CHAT_RESPONSE_TIMEOUT
from utils import extract_first_json_array, cleanup_temp_file
from typing import List

logger = logging.getLogger(__name__)

class StudyBuddyClient:
    """Client for handling OpenAI operations."""
    
    def __init__(self):
        """Initialize the OpenAI client."""
        try:
            self.client = openai.OpenAI()
            self.model = OPENAI_MODEL
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    def upload_file(self, filepath: str) -> str:
        """Upload a file to OpenAI and return its file ID."""
        try:
            with open(filepath, "rb") as f:
                response = self.client.files.create(file=f, purpose="assistants")

            return response.id
        except Exception as e:
            logger.error(f"Failed to upload file {filepath}: {e}")
            raise
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file from OpenAI servers."""
        try:
            self.client.files.delete(file_id)
            logger.info(f"Successfully deleted file from OpenAI: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from OpenAI {file_id}: {e}")
            return False
    
    def create_vector_store(self, name: str = "StudyBuddyVectorStore") -> str:
        """Create a vector store and return its ID."""
        try:
            vector_store = self.client.vector_stores.create(name=name)
            return vector_store.id
        except Exception as e:
            logger.error(f"Failed to create vector store: {e}")
            raise
    
    def upload_files_to_vector_store(self, vector_store_id: str, file_paths: List[str]) -> None:
        """Upload files to a vector store."""
        try:
            self.client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=[Path(path) for path in file_paths]
            )
        except Exception as e:
            logger.error(f"Failed to upload files to vector store: {e}")
            raise

    def attach_file_to_vector_store(self, vector_store_id: str, file_id: str) -> None:
        """Attach an already-uploaded OpenAI file_id to a vector store."""
        self.client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_id
        )

    def attach_files_to_vector_store(self, vector_store_id: str, file_ids: List[str]) -> None:
        """Attach multiple file_ids to a vector store."""
        for fid in file_ids:
            self.attach_file_to_vector_store(vector_store_id, fid)

    def remove_file_from_vector_store(self, vector_store_id: str, file_id: str) -> bool:
        """Remove a file from a vector store."""
        try:
            self.client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to remove file {file_id} from vector store {vector_store_id}: {e}")
            return False
    
    def create_assistant(self, name: str, instructions: str, vector_store_ids: List[str]) -> str:
        """Create an assistant with file search capabilities."""
        try:
            assistant = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=[{"type": "file_search"}],
                model=self.model,
                tool_resources={"file_search": {"vector_store_ids": vector_store_ids}}
            )
            return assistant.id
        except Exception as e:
            logger.error(f"Failed to create assistant: {e}")
            raise
    
    def create_thread(self) -> str:
        """Create a new thread and return its ID."""
        try:
            thread = self.client.beta.threads.create()
            return thread.id
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
            raise
    
    def send_message(self, thread_id: str, content: str) -> None:
        """Send a message to a thread."""
        try:
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=content
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    def run_assistant(self, thread_id: str, assistant_id: str, instructions: str = "") -> str:
        """Run an assistant in a thread and return the run ID."""
        try:
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                instructions=instructions
            )
            return run.id
        except Exception as e:
            logger.error(f"Failed to run assistant: {e}")
            raise
    
    def wait_for_run_completion(self, thread_id: str, run_id: str, timeout: int = 120) -> Dict[str, Any]:
        """Wait for a run to complete and return the run status."""
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise RuntimeError(f"Run timed out after {timeout} seconds")
            
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.status in {"completed", "failed", "cancelled", "expired"}:
                return run
            
            time.sleep(1)
    
    def get_assistant_messages(self, thread_id: str, run_id: str) -> List[Any]:
        """Get assistant messages from a completed run."""
        try:
            messages = self.client.beta.threads.messages.list(thread_id=thread_id)
            return [msg for msg in messages if msg.run_id == run_id and msg.role == "assistant"]
        except Exception as e:
            logger.error(f"Failed to get assistant messages: {e}")
            raise
    
    def generate_quiz(self, thread_id: str, assistant_id: str) -> List[Dict[str, Any]]:
        """Generate a quiz using the assistant."""
        try:
            # Send quiz generation prompt
            self.send_message(thread_id, QUIZ_GENERATION_PROMPT)
            
            # Run the assistant
            run_id = self.run_assistant(
                thread_id=thread_id,
                assistant_id=assistant_id,
                instructions="Use the file_search tool to base questions on the uploaded document content. Return only JSON."
            )
            
            # Wait for completion
            run = self.wait_for_run_completion(thread_id, run_id, QUIZ_GENERATION_TIMEOUT)
            
            if run.status != "completed":
                raise RuntimeError(f"Quiz generation run did not complete: {run.status}")
            
            # Get the response
            assistant_messages = self.get_assistant_messages(thread_id, run_id)
            if not assistant_messages:
                raise RuntimeError("No assistant message returned for quiz generation.")
            
            # Extract text content
            text_parts = []
            for part in assistant_messages[0].content:
                if getattr(part, "type", None) == "text":
                    text_parts.append(part.text.value)
            
            raw_output = "\n".join(text_parts).strip()
            
            # Parse the JSON response
            quiz_data = extract_first_json_array(raw_output)
            return quiz_data
            
        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")
            raise
    
    def chat_with_assistant(self, thread_id: str, assistant_id: str, message: str, instructions: str = "") -> str:
        """Chat with the assistant and return the response."""
        try:
            # Send the message
            self.send_message(thread_id, message)
            
            # Run the assistant
            run_id = self.run_assistant(thread_id, assistant_id, instructions)
            
            # Wait for completion
            run = self.wait_for_run_completion(thread_id, run_id, CHAT_RESPONSE_TIMEOUT)
            
            if run.status != "completed":
                raise RuntimeError(f"Chat response generation did not complete: {run.status}")
            
            # Get the response
            assistant_messages = self.get_assistant_messages(thread_id, run_id)
            if not assistant_messages:
                raise RuntimeError("No assistant message returned for chat.")
            
            # Return the first message content
            message_content = assistant_messages[0].content[0]
            if hasattr(message_content, "text"):
                return message_content.text.value
            else:
                return str(message_content)
                
        except Exception as e:
            logger.error(f"Chat with assistant failed: {e}")
            raise 