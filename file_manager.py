"""
File management operations for Study Buddy application.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from config import SUPPORTED_EXTS, MAX_FILE_SIZE_MB
from utils import create_temp_filename, validate_file_type, get_file_size_mb, cleanup_temp_file

logger = logging.getLogger(__name__)

@dataclass
class UploadedFile:
    """Data class for uploaded file information."""
    original_name: str
    temp_path: str
    file_id: str
    file_size_mb: float
    file_type: str
    upload_time: float

class FileManager:
    """Manages file uploads and storage."""
    
    def __init__(self):
        """Initialize the file manager."""
        self.uploaded_files: List[UploadedFile] = []
        self.vector_store_id: Optional[str] = None
        self.assistant_id: Optional[str] = None
    
    def add_file(self, file_data: Any) -> Optional[UploadedFile]:
        """Add a new file to the manager."""
        try:
            # Validate file type
            if not validate_file_type(file_data.name, SUPPORTED_EXTS):
                raise ValueError(f"File type not supported: {file_data.name}")
            
            # Check file size
            file_size_mb = get_file_size_mb(file_data.size)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise ValueError(f"File too large: {file_size_mb}MB (max: {MAX_FILE_SIZE_MB}MB)")
            
            # Create temporary file
            temp_filename = create_temp_filename(file_data.name)
            temp_path = temp_filename
            
            # Save file to disk
            with open(temp_path, "wb") as f:
                f.write(file_data.getbuffer())
            
            # Create file info
            file_info = UploadedFile(
                original_name=file_data.name,
                temp_path=temp_path,
                file_id="",  # Will be set after OpenAI upload
                file_size_mb=file_size_mb,
                file_type=Path(file_data.name).suffix.lower().lstrip("."),
                upload_time=time.time()
            )
            
            self.uploaded_files.append(file_info)
            logger.info(f"Added file: {file_data.name} ({file_size_mb}MB)")
            return file_info
            
        except Exception as e:
            logger.error(f"Failed to add file {file_data.name}: {e}")
            raise
    
    def get_file_by_name(self, filename: str) -> Optional[UploadedFile]:
        """Get a file by its original name."""
        for file in self.uploaded_files:
            if file.original_name == filename:
                return file
        return None
    
    def has_file_with_name(self, filename: str) -> bool:
        """Check if a file with the given name already exists."""
        return any(file.original_name == filename for file in self.uploaded_files)
    
    def remove_file(self, filename: str) -> bool:
        """Remove a file from the manager."""
        for i, file in enumerate(self.uploaded_files):
            if file.original_name == filename:
                # Clean up temp file
                cleanup_temp_file(file.temp_path)
                # Remove from list
                self.uploaded_files.pop(i)
                logger.info(f"Removed file: {filename}")
                return True
        return False
    
    def get_all_temp_paths(self) -> List[str]:
        """Get all temporary file paths."""
        return [file.temp_path for file in self.uploaded_files]
    
    def get_all_file_ids(self) -> List[str]:
        """Get all OpenAI file IDs."""
        return [file.file_id for file in self.uploaded_files if file.file_id]
    
    def get_file_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all uploaded files."""
        return [
            {
                "name": file.original_name,
                "size": f"{file.file_size_mb}MB",
                "type": file.file_type,
                "uploaded": time.strftime("%H:%M:%S", time.localtime(file.upload_time))
            }
            for file in self.uploaded_files
        ]
    
    def update_file_id(self, filename: str, file_id: str) -> bool:
        """Update the OpenAI file ID for a file."""
        for file in self.uploaded_files:
            if file.original_name == filename:
                file.file_id = file_id
                logger.info(f"Updated file ID for {filename}: {file_id}")
                return True
        return False
    
    def has_files(self) -> bool:
        """Check if there are any uploaded files."""
        return len(self.uploaded_files) > 0
    
    def get_file_count(self) -> int:
        """Get the total number of uploaded files."""
        return len(self.uploaded_files)
    
    def cleanup_all_files(self) -> None:
        """Clean up all temporary files."""
        for file in self.uploaded_files:
            cleanup_temp_file(file.temp_path)
        self.uploaded_files.clear()
        logger.info("Cleaned up all temporary files")
    
    def get_supported_extensions_text(self) -> str:
        """Get a formatted string of supported file extensions."""
        extensions = list(SUPPORTED_EXTS)
        if len(extensions) <= 3:
            return ", ".join(extensions)
        else:
            return f"{', '.join(extensions[:3])}, and {len(extensions) - 3} more"
    
    def validate_files_for_processing(self) -> List[str]:
        """Validate that all files are ready for processing."""
        errors = []
        for file in self.uploaded_files:
            if not file.file_id:
                errors.append(f"{file.original_name}: Not uploaded to OpenAI")
            if not os.path.exists(file.temp_path):
                errors.append(f"{file.original_name}: Temporary file missing")
        return errors

    def remove_file_from_openai(self, filename: str, openai_client) -> bool:
        """Remove a file from the vector store (if present) and the OpenAI Files API."""
        try:
            file_info = self.get_file_by_name(filename)
            if not file_info:
                return False

            # Detach from vector store first
            if self.vector_store_id and file_info.file_id:
                try:
                    openai_client.remove_file_from_vector_store(self.vector_store_id, file_info.file_id)
                    logger.info(f"Detached from vector store: {filename}")
                except Exception as e:
                    logger.warning(f"Detach from vector store failed for {filename}: {e}")

            # Delete from OpenAI Files API
            if file_info.file_id:
                try:
                    openai_client.delete_file(file_info.file_id)
                    logger.info(f"Deleted file from OpenAI Files: {filename}")
                except Exception as e:
                    logger.warning(f"OpenAI Files delete failed for {filename}: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete file {filename} from OpenAI/vector store: {e}")
            return False

    def remove_file_completely(self, filename: str, openai_client=None) -> bool:
        """Remove a file completely - from local storage and OpenAI."""
        # First remove from OpenAI if client is provided
        if openai_client:
            self.remove_file_from_openai(filename, openai_client)
        
        # Then remove from local storage
        return self.remove_file(filename)
    
    def needs_vector_store_update(self) -> bool:
        """Check if vector store needs to be updated after file changes."""
        # If we have no files, vector store should be cleared
        if not self.uploaded_files:
            return bool(self.vector_store_id or self.assistant_id)
        
        # If we have files but no vector store, we need to create one
        if not self.vector_store_id:
            return True
        
        return False
    
    def clear_vector_store_info(self) -> None:
        """Clear vector store and assistant IDs when files are removed."""
        self.vector_store_id = None
        self.assistant_id = None
        logger.info("Cleared vector store and assistant IDs") 